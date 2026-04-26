# Tasks MCP Server — Implementation Plan (v1)

This document plans **how** we will build the Tasks MCP server defined in
`tasks-server-tools.md`, following the cross-cutting choices in
`decisions.md`.

It does not contain code. It defines project layout, dependencies,
test-first workflow, end-to-end live verification, and the exit criteria
that gate "done".

---

## 0. Guardrails

- **Skill in use:** `mcp-builder` (loaded). Reference docs to consult
  during implementation:
  - MCP Best Practices: `.claude/skills/mcp-builder/reference/mcp_best_practices.md`
  - Python guide: `.claude/skills/mcp-builder/reference/python_mcp_server.md`
  - Evaluation guide: `.claude/skills/mcp-builder/reference/evaluation.md`
  - Python SDK README (fetch fresh): `https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md`
- **Language / runtime:** Python 3.12+ (per `AGENTS.md`).
- **Package manager:** `uv` exclusively. No `pip`, `poetry`, or `conda`.
- **TDD:** every behavior arrives as a failing test first, then the
  smallest change that makes it pass, then refactor.
- **Verification rule (from `AGENTS.md`):** unverified is the same as
  broken. The server must be run live and exercised end-to-end before
  this work is considered delivered.

---

## 1. Project Layout

New top-level directory in the repo:

```
services/
  tasks-mcp/
    pyproject.toml            # uv-managed
    uv.lock
    README.md                 # one-page: what it is, how to run, how to test
    src/
      tasks_mcp/
        __init__.py
        server.py             # MCP server bootstrap + transport
        tools.py              # 5 tool registrations (capture/review/modify/resolve/remove)
        models.py             # Pydantic models: Task, inputs, outputs, error envelope
        store.py              # in-memory store (dict + lock), per-user scoping
        time_utils.py         # UTC parsing/formatting, "today/overdue/upcoming" resolution
        errors.py             # error codes + envelope helper
    tests/
      unit/
        test_models.py
        test_store.py
        test_time_utils.py
        test_tools_capture.py
        test_tools_review.py
        test_tools_modify.py
        test_tools_resolve.py
        test_tools_remove.py
      integration/
        test_mcp_protocol.py  # boots the server in-process, exercises tools via MCP client
      e2e/
        test_live_server.py   # boots the server as a subprocess on HTTP, hits it over the wire
```

`services/` is introduced as the conventional home for deployable units in
this repo. Future MCP servers and APIs live as siblings.

---

## 2. Dependencies (via `uv`)

All dependency management goes through `uv`. Standard CLI commands:

| Action | Command |
|---|---|
| Init project | `uv init --package tasks-mcp` |
| Add runtime dep | `uv add <pkg>` |
| Add dev dep | `uv add --dev <pkg>` |
| Sync env | `uv sync` |
| Run a script | `uv run <cmd>` |
| Lock | `uv lock` |

**Runtime dependencies** (initial set, justified):

- `mcp` — official Python MCP SDK (FastMCP). Required.
- `pydantic` (>=2) — input/output validation, structured outputs.
- `python-ulid` — task IDs.

**Dev dependencies:**

- `pytest` — test runner.
- `pytest-asyncio` — async tests for tool handlers.
- `httpx` — HTTP client for end-to-end tests against the live server.
- `ruff` — lint + format.
- `mypy` — type checking.

No queues, databases, ORMs, or web frameworks. The MCP SDK provides the
HTTP transport.

---

## 3. TDD Workflow

We work in **vertical slices**, one tool at a time. For each slice:

1. **Red** — write a failing unit test that captures one behavior of the
   tool (happy path, then one or two edge cases).
2. **Green** — implement the smallest change in `models.py` / `store.py` /
   `tools.py` to make the test pass.
3. **Refactor** — tighten naming, eliminate duplication, keep functions
   small. Re-run tests.
4. **Lint + type check** — `uv run ruff check`, `uv run mypy src`.

### Build order

The order is chosen so each slice depends only on what came before:

1. **Foundations** (no tools yet)
   - `time_utils`: parse UTC ISO-8601, reject naive/non-UTC, format with `Z`.
   - `errors`: error envelope shape, code enum, helper to build errors.
   - `models`: `Task`, input models, output wrappers — Pydantic only,
     no I/O.
   - `store`: in-memory dict guarded by a lock, per-`user_id` scoping,
     CRUD primitives that the tools will call.

2. **Tools** (one at a time, full TDD per tool)
   1. `capture_task` — also exercises ULID generation, `default-user`
      fallback, UTC validation on `due_at`.
   2. `review_tasks` — filters (`today`/`overdue`/`upcoming`/`open`/`all`),
      `tz` parameter, free-text `query`, pagination cursor, per-user
      scoping.
   3. `modify_task` — partial update, `null` clears, owner check returns
      `not_found` on mismatch.
   4. `resolve_task` — state machine, idempotent same-outcome,
      `invalid_state_transition` on conflict.
   5. `remove_task` — destructive hint, idempotent on already-removed.

3. **MCP wiring**
   - `server.py`: register the 5 tools with annotations
     (`readOnlyHint`, `destructiveHint`, `idempotentHint`), output schemas,
     and concise descriptions.
   - Choose Streamable HTTP transport, stateless JSON (per Decision 1).

4. **Integration tests** (`tests/integration/`)
   - Boot the FastMCP server in-process and call each tool through the
     MCP client API. Verifies the handlers are correctly registered, the
     schemas match, and the protocol envelope is right.

