---
name: service-bootstrap
description: Scaffold a new service in this monorepo end-to-end — Dockerfile, .dockerignore, GHCR build-and-push GitHub Actions workflow, then verify by building locally, pushing, watching CI, and confirming the image landed on ghcr.io. Use this skill whenever the user wants to add a new service under `services/`, mentions "bootstrap a service", "scaffold service X", "give X a Dockerfile and CI", "set up CI for the new service", or otherwise wants to wire a fresh subdirectory of `services/` into the existing tasks-mcp / tasks-agent containerization pattern. Use it even if the user only asks for *part* of the flow (just the workflow file, just the Dockerfile) — this skill knows the whole pattern and the conventions and will produce something consistent with the rest of the repo.
---

# service-bootstrap

The repo's convention: every service under `services/<name>/` ships as a container image to `ghcr.io/<owner>/<repo>/<name>`, built and pushed by a per-service GitHub Actions workflow at `.github/workflows/<name>.yml`. The reference implementations are `services/tasks-mcp/` and `services/tasks-agent/` — when in doubt, read those first.

This skill walks through bootstrapping a brand-new service so it follows that pattern, and verifies the work end-to-end. Don't claim "done" until the image is visible on GHCR.

## Workflow

### 1. Capture intent

Confirm with the user before writing files:

- **Service name** — directory under `services/`, also the GHCR image suffix and workflow filename. The reference services use lowercase-hyphenated names (`tasks-mcp`, `tasks-agent`).
- **Shape** — HTTP server or CLI? This changes the Dockerfile (port + EXPOSE + HEALTHCHECK vs. just an ENTRYPOINT) and a couple of env defaults. If the user hasn't said, infer from the service's `pyproject.toml`:
  - Has a server framework dep (`fastapi`, `mcp`, `uvicorn`, `starlette`, …) or already binds a port → HTTP.
  - Built on `openai-agents`, click/typer-only, or otherwise interactive → CLI.
  - If still ambiguous, ask in one sentence rather than guessing.

If the service directory doesn't exist yet, that's fine — confirm the name and shape, then proceed. The Dockerfile and CI are the deliverables; service code is out of scope unless the user asks.

### 2. Read existing conventions

Before writing anything, read at least one reference service so you copy the right details (uv version, base image, env var naming, label conventions):

- `services/tasks-mcp/Dockerfile` — HTTP-shaped reference.
- `services/tasks-agent/Dockerfile` — CLI-shaped reference.
- `.github/workflows/tasks-mcp.yml` (or `tasks-agent.yml`) — workflow reference.

If the references have diverged from anything in this skill (e.g. uv version bumped), trust the references over this skill — they're the source of truth.

### 3. Create the Dockerfile

Delegate to the **`multi-stage-dockerfile`** skill for the actual Dockerfile authoring. Brief it with:

- The service path (`services/<name>/`).
- Whether it's HTTP or CLI.
- The repo conventions it must follow (paste these into the brief so the dockerfile skill doesn't have to guess):
  - Python 3.12, `python:3.12-slim-bookworm` base, multi-stage with `builder` and `runtime`.
  - `uv` from `ghcr.io/astral-sh/uv:0.10.6` (match the version the other services use unless the user says otherwise — check `services/tasks-mcp/Dockerfile`).
  - Bind-mounts for `pyproject.toml` / `uv.lock` / `README.md` in the cached deps layer; full source copy + project install in a second layer.
  - `--frozen --no-dev --no-editable` on `uv sync`.
  - Non-root runtime user (`uid 1001`, group `app`).
  - HTTP services: set `<NAME>_HOST=0.0.0.0`, `<NAME>_PORT=8000`, `<NAME>_LOG_LEVEL=INFO` env defaults; `EXPOSE 8000`; HEALTHCHECK that opens a TCP socket against the port.
  - CLI services: no EXPOSE, no HEALTHCHECK; create any working directories the entrypoint needs (e.g. `tasks-agent` mounts a sandbox `/workspace` owned by the app user).
  - `ENTRYPOINT ["<service-name>"]` (the project script from `pyproject.toml`'s `[project.scripts]`).

If you've already read the reference Dockerfiles in step 2 and the new service is a close shape match, it's fine to copy one of them and adapt rather than going back to the dockerfile skill — the goal is consistency, not novelty.

Also write `services/<name>/.dockerignore`. Match the reference (`.venv/`, caches, tests, `.git/`, `.python-version`, `.env*` except `.env.example`, the Dockerfile itself).

### 4. Create the CI workflow

Use `assets/workflow.yml.template` and substitute `__SERVICE_NAME__` with the service name. The result goes at `.github/workflows/<name>.yml`. Don't hand-rewrite the template — substitution is enough, and rewriting risks drift from the working pattern.

The template gives you, by design:
- Path-filtered triggers so the workflow only runs when its own service or workflow file changes.
- A concurrency group keyed on the ref so duplicate pushes cancel.
- Tags: `latest` on the default branch, the short SHA, and `<name>-vX.Y.Z` from matching git tags.
- Per-service GHA cache scope so services don't fight over cache.
- Push only on non-PR events (so forked PRs can't push).

### 5. Verify the build locally

Before touching git, prove the Dockerfile works:

```bash
docker build -t <name>:local services/<name>
```

For HTTP services, also run a quick container start to confirm the entrypoint binds:

```bash
docker run --rm -d --name <name>-smoke -p 18000:8000 <name>:local
sleep 2 && docker logs <name>-smoke && docker rm -f <name>-smoke
```

For CLI services, an import smoke test is enough — the entrypoint usually needs external services (an API key, an MCP server) that aren't worth setting up here:

```bash
docker run --rm --entrypoint python <name>:local -c "import <module>; print('ok')"
```

A traceback at the end of the CLI run from missing external deps is fine and expected; what you're checking is that the binary loads and the banner prints.

### 6. Commit only the new files

This is the part that's easy to get wrong and the user has flagged before: **don't sweep up unrelated staged changes**. Inspect `git status` first. If there are pre-existing staged or unrelated untracked changes, unstage them and add only the three files this skill creates:

```bash
git reset HEAD -- . >/dev/null
git add services/<name>/Dockerfile services/<name>/.dockerignore .github/workflows/<name>.yml
git status   # confirm only those three are staged
```

Match the existing commit style (look at `git log --oneline -5` — the tasks-mcp commits are the model). One commit, message focused on *what* and *why*:

```
Add prod Dockerfile and CI workflow for <name>

Mirrors the tasks-mcp setup: multi-stage uv build, non-root runtime,
GHCR push on main and on <name>-v* tags.
```

Push to `main` (the default branch in this repo).

### 7. Watch CI and verify GHCR

Don't declare done until the workflow is green and the image exists on GHCR.

```bash
# Get the run id (give Actions a few seconds to register the push first)
gh run list --workflow=<name>.yml --limit 1

# Stream until it finishes
gh run watch <run-id> --exit-status
```

Then confirm the image landed:

```bash
gh api "/users/<owner>/packages/container/<repo>%2F<name>/versions" \
  --jq '.[0:3] | .[] | {tags: .metadata.container.tags, created: .created_at}'
```

You should see `latest` and the short-SHA tag on the most recent version. If the package endpoint 404s, the image either hasn't published yet (rerun after a few seconds) or the workflow's GHCR push step was skipped (check `if: github.event_name != 'pull_request'`).

### 8. Report

Tell the user, in one short paragraph:
- The three files added (with paths).
- That the local build passed.
- The CI run id and duration.
- The GHCR tags that were published.
- How to cut a versioned release: `git tag <name>-vX.Y.Z && git push origin <name>-vX.Y.Z`.

Don't summarize what the Dockerfile or workflow contains — the user can read the diff. Save them the wall of text.

## Common pitfalls

- **Forgetting `<name>-v*` in the workflow's tag filter and the metadata-action match pattern.** Both have to use the *service-prefixed* tag, not bare `v*`, otherwise tagging one service triggers every workflow.
- **Cache scope collisions.** `cache-from` / `cache-to` must use `scope=<service-name>`. If two services share a scope they thrash each other's cache and builds get slower over time, not faster.
- **EXPOSE without a HEALTHCHECK** (or vice versa). For HTTP services, do both; the readiness probe story on Kubernetes depends on the HEALTHCHECK matching the port the app actually binds.
- **Sweeping unrelated changes into the bootstrap commit.** Always `git reset HEAD -- .` and add only the three files. The user has called this out specifically.
- **Hand-rewriting the workflow YAML.** If you find yourself typing out `permissions:` or `docker/metadata-action` from memory, stop and use the template — the working version is right there.
- **Calling the work done before GHCR is verified.** The workflow can succeed and still skip the push step (e.g. on a PR event). Always check the registry.

## Files in this skill

- `assets/workflow.yml.template` — substitute `__SERVICE_NAME__` to produce `.github/workflows/<name>.yml`.
