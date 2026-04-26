# tasks-mcp

The Tasks MCP server (v1) for the AI-native tasks manager.

Implements the spec in `specs/mcp-server/tasks-server-tools.md`, following
the cross-cutting decisions in `specs/mcp-server/decisions.md`.

## What it is

- **Transport:** Streamable HTTP, stateless JSON (no sessions, no SSE).
- **Storage:** in-memory `dict` guarded by a lock. Lost on restart.
- **Auth:** none. Every tool accepts an optional `user_id`; if omitted, the
  task is owned by the constant `"default-user"`.
- **Tools (5):** `capture_task`, `review_tasks`, `modify_task`,
  `resolve_task`, `remove_task`. Tool names, input fields, and error codes
  match the spec exactly.

## How to run

```bash
cd services/tasks-mcp
uv sync
uv run tasks-mcp                # 0.0.0.0:8000/mcp by default
```

Configuration via env vars:

| Var | Default |
|---|---|
| `TASKS_MCP_HOST` | `0.0.0.0` |
| `TASKS_MCP_PORT` | `8000` |
| `TASKS_MCP_LOG_LEVEL` | `INFO` |

## How to test

```bash
uv run pytest                   # unit + integration + e2e
uv run ruff check
uv run ruff format --check
uv run mypy src
```

A live smoke script is provided:

```bash
uv run python scripts/smoke.py  # exercises all 14 live-checklist items
```

## Known constraints (v1)

- **Single replica only.** State is in-memory and not shared across pods.
  The Kubernetes Deployment must use `replicas: 1` and `strategy: Recreate`
  until persistent storage lands.
- **No authentication.** Deploy only on a trusted internal network.
- **No timezone guessing.** All `due_at` values must be ISO-8601 UTC with
  the trailing `Z` suffix. Naive or non-UTC datetimes are rejected.
- **No reopen, no batch, no idempotency keys.** See the "Deferred" section
  in `tasks-server-tools.md`.

## Layout

```
src/tasks_mcp/
  server.py     # FastMCP bootstrap + tool registration
  tools.py      # tool implementations (pure logic)
  models.py     # Pydantic input/output models
  store.py      # in-memory store
  errors.py     # error envelope
  time_utils.py # UTC parsing/formatting + timezone day boundaries
tests/
  unit/         # 50 tests
  integration/  # 6 tests (in-process FastMCP)
  e2e/          # 2 tests (subprocess HTTP)
```