5. **End-to-end tests** (`tests/e2e/`)
   - Launch the server as a subprocess on a real port. Use `httpx` to hit
     `POST /mcp` with raw JSON-RPC payloads. Verifies the wire format,
     content-type handling, and that the deployable artifact actually
     speaks MCP over HTTP.

### Test coverage targets per tool

For each tool, at minimum:

- 1 happy-path test.
- 1 validation failure (e.g. naive datetime, missing required field).
- 1 cross-user `not_found` test (where applicable).
- 1 idempotency test (where applicable).
- 1 state-machine edge case (`resolve_task` only).

Pagination, `query`, and each filter on `review_tasks` get their own
tests.

---

## 4. Local Run & Live Verification

After all unit + integration tests pass, the server must be exercised
**live** before this work is called done.

### Run the server

```
cd services/tasks-mcp
uv run tasks-mcp                # entry point defined in pyproject.toml
# binds to 127.0.0.1:8000 by default; configurable via env vars
```

Configuration via env vars (so it's K8s-ready from day one, per
`AGENTS.md`):

- `TASKS_MCP_HOST` (default `0.0.0.0`)
- `TASKS_MCP_PORT` (default `8000`)
- `TASKS_MCP_LOG_LEVEL` (default `INFO`)

### Live end-to-end checklist

Run each by hand against the running server (using either the MCP
Inspector or a small `httpx` script captured under `scripts/smoke.py`)
and confirm the result. Each item is a **gate** — if it doesn't pass live,
the work is not done.

1. **List tools** — protocol `tools/list` returns exactly 5 tools with
   the correct names, annotations, and output schemas.
2. **Capture** — `capture_task` with a title and a UTC `due_at` returns a
   Task with a generated id, `user_id: "default-user"`, status `pending`,
   `created_at`/`updated_at` populated.
3. **Capture (validation)** — `capture_task` with a naive datetime is
   rejected with `invalid_argument` and an actionable message.
4. **Capture (with user)** — `capture_task` with `user_id: "alice"`
   returns a task owned by alice.
5. **Review (default user)** — `review_tasks(filter="open")` returns the
   default-user task from step 2 but **not** alice's task from step 4.
6. **Review (filters)** — verify `today`, `overdue`, `upcoming` against
   tasks created with carefully chosen `due_at` values; also verify the
   `tz` parameter changes which tasks fall into `today`.
7. **Review (pagination)** — create >50 tasks, page through with
   `cursor`, verify no duplicates and no gaps.
8. **Modify** — change title, then clear `description` with `null`, then
   reject a missing-id call with `not_found`.
9. **Modify (cross-user)** — try to modify alice's task as default-user;
   expect `not_found` (not `forbidden` — we don't disclose existence).
10. **Resolve happy path** — complete a pending task; second identical
    call is a no-op success.
11. **Resolve conflict** — complete then cancel returns
    `invalid_state_transition` with a suggestion.
12. **Remove** — delete a task; second delete returns
    `{ removed: true }` (idempotent), not `not_found`.
13. **Cross-user remove** — try to remove alice's task as default-user;
    expect `not_found`.
14. **Restart** — kill the server, start it again, confirm storage is
    empty (in-memory by design). This makes the single-replica
    constraint visible.

The result of running this checklist gets pasted into the PR description
as proof of live verification, per the `AGENTS.md` "Always Verify" rule.

---

## 5. Quality Gates Before Delivery

In order, all must be green:

1. `uv run pytest` — unit, integration, and e2e all pass.
2. `uv run ruff check` and `uv run ruff format --check`.
3. `uv run mypy src` — clean.
4. **Live checklist** in §4 — every item passes against a running
   server.
5. Spec-vs-implementation diff review: tool count, names, input fields,
   output shape, error codes match `tasks-server-tools.md` exactly. Any
   intentional drift is reflected back into the spec in the same PR.
6. README in `services/tasks-mcp/` covers: what it is, how to run, how to
   test, known constraints (single replica, no auth, in-memory).

---

## 6. Out of Scope for This Implementation

These are deliberately not part of v1 and should be rejected if they
creep in during implementation:

- Persistent storage / databases.
- Authentication, JWT validation, or user verification.
- Idempotency keys on `capture_task`.
- Reminders, notifications, recurring tasks, sub-tasks, dependencies,
  tags, priorities, sharing.
- Multi-replica deployment, leader election, distributed locks.
- Any retry/circuit-breaker/queueing infrastructure.

If a need for any of these surfaces during implementation, capture it as
a follow-up and continue.

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| MCP SDK API drifts from what the skill docs describe | Fetch the SDK README live in Phase 1 of mcp-builder; pin the SDK version in `pyproject.toml`. |
| `today`/`overdue` timezone math is subtly wrong | Dedicated `time_utils` module with its own tests covering DST boundaries and IANA edge cases. |
| In-memory store accidentally shared across `user_id`s | Cross-user `not_found` test on every mutating tool, run live too (steps 9 and 13 above). |
| Single-replica constraint silently violated in K8s manifests | Manifests are out of scope here, but the README must explicitly say `replicas: 1` and `strategy: Recreate` so whoever writes the deployment cannot miss it. |

---

## 8. Definition of Done

- All five tools implemented, tested, and registered with correct MCP
  annotations and output schemas.
- `uv run pytest`, `ruff`, and `mypy` are green.
- The live end-to-end checklist (§4) was executed against a running
  server and every step passed. Results captured in the PR.
- Spec (`tasks-server-tools.md`) and implementation match; any
  intentional drift was reflected back into the spec.
- README explains how to run and what is intentionally missing
  (auth, persistence, multi-replica).
