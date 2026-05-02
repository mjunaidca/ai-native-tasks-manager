# OpenAI Agents SDK — Study Notes for the Tasks Manager Agent

Source of truth: <https://openai.github.io/openai-agents-python/>. Fetched
2026-05-02. Re-verify against official docs before implementation.

This file is a working brief, not a tutorial. It covers only the
primitives we plan to use, mapped to our `AGENTS.md` constitution.

For locked decisions see `decisions.md`. The full spec lives in
`spec.md`.

---

## 1. Agent

The core unit. Two required fields, several optional ones.

| Field | Required | Notes |
|---|---|---|
| `name` | yes | Human-readable id; used in traces and handoff tool names. |
| `instructions` | yes | System prompt. May be a string or a callable receiving `RunContextWrapper` + `Agent` (dynamic instructions). |
| `model` | no | Model id; defaults to SDK default. |
| `tools` | no | List of `@function_tool` callables, hosted tools, or other agents exposed via `as_tool()`. |
| `mcp_servers` | no | List of MCP server clients (see §3). Tools auto-listed. |
| `output_type` | no | Pydantic model / dataclass for structured outputs. |
| `handoffs` | no | Sub-agents this agent can delegate to (see §5). |
| `input_guardrails` / `output_guardrails` | no | Validators that can short-circuit a run (see §6). |
| `model_settings` | no | Temperature, `tool_choice`, etc. |
| `hooks` | no | Lifecycle callbacks. |

Minimal:

```python
from agents import Agent, function_tool

@function_tool
def get_weather(city: str) -> str:
    return f"The weather in {city} is sunny"

agent = Agent(
    name="Weather Assistant",
    instructions="Help users with weather information",
    tools=[get_weather],
)
```

**For us:** instructions stay strict and constitution-aligned (clarify
before action, confirm before destructive). Tools come from MCP, not
from `@function_tool` — we don't re-implement task ops in Python.

---

## 2. Runner

Three entry points: `Runner.run` (async), `Runner.run_sync`,
`Runner.run_streamed`. The agent loop:

1. Call LLM with current agent + input.
2. If response has `final_output` and no tool calls → done.
3. If response is a handoff → switch active agent, loop.
4. If response has tool calls → execute, append results, loop.
5. Respect `max_turns`; raises `MaxTurnsExceeded` past the limit.

`error_handlers={"max_turns": fn, "model_refusal": fn}` lets us return a
controlled `final_output` instead of raising.

**For us:** v1 CLI uses `Runner.run_sync` for simplicity. Set
`max_turns` defensively so a runaway loop can't burn tokens. Wire a
`max_turns` handler that returns a polite "I couldn't finish — please
restate" message.

---

## 3. MCP integration

