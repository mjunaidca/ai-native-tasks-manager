# MCP Server — Design Decisions

This document captures the cross-cutting decisions for the MCP server(s) in
this repository. Server-specific specs (tool surface, schemas, etc.) live in
sibling files under `specs/mcp-server/` and reference these decisions.

Decisions are numbered. When a decision changes, update it in place and note
the date and reason in the **History** section at the bottom.

---

## Decision 1 — Transport & Deployment Shape

**Status:** Accepted (2026-04-26)
**Scope:** All MCP servers in this repo, v1.

### Choice

| Aspect | Choice |
| --- | --- |
| Transport | Streamable HTTP |
| Response mode | Stateless JSON (no SSE streaming) |
| Topology | Single shared Kubernetes Deployment + Service per MCP server |
| Sessions | None (no `Mcp-Session-Id`) |
| Authentication | None (v1, explicitly deferred) |

### Rationale

- The server will be deployed in Kubernetes and consumed by multiple agents
  running in different pods. stdio transport is single-consumer and local-only,
  so it is ruled out. Streamable HTTP is the only viable transport.
- Stateless JSON responses make every request independent of any specific pod.
  This gives us trivial horizontal scaling, safe rolling deploys, and no
  session-affinity routing — all of which align with the Kubernetes-first
  principle in `AGENTS.md`.
- A single shared Deployment + Service is the standard topology and keeps
  logs, metrics, and configuration in one place. Per-agent or per-tenant
  deployments are not justified at this stage.
- No sessions removes a whole class of "which pod owns my session" failure
  modes and simplifies the client contract for agents.
- Auth is explicitly out of scope for v1 to keep the first cut minimal. The
  server must therefore be deployed only on a trusted internal network until
  Decision 2 is taken.

### What we are giving up

By choosing stateless JSON over stateful SSE, the server cannot:

- Stream partial/progress responses mid-call.
- Push server-initiated notifications or logs to the client.
- Request "sampling" (ask the calling client's LLM to generate text).

None of these are needed for a request → do work → respond tool server. If a
future requirement needs them, revisit the response-mode sub-decision; the
transport choice itself does not need to change.

### Operational implications

- Service should expose standard health, readiness, and startup probes.
- Resource requests/limits set per `AGENTS.md` quality gates.
- Horizontal Pod Autoscaler is safe to enable from day one (no session
  affinity required).
- Graceful shutdown: drain in-flight HTTP requests on SIGTERM.
- Internal service-to-service traffic only until auth is added.

---

## Decision 3 — Tool Surface Design

**Status:** Accepted (2026-04-26)
**Scope:** All MCP servers in this repo. Server-specific tool specs live in
sibling files (e.g. `tasks-server-tools.md`).

### Principle

Tools model **units of user work**, not units of database mutation. Each
tool must accept everything needed to complete its intent in a **single
call**. CRUD-shaped or REST-shaped tool surfaces are explicitly rejected
because they force the agent to chain multiple calls per user request,
burning context and multiplying failure points.

### Rules

1. **Name tools after intents**, not resources or HTTP verbs
   (`capture_task`, not `create_task` or `POST /tasks`).
2. **One call, one intent.** A tool must accept all reasonable inputs for
   its intent so the agent never has to chain a follow-up "and now set
   field X" call to finish the same user request.
3. **Use a shared prefix per server** (`tasks_` for the Tasks server) so
   agents with multiple MCP servers mounted can disambiguate at a glance.
4. **List/review tools return full objects.** No separate `get_*` tool
   exists when the list tool already returns enough data.
5. **Destructive tools are their own tool** with `destructiveHint: true`,
   never folded into a generic update. The agent's confirmation policy
   (per `AGENTS.md`) keys off the tool name.
6. **Lifecycle transitions are their own tool** when they are high-frequency
   or carry distinct semantics (e.g. resolution). The state machine lives on
   the server, not in the agent.
7. **High-level filters over raw predicates.** Surface filters that match
   how users actually ask (`today`, `overdue`, `upcoming`) rather than
   forcing the agent to assemble `status in [...] AND due_before=...`
   queries.
8. **Keep the tool count small.** Fewer, well-shaped tools beat many
   narrow ones — the LLM picks the right tool faster and the surface is
   easier to reason about.

### Why intent-based works here

The intent space for a task manager is small and well-known. The usual
risk of intent-based design — combinatorial explosion of bespoke tools —
does not apply. If the product later grows into territory where an intent
tool starts trying to do too much, split it then; do not preemptively
decompose into primitives.

### What this rules out

- Generic `query_tasks(where={...})` style endpoints.
- Separate `get_*` tools when a list/review tool returns the same data.
- "Upsert" tools that hide whether a create or update happened.
- Batch tools in v1 (partial-failure semantics need their own design).

### See also

- `tasks-server-tools.md` — concrete application of this principle to the
  Tasks MCP server (5 tools).

---

## Decisions Deferred

The following decisions are intentionally postponed and will be added as
separate sections below when taken:

- **Decision 2** — Identity, Auth & Multi-Tenancy *(deferred)*
- **Decision 4** — Idempotency & Concurrency *(deferred)*
- **Decision 5** — Response & Context Discipline *(deferred)*
- **Decision 6** — Observability & Governance *(deferred)*
- **Decision 7** — Versioning & Evolution *(deferred)*
- **Decision 8** — SDK & Runtime *(deferred; default per `AGENTS.md` is
  Python 3.12 + `uv` unless an operational reason argues otherwise)*

---

## History

| Date | Change |
| --- | --- |
| 2026-04-26 | Initial document. Decision 1 accepted. |
| 2026-04-26 | Decision 3 accepted. Tasks server tool spec added in `tasks-server-tools.md`. |
