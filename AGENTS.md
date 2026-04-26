# AGENTS.md

## Project Constitution

This repository builds an AI-native task management system. The system uses agents,
tools, APIs, and a user interface, but this file is not a technical schema or API
reference.

Treat this file as the constitution for how we work: the principles, boundaries,
and operating rules that guide every design and implementation decision.

Detailed contracts belong in code, tests, OpenAPI specs, MCP tool definitions,
database migrations, and Kubernetes manifests.

---

## Product Direction

The product helps users manage tasks, reminders, and appointment-style workflows
through natural conversation.

The Tasks Manager Agent is the primary user-facing orchestrator. Other agents,
tools, and services exist to support that orchestrator, not to bypass it.

The system must remain:

* Clear enough for users to understand what action was taken.
* Reliable enough that task and notification changes are not duplicated.
* Explicit enough that time, date, identity, and destructive actions are never
  guessed.
* Modular enough that agents, tools, APIs, and UI layers can evolve separately.

---

## Agent Boundaries

* The Tasks Manager Agent owns user intent, clarification, routing, and final
  confirmation.
* Task mutations must go through the Tasks MCP server.
* Booking workflows must be routed to the Appointment Booking Agent.
* The Appointment Booking Agent must not mutate tasks directly.
* Notifications are triggered only after a valid task mutation succeeds.
* Destructive actions require user confirmation before execution.
* Missing or ambiguous dates, times, participants, or targets must be clarified
  before action is taken.

Agent behavior should be structured and deterministic, but implementation-level
schemas do not belong in this file.

---

## Engineering Principles

* Work test-first by default. Start with a failing test that captures the
  expected behavior, implement the smallest useful change, then refactor.
* Prefer simple, explicit designs over clever abstractions.
* Keep changes small enough to review and reason about.
* Preserve clear separation between orchestration, tools, APIs, persistence,
  notifications, authentication, and UI.
* Make failures visible and recoverable instead of silent.
* Design every mutation to be idempotent where practical.
* Treat time, timezone, retries, and duplicate requests as first-class product
  concerns.
* Avoid direct database changes from agents or UI code when a service or MCP
  boundary exists.
* Do not introduce a new framework, SDK, queue, database, or runtime dependency
  without a clear operational reason.

---

## Docs-First Development

Before implementing with an SDK, framework, or infrastructure feature, check the
official documentation for the exact version or service being used.

Use the most reliable documentation path available:

* Prefer project-provided MCP documentation tools or installed agent skills when
  available.
* Prefer official vendor documentation over blog posts, examples, or generated
  snippets.
* For OpenAI, MCP, FastAPI, Next.js, Kubernetes, and cloud-provider features,
  verify current behavior against official docs before relying on memory.
* Capture important documentation assumptions in code comments, tests, or PR
  notes when they affect behavior.

Outdated SDK assumptions are treated as bugs.

---

## Development Workflow

Every meaningful change should follow this path:

1. Understand the user-facing behavior and the system boundary involved.
2. Read the existing code before designing the change.
3. Check official docs for any SDK, framework, or platform behavior involved.
4. Write or update tests first when the behavior is testable.
5. Implement the smallest coherent change.
6. Run the relevant tests, type checks, linters, and local service checks.
7. Review the Kubernetes and operational impact before considering the work done.

Tests should cover the behavior users depend on, not only implementation details.
When a bug is fixed, add a regression test unless the cost is clearly unjustified.

---

## Kubernetes From The Start

The final system is expected to run on Kubernetes. Development decisions should
account for that from the beginning rather than treating deployment as an
afterthought.

Services should be designed to support:

* Stateless application containers wherever possible.
* Configuration through environment variables and mounted secrets.
* Health, readiness, and startup probes.
* Graceful shutdown and safe handling of interrupted requests.
* Clear resource requests and limits.
* Horizontal scaling without duplicate task mutations or notifications.
* Idempotent jobs, retries, and scheduled work.
* Structured logs, metrics, traces, and correlation IDs.
* Database migrations that can run safely during deployment.
* Internal service communication through stable service names, not localhost
  assumptions.

Any feature that requires local files, background workers, queues, cron behavior,
or long-running connections must include a deployment-aware design.

---

## Quality Gates

Before completing work, verify the relevant layer:

* Agent behavior: intent parsing, clarification, routing, and confirmations.
* MCP tools: validation, deterministic responses, and idempotency.
* Notifications: scheduling, cancellation, retry behavior, and duplicate
  prevention.
* API layer: authentication, authorization, validation, error handling, and
  observability.
* UI layer: accessible flows, clear states, loading/error handling, and no hidden
  assumptions about backend success.
* Deployment layer: configuration, secrets, probes, resources, scaling, and
  rollback behavior.

If a check cannot be run locally, document what was not verified and why.

---

## Observability

The system must make agent and service behavior inspectable.

Log important decisions and tool calls with correlation IDs. Track task
mutations, booking handoffs, notification scheduling, retries, failures, and user
confirmation boundaries.

Logs must not leak secrets, credentials, tokens, or unnecessary personal data.

---

## Ownership

* Tasks MCP: Backend team.
* Agents: AI/Platform team.
* Notifications: Backend/API team.
* UI and Auth: Frontend team.
* Kubernetes and runtime operations: Platform team, with each service owner
  responsible for deployment readiness.

Cross-boundary changes require coordination with the owning area.

---

## Final Principle

Keep this file minimal, explicit, and operational.

If guidance can be inferred from the codebase, generated from a schema, or
enforced by a test, it usually does not belong here. This file exists for the
working principles that humans and agents must remember while building the
system.