Three transport clients (plus a hosted variant we don't need):

- `MCPServerStreamableHttp` — what our `tasks-mcp` server speaks.
- `MCPServerStdio` — for subprocess servers.
- `MCPServerSse` — deprecated.

Attach to an Agent via `mcp_servers=[...]`. Tools are auto-listed each
run; cache with `cache_tools_list=True`.

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp

async with MCPServerStreamableHttp(
    name="Tasks MCP",
    params={"url": "http://localhost:8000/mcp", "timeout": 10},
    cache_tools_list=True,
    max_retry_attempts=3,
) as tasks_server:
    agent = Agent(
        name="Tasks Manager",
        instructions=...,
        mcp_servers=[tasks_server],
    )
    result = await Runner.run(agent, "Capture: pay rent tomorrow 5pm UTC")
```

**Approval / filtering** (relevant to our destructive-action rule):

- `require_approval`: `"always" | "never"`, or per-tool mapping
  (`{"remove_task": "always", "review_tasks": "never"}`), or grouped
  syntax (`{"always": {"tool_names": ["remove_task"]}}`).
- Static or dynamic `tool_filter` for allow/block lists.
- `tool_meta_resolver` to inject per-call metadata (correlation ids,
  user ids) into the MCP `_meta` payload.

**For us:**
- Connect to Tasks MCP over Streamable HTTP at the K8s service URL
  (env var, not localhost).
- `cache_tools_list=True` is fine — the tool surface is fixed.
- Use `require_approval` with `remove_task` (and `resolve_task` when
  it would cancel) marked `"always"`. This is the constitution's
  "destructive actions require user confirmation" rule expressed at
  the SDK boundary.
- Use `tool_meta_resolver` to pass a correlation id per turn for
  traceability against MCP server logs.

---

## 4. Sessions

Auto-managed conversation history. Before each `Runner.run`, the
session is read and prepended; after, new items are persisted.

Backends: `SQLiteSession`, `AsyncSQLiteSession`, `RedisSession`,
`SQLAlchemySession`, `MongoDBSession`, `DaprSession`,
`OpenAIConversationsSession`, plus `EncryptedSession` wrapper.

```python
from agents import Agent, Runner, SQLiteSession

session = SQLiteSession("conversation_123", "history.db")
result = await Runner.run(agent, "Hi", session=session)
```

`pop_item()` removes the last item; `clear_session()` wipes.

**For us:** v1 CLI uses an in-memory `SQLiteSession` keyed on a single
hardcoded session id (matches the in-memory Tasks MCP store —
restart = fresh state). Keep the backend swappable so the future
HTTP service can move to Redis or SQLAlchemy without reshaping the
agent.

---

## 5. Handoffs

Used to delegate to a specialist agent within the same run.

```python
from agents import Agent, handoff

booking_agent = Agent(name="Appointment Booking")

tasks_agent = Agent(
    name="Tasks Manager",
    handoffs=[handoff(booking_agent)],
)
```

Handoffs surface to the LLM as tools named
`transfer_to_<agent_name>`. The receiving agent inherits the
conversation by default; can be filtered. Stays within a single run.

**For us:** not in v1. Reserved for the future Appointment Booking
Agent. The decision record in `decisions.md` already requires booking
to enter via Handoffs and **never** mutate tasks directly — that
boundary is enforced by giving the booking agent no `mcp_servers` for
Tasks MCP.

---

## 6. Guardrails

Two kinds:

- **Input guardrails** — run before the agent loop, only on the first
  agent in a chain. Useful for validating user input, blocking
  obviously bad requests cheaply.
- **Output guardrails** — run after the final agent produces output,
  only on the final agent.

Each returns a `GuardrailFunctionOutput`. If
`tripwire_triggered=True`, the SDK raises
`InputGuardrailTripwireTriggered` / `OutputGuardrailTripwireTriggered`
and halts.

```python
from agents import GuardrailFunctionOutput, input_guardrail

@input_guardrail
async def reject_naive_dates(ctx, agent, input):
    bad = looks_like_naive_datetime(input)
    return GuardrailFunctionOutput(
        output_info="naive datetime" if bad else None,
        tripwire_triggered=bad,
    )
```

**For us — important nuance:** the constitution requires confirmation
on **destructive tool calls**, not on "the final answer mentions a
delete word." The cleanest implementation is **MCP `require_approval`
on `remove_task`** (and cancel transitions of `resolve_task`) — that
intercepts the actual tool call. Output guardrails on the assistant
text are too late and too unreliable.

We'll use guardrails for cheaper checks: missing `due_at` timezone in
input, empty/garbage input, etc.

---

## 7. Tracing

Built-in. Every step (LLM call, tool call, handoff, guardrail) emits a
span. Default sink is OpenAI traces; third-party processors pluggable.

**For us:** enable tracing from day one. Pass a correlation id on each
turn (also threaded into MCP `_meta`) so a single user action can be
followed across agent → MCP → store.

---

## 8. What we will NOT use in v1

- **Sandbox agents / harness** — see `decisions.md` (Decision 2).
- **Voice / Realtime** — out of scope.
- **Hosted MCP tool** — we run our own MCP server.
- **Multiple model providers** — single OpenAI model in v1.
- **Output guardrails for confirmation** — replaced by MCP
  `require_approval`.
- **Persistent Sessions backend** — in-memory only in v1.

---

## 9. Open questions to resolve in `spec.md`

1. Which model do we default to (and how is it configurable)?
2. Exact `require_approval` policy: just `remove_task`, or also
   `resolve_task` when status would become `cancelled`?
3. How does the CLI render a confirmation prompt when `require_approval`
   fires? (SDK exposes an approval callback path; need to confirm shape.)
4. How do we pass `user_id` into MCP calls — via instructions, via
   `tool_meta_resolver`, or both?
5. Where do API keys live in dev (env file) and what's the K8s secret
   plan when we get there?
6. `max_turns` default — start with 8, revisit after first eval run.

These get answered, with code-level detail, in `spec.md`.
