# tasks-agent

The Tasks Manager Agent. Built on the **OpenAI Agents SDK** (Python).
v1 is a CLI; HTTP/UI come later.

See:
- `specs/tasks-agent/decisions.md` — locked design decisions.
- `specs/tasks-agent/sdk-study.md` — SDK primitives we use.

## Status

**Step 1 — Hello world.** Single Agent, no tools, no MCP. Two
providers: OpenAI and Google Gemini (via LiteLLM).

Coming next: Sessions → MCP tools → eval pass.

## Run

```bash
cd services/tasks-agent
cp .env.example .env   # fill in keys
uv sync
uv run tasks-agent
```

`.env` controls the provider:

```
TASKS_AGENT_PROVIDER=gemini      # or "openai"
GEMINI_API_KEY=...
OPENAI_API_KEY=...
TASKS_AGENT_GEMINI_MODEL=gemini-3.1-flash-lite-preview
TASKS_AGENT_OPENAI_MODEL=gpt-4.1-mini
```

## Constraints (v1)

- No persistent memory — Sessions are in-process and reset on restart.
- No auth — `user_id` is hardcoded to `default-user` when MCP lands in
  Step 3.
- No approval / confirmation gating — re-enabled when an HTTP/UI
  surface appears.
- Single replica only.
