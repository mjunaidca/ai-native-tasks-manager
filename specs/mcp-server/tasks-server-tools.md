# Tasks MCP Server — Tool Specification (v1)

This document specifies the tool surface of the Tasks MCP server. It assumes
the cross-cutting choices in `decisions.md` (Streamable HTTP, stateless JSON,
no auth, in-memory storage, intent-based tool design).

The server exposes **five tools**, each modeled after a unit of user work,
not a database operation. Every tool is designed to complete its intent in a
**single call**.

---

## Task Resource

The canonical Task object returned by every tool that returns a task:

```jsonc
{
  "id":          "string",          // server-generated, ULID
  "user_id":     "string",          // owner; "default-user" if unspecified at creation
  "title":       "string",          // 1..200 chars
  "description": "string | null",   // 0..4000 chars
  "status":      "pending | completed | cancelled",
  "due_at":      "string | null",   // ISO-8601 in UTC, e.g. "2026-04-27T17:00:00Z"
  "note":        "string | null",   // last resolution note, if any
  "created_at":  "string",          // ISO-8601 UTC
  "updated_at":  "string"           // ISO-8601 UTC
}
```

### Field rules

- `id` — server-assigned. Clients never set it.
- `title` — required, trimmed, must be non-empty after trim.
- `due_at` — if provided, MUST be ISO-8601 in **UTC** with the `Z` suffix
  (e.g. `2026-04-27T17:00:00Z`). Datetimes with non-UTC offsets or no
  timezone at all are rejected with `invalid_argument`. Callers convert
  local time to UTC before sending. The server never guesses timezone.
- All other timestamps (`created_at`, `updated_at`) are also UTC with the
  `Z` suffix.
- `status` — server-managed. Clients change it via `resolve_task`, never via
  `modify_task`.
- `note` — set by `resolve_task`; preserved on the task for audit.
- `user_id` — owner of the task. Set at creation from the `user_id` input
  on `capture_task`, or to the constant `"default-user"` if omitted. Tasks
  are immutably owned by their creator in v1 (no transfer).

---

## User Identity (v1)

There is no auth in v1 (per Decision 1), but every tool accepts an optional
`user_id` parameter so the server can scope tasks per user from day one.
This avoids a painful retrofit when real identity arrives (Decision 2).

Rules:

- Every tool accepts an optional `user_id: string` input.
- If `user_id` is omitted, the server uses the constant `"default-user"`.
  This is the **mock identity** for development and unauthenticated calls.
- All read tools (`review_tasks`) only return tasks owned by the supplied
  (or default) `user_id`.
- All tools that take an `id` (`modify_task`, `resolve_task`,
  `remove_task`) verify that the target task's `user_id` matches the
  supplied (or default) `user_id`. A mismatch returns `not_found` — the
  server does **not** disclose the existence of tasks owned by other users.
- `user_id` format in v1: any non-empty string up to 128 chars. The server
  does not validate it against any registry.

When real auth lands, `user_id` will be derived from the authenticated
principal and the input parameter will be ignored (or rejected).

---

## Tools

### 1. `capture_task`

Create a new task in one call, with all known details.

**Annotations:** `readOnlyHint: false`, `destructiveHint: false`,
`idempotentHint: false` *(becomes idempotent once Decision 4 lands)*.

**Input:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | string | yes | 1..200 chars |
| `due_at` | string (ISO-8601 UTC) | no | Must be UTC with `Z` suffix |
| `description` | string | no | 0..4000 chars |
| `user_id` | string | no | Owner. Defaults to `"default-user"` (see *User Identity*). |

**Output:** the created `Task`.

**Errors:** `invalid_argument` (missing title, naive datetime, length
violations).

---

### 2. `review_tasks`

Return tasks the user wants to look at, using high-level filters that match
how people actually ask. Returns full `Task` objects so no follow-up fetch is
needed.

**Annotations:** `readOnlyHint: true`, `idempotentHint: true`.

**Input:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `filter` | enum | yes | `today` \| `overdue` \| `upcoming` \| `open` \| `all` |
| `query` | string | no | Free-text match against title + description (case-insensitive substring in v1) |
| `limit` | integer | no | Default 50, max 200 |
| `cursor` | string | no | Opaque pagination cursor returned by a prior call |
| `user_id` | string | no | Scope of the review. Defaults to `"default-user"`. |
| `tz` | string (IANA) | no | Timezone used to resolve "today" / "overdue" / "upcoming" calendar boundaries. Stored data is UTC; this is only for filter evaluation. Defaults to `UTC`. |

**Filter semantics** (server-evaluated, in the user's timezone — see
*Open question* below):

