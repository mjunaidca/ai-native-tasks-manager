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

## Tech Stack Defaults

These are the defaults for any new service, agent, or tool in this repo.
Deviating requires a clear operational reason.

* **Preferred programming language:** Python 3.12+.
* **Package and environment manager:** [`uv`](https://docs.astral.sh/uv/).
  Use `uv` for dependency resolution, virtual environments, lockfiles, and
  running scripts. Do not mix `pip`, `poetry`, or `conda` into the same
  service unless there is a documented reason.

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

## Deployment Conventions

* **Container image registry:** GitHub Container Registry (`ghcr.io`). Images
  are public for now because the repository is public.
* **Kubernetes manifests and Helm charts:** live under `deployments/` at the
  repository root. Do not scatter manifests or charts inside individual service
  directories.
* **Dockerfiles:** live at the root of each service or project directory. For
  example, the Tasks MCP server's Dockerfile is `services/tasks-mcp/Dockerfile`.

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

## Always Verify

Verification is not a final step — it is part of doing the work.

* Always verify what you are doing. Before declaring something done, prove it
  works: run the test, hit the endpoint, read the file back, check the log,
  inspect the diff.
* Trust nothing by default — not your own memory, not a plausible-looking
  output, not "it should work." Confirm against the real system.
* When you change behavior, verify both the happy path and at least one
  failure or edge case.
* If you cannot verify something locally, say so explicitly instead of
  implying success.
* Treat unverified claims the same as bugs.

---

## Working Practices for Agents and Humans

These practices are adapted from the Panaversity Agent Factory creator
workflow and apply to anyone — human or AI — building in this repo.

### Plan before executing

* For any non-trivial change, produce a written plan first. Iterate on the
  plan until it is solid before touching code.
* When execution starts going wrong, stop and re-plan instead of pushing
  through.
* Invite "poke holes in this plan" style review before committing to an
  approach. A second pass with fresh eyes catches blind spots the original
  author missed.

### Manage context as a scarce resource

* Treat the context window as the limiting resource. Keep sessions focused
  on one task at a time.
* Reset context between unrelated tasks rather than letting one session
  accumulate noise.
* Delegate bounded investigations (large searches, repo-wide audits) to
  subagents so the main context stays clean.
* If a task is going in circles after two failed corrections, stop and
  restart with a clearer prompt rather than spiraling.

### Use parallel workstreams

* Use git worktrees or separate directories when working on independent
  changes in parallel, so contexts do not bleed into each other.
* Keep each workstream's history isolated and recoverable.

### Reduce ambiguity in prompts and briefs

* Give the problem, the constraints, the audience, and the success criteria
  — not a pre-baked solution.
* Prefer detailed briefs over terse one-liners for anything non-trivial.
* Ask clarifying questions when intent is ambiguous; do not guess.

### Build verification loops

* Give agents tools to check their own work: tests, type checks, linters,
  health checks, MCP tools, hooks, or browser automation as appropriate.
* Prefer automated checks over manual inspection where possible.
* Use a Claude-reviews-Claude (or human-reviews-agent) pattern for important
  changes: a fresh reviewer is better than the original author at catching
  blind spots.

### Treat documentation as living infrastructure

* When a mistake is discovered, update this file (or the relevant doc) so it
  is not repeated. Lessons learned become permanent institutional memory.
* Prune ruthlessly. Delete rules the codebase already enforces. Keep this
  file lean enough that people actually read it.
* Capture important assumptions about SDKs, frameworks, or platforms in
  code comments, tests, or PR notes when they affect behavior.

### Automate repeated workflows

* If a workflow is done more than once, turn it into a script, hook, skill,
  or CI check.
* Pre-allow safe commands (builds, tests, type checks, formatters) in
  project settings rather than skipping safety checks.
* Use post-write hooks for formatting and lint fixes so they are never
  forgotten.

### Choose models and tools deliberately

* Prefer the more capable model with thinking enabled when correctness
  matters. A correct slow answer beats a wrong fast answer that needs
  rework.
* Keep a portable, version-controlled set of skills, settings, and hooks so
  the team shares the same working environment.

### Avoid common pitfalls

* **Kitchen-sink sessions**: do not pile unrelated questions into one
  context. Reset between tasks.
* **Correction spirals**: more than two failed corrections means the
  approach is muddled — stop and re-plan.
* **Bloated docs**: do not add a rule that the code, a test, or a schema
  already enforces.
* **Trust-then-verify gap**: plausible output is not verified output. Edge
  cases are not optional.
* **Infinite exploration**: scope investigations narrowly or delegate them.

---

## Final Principle

Keep this file minimal, explicit, and operational.

If guidance can be inferred from the codebase, generated from a schema, or
enforced by a test, it usually does not belong here. This file exists for the
working principles that humans and agents must remember while building the
system.
