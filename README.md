# AI-Native Tasks Manager

A multi-agent task management system where you talk to an assistant in plain
language and it handles your tasks, reminders, and appointment-style workflows
for you.

This repo is the working space for the project. The detailed operating rules
for agents and contributors live in [AGENTS.md](./AGENTS.md) — start there if
you want to understand how the system is meant to behave.

---

## What it does

You tell the system things like:

- "Remind me to renew my passport next Tuesday at 6pm."
- "Mark the dentist task as done."
- "Book a meeting with Sara on Friday afternoon."

Behind the scenes a small team of agents and services coordinates to:

- Understand what you actually want.
- Ask a clarifying question if something important is missing (like a date).
- Create, update, or delete the task through a controlled tool boundary.
- Schedule reminders or notifications when needed.
- Hand off booking-style requests to a dedicated booking agent.
- Confirm back to you in plain language.

---

## How it is organized

The system is split into clear layers so each piece can evolve on its own:

- **Tasks Manager Agent** — the user-facing orchestrator. Owns intent,
  clarification, routing, and final confirmation.
- **Tasks MCP server** — the only path for creating, updating, or deleting
  tasks.
- **Notifications API** — schedules and sends reminders after a task change
  succeeds.
- **Appointment Booking Agent** — handles "book / schedule / reserve" style
  requests without touching tasks directly.
- **UI and Auth** — how humans actually sign in and interact with the system.

Agents do not bypass each other, and nothing writes to the database outside the
MCP boundary. This is intentional and is described in
[AGENTS.md](./AGENTS.md).

---

## Principles we follow

A few rules shape almost every decision in this repo:

- **Be explicit, not clever.** Time, date, identity, and destructive actions
  are never guessed.
- **Confirm before destroying.** Deletes and updates require user
  confirmation.
- **Test-first when behavior is testable.** Bugs come back with a regression
  test.
- **Docs-first for SDKs and platforms.** Verify against official docs before
  trusting memory.
- **Kubernetes-aware from day one.** Services are designed to run as stateless,
  observable, idempotent containers — not as local scripts.
- **Make failures visible.** Logs, correlation IDs, and clear error states
  beat silent retries.

The full list lives in [AGENTS.md](./AGENTS.md).

---

## Status

Early-stage. The constitution and agent boundaries are in place; individual
services (MCP server, notifications API, booking agent, UI) are being built
out against those boundaries.

---

## Contributing

If you are a human contributor:

1. Read [AGENTS.md](./AGENTS.md) first — it explains the boundaries you are
   expected to respect.
2. Keep changes small and reviewable.
3. Add or update tests for behavior users depend on.
4. When in doubt, prefer the explicit, boring option.

If you are an AI agent working in this repo, the same rules apply to you.