- `today` — `due_at` falls within the current calendar day, status is `pending`.
- `overdue` — `due_at` is in the past, status is `pending`.
- `upcoming` — `due_at` is in the future, status is `pending`.
- `open` — status is `pending`, regardless of `due_at`.
- `all` — every task, any status.

**Sort order:** `due_at` ascending, nulls last, then `created_at` ascending.

**Output:**

```jsonc
{
  "items":       [Task, ...],
  "next_cursor": "string | null"
}
```

**Errors:** `invalid_argument` (unknown filter, limit out of range, malformed
cursor).

---

### 3. `modify_task`

Edit the editable fields of an existing task in one call. Status is **not**
editable here — use `resolve_task`.

**Annotations:** `readOnlyHint: false`, `destructiveHint: false`,
`idempotentHint: true`.

**Input:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | |
| `title` | string | no | If present, replaces existing |
| `description` | string \| null | no | `null` clears it |
| `due_at` | string \| null | no | `null` clears it; otherwise must be UTC with `Z` suffix |
| `user_id` | string | no | Must match the task's owner. Defaults to `"default-user"`. |

At least one of `title`, `description`, `due_at` must be present.

**Output:** the updated `Task`.

**Errors:** `not_found`, `invalid_argument` (no fields provided, naive
datetime, length violations).

---

### 4. `resolve_task`

End a task's lifecycle by marking it completed or cancelled, optionally with
a short note explaining why.

**Annotations:** `readOnlyHint: false`, `destructiveHint: false`,
`idempotentHint: true`.

**Input:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | |
| `outcome` | enum | yes | `completed` \| `cancelled` |
| `note` | string | no | 0..500 chars; stored on the task |
| `user_id` | string | no | Must match the task's owner. Defaults to `"default-user"`. |

**Behavior:**

- Allowed transitions: `pending → completed`, `pending → cancelled`.
- Calling `resolve_task` on an already-resolved task with the **same outcome**
  is a no-op success (idempotent).
- Calling with a **different outcome** returns `invalid_state_transition`
  with a suggestion to call `reopen` first. *(Reopen is intentionally not in
  v1 — see Deferred below.)*

**Output:** the updated `Task`.

**Errors:** `not_found`, `invalid_state_transition`, `invalid_argument`.

---

### 5. `remove_task`

Hard-delete a task. Destructive — the agent layer is responsible for getting
explicit user confirmation before calling this (per `AGENTS.md`).

**Annotations:** `readOnlyHint: false`, `destructiveHint: true`,
`idempotentHint: true`.

**Input:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | |
| `user_id` | string | no | Must match the task's owner. Defaults to `"default-user"`. |

**Output:**

```jsonc
{ "id": "string", "removed": true }
```

**Behavior:**

- Removing an already-removed id returns `{ id, removed: true }` (idempotent
  success), not `not_found`. This avoids spurious errors when the agent
  retries.

**Errors:** none under normal operation. Unexpected internal failures return
the standard error envelope.

---

## Error Envelope

All tools return errors in a single shape:

```jsonc
{
  "error": {
    "code":       "not_found | invalid_argument | invalid_state_transition | internal",
    "message":    "human-readable description",
    "suggestion": "string | null"   // optional, actionable next step for the agent
  }
}
```

Example:

```jsonc
{
  "error": {
    "code": "invalid_state_transition",
    "message": "Task is already 'completed' and cannot be 'cancelled'.",
    "suggestion": "Reopen the task first, then cancel it."
  }
}
```

---

## Storage (v1)

- A single in-process `dict[id, Task]` guarded by a lock.
- **Single replica only.** State is lost on pod restart and not shared
  across pods. The Kubernetes Deployment must run with `replicas: 1` and
  `strategy: Recreate` until persistence is added.
- Documented as a known constraint in `decisions.md`.

---

## Open Questions

These are not blocking v1 implementation but should be resolved before
release:

1. **User timezone source.** `review_tasks` accepts an optional `tz`
   parameter (defaults to `UTC`). Once real identity lands (Decision 2),
   we may want to store a per-user default timezone on a user profile and
   fall back to that when `tz` is omitted.
2. **Reopen.** Intentionally omitted from v1 to keep the state machine
   minimal. Add a `reopen_task` tool (or extend `resolve_task` with an
   `outcome: pending`) when a real use case appears.
3. **Batch operations.** Out of scope for v1. Batch invites partial-failure
   semantics that need their own design.

---

## Deferred (explicitly not in v1)

- Recurring tasks, sub-tasks, dependencies.
- Tags, priority, assignees, sharing.
- Reminders/notifications (separate system per `AGENTS.md`).
- Idempotency keys on `capture_task` (Decision 4).
- Authentication and authorization (Decision 2). v1 scaffolds an optional
  `user_id` parameter with a `"default-user"` fallback so per-user scoping
  works today, but there is no verification that the caller is who they
  claim to be.
