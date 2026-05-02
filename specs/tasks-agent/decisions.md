# Tasks Manager Agent — Decisions (v1)

This file records locked decisions for the Tasks Manager Agent. Detailed
behavior belongs in `spec.md`; SDK study notes belong in `sdk-study.md`.

---

## Decision 1 — SDK choice

**Decision:** Build the Tasks Manager Agent on the **OpenAI Agents SDK**
(Python).

**Why:**
- Python 3.12 + `uv` are the repo defaults (`AGENTS.md`).
- First-class MCP integration — our Tasks MCP server attaches directly,
  no Python re-wrapping of tools.
- Built-in primitives we already need: Sessions (memory), Handoffs
  (future Appointment Booking Agent), Guardrails (destructive-action
  confirmation), Tracing (observability requirement).

---

## Decision 2 — Agent type: Sandbox Agent (revised)

**Decision:** The Tasks Manager Agent is a **`SandboxAgent`** from the
OpenAI Agents SDK. It still drives the conversation and calls Tasks MCP
for all task mutations; the sandbox provides a persistent workspace,
filesystem/shell tools, and harness memory for capabilities the simple
agent cannot offer (bulk import from files, scripted workflows, future
browser/computer automation through handoffs).

**Why (revised):**
1. Forward-compatibility with the broader product: bulk import,
   scripted reconciliation, and future Appointment Booking Agent
   handoffs benefit from a real workspace.
2. `SandboxAgent` keeps the full `Agent` surface — `mcp_servers`,
   handoffs, instructions, model — so the constitution's rule that
   *task mutations go through Tasks MCP* still holds. The sandbox is
   additive, not a bypass.
3. Confirmed: works with non-OpenAI providers via `LitellmModel`, so
   our Gemini constraint is preserved (Decision 3).

**Boundary still enforced:** even with sandbox capabilities present,
all task mutations MUST go through the Tasks MCP server. The sandbox's
filesystem and shell are for *side work* (parsing inputs, scratch
artifacts, scripts), never for storing or modifying tasks.

**Backend choice (v1):** start with `UnixLocalSandboxClient` for local
development. Hosted backends (E2B / Modal / Daytona) are deferred to
the K8s deployment milestone; revisit then.

**Capabilities (v1):** constructed with `capabilities=[]`. Reason: the
default sandbox capability set includes hosted/grammar tools (e.g.
`apply_patch`) that require OpenAI's **Responses API**. LiteLLM —
which we use for Gemini — speaks only ChatCompletions, so default
capabilities raise at runtime. With `capabilities=[]` we still get the
sandbox **workspace, filesystem, and shell runtime**; we just lose the
hosted file-editor tools. If/when a feature genuinely needs
`apply_patch` we either (a) switch that flow to OpenAI as the model,
or (b) introduce a ChatCompletions-compatible replacement.

**Earlier rejection of Sandbox is recorded for history:** the prior
arguments (smaller blast radius, simpler K8s fit, lower latency) are
real tradeoffs we've now accepted in exchange for the capability
ceiling.

---

## Decision 3 — Models

**Decision:** v1 supports two model providers, selectable by env var:

- **OpenAI** (default model TBD when we wire it up).
- **Google Gemini**, model `gemini-3.1-flash-lite-preview`, via the
  SDK's non-OpenAI provider adapter.

**Why:** Cost/latency comparison and provider-portability check from
day one. The simple-agent loop is provider-agnostic; the sandbox
harness is not (it's OpenAI-only in practice), which further validates
Decision 2.

---

## Decision 4 — No approval gate in v1

**Decision:** v1 does **not** use MCP `require_approval` or any
guardrail-driven confirmation flow. All tool calls execute directly.

**Why:** Prove the loop works end-to-end first. The CLI's existing
prompt-and-print interaction is enough oversight for a single local
user during bring-up.

**Revisit when:** an HTTP surface or multi-user UI lands — at that
point destructive-action confirmation must come back, per the
constitution. The MCP server already supports per-tool approval, so
this is a re-enable, not a redesign.

---

## Decision 5 — `user_id` is mocked

**Decision:** v1 hardcodes `user_id = "default-user"` (matches the
Tasks MCP server default). No per-call user injection.

**Revisit when:** real auth lands. At that point switch to passing
`user_id` via MCP `_meta` (and update the MCP server to read it).

---

## Decision 6 — Secrets

**Decision:** v1 reads API keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`)
from a local `.env` file via `python-dotenv`. No K8s secret wiring
yet.

---

## Decision 7 — `max_turns`

**Decision:** Start with the SDK default. Tune after first eval run.

---

## Decision 8 — Run surface (v1)

**Decision:** v1 ships as a **Python CLI** invoked via `uv run`. No HTTP
service, no UI yet.

**Why:**
- Lets us prove the agent loop, MCP wiring, and confirmation flow
  without committing to a transport.
- A FastAPI service or UI can wrap the same `Agent` later without
  reshaping the core.

**Out of scope for v1 (rejected if it creeps in):**
- Web UI, mobile UI, voice/realtime modalities.
- Multi-tenant auth.
- Persistent agent memory across processes (Sessions live in-process
  for v1, mirroring the in-memory Tasks MCP store).
- Sandbox backends.
- Multiple specialized agents — Appointment Booking Agent is a separate
  future workstream and only enters via Handoffs once it exists.
