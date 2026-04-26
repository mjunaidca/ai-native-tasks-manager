import base64
import json
from datetime import datetime, timezone

from ulid import ULID

from tasks_mcp.errors import ErrorCode, ToolError
from tasks_mcp.models import (
    DEFAULT_USER,
    CaptureTaskInput,
    ModifyTaskInput,
    RemoveTaskInput,
    RemoveTaskOutput,
    ResolveOutcome,
    ResolveTaskInput,
    ReviewFilter,
    ReviewTasksInput,
    ReviewTasksOutput,
    Task,
    TaskStatus,
)
from tasks_mcp.store import TaskStore
from tasks_mcp.time_utils import day_bounds_utc, format_utc, now_utc, parse_utc_iso


def _user(user_id: str | None) -> str:
    return user_id if user_id else DEFAULT_USER


def _validate_due_at(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parse_utc_iso(value)
    except ValueError as e:
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            str(e),
            "Convert local time to UTC and send as e.g. '2026-04-27T17:00:00Z'.",
        ) from e
    return value


def capture_task(store: TaskStore, params: CaptureTaskInput) -> Task:
    due_at = _validate_due_at(params.due_at)
    now_str = format_utc(now_utc())
    task = Task(
        id=str(ULID()),
        user_id=_user(params.user_id),
        title=params.title,
        description=params.description,
        status=TaskStatus.PENDING,
        due_at=due_at,
        note=None,
        created_at=now_str,
        updated_at=now_str,
    )
    return store.add(task)


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"o": offset}).encode()).decode()


def _decode_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        offset = int(data["o"])
        if offset < 0:
            raise ValueError
        return offset
    except Exception as e:
        raise ToolError(ErrorCode.INVALID_ARGUMENT, "Malformed cursor.") from e


def _matches_filter(
    task: Task,
    filter_: ReviewFilter,
    now: datetime,
    tz: str,
) -> bool:
    if filter_ is ReviewFilter.ALL:
        return True
    if filter_ is ReviewFilter.OPEN:
        return task.status == TaskStatus.PENDING.value
    if task.status != TaskStatus.PENDING.value:
        return False
    if filter_ is ReviewFilter.OVERDUE:
        if not task.due_at:
            return False
        return parse_utc_iso(task.due_at) < now
    if filter_ is ReviewFilter.UPCOMING:
        if not task.due_at:
            return False
        return parse_utc_iso(task.due_at) > now
    if filter_ is ReviewFilter.TODAY:
        if not task.due_at:
            return False
        start, end = day_bounds_utc(now, tz)
        due = parse_utc_iso(task.due_at)
        return start <= due < end
    return False


def _matches_query(task: Task, query: str) -> bool:
    needle = query.lower()
    haystack = (task.title or "").lower()
    if task.description:
        haystack += "\n" + task.description.lower()
    return needle in haystack


def _sort_key(t: Task) -> tuple[int, str, str]:
    # due_at asc, nulls last, then created_at asc
    return (1 if t.due_at is None else 0, t.due_at or "", t.created_at)


def review_tasks(store: TaskStore, params: ReviewTasksInput) -> ReviewTasksOutput:
    user = _user(params.user_id)
    try:
        # Pre-validate tz so we fail fast even for filters that don't use it.
        if params.filter is ReviewFilter.TODAY:
            day_bounds_utc(now_utc(), params.tz)
    except ValueError as e:
        raise ToolError(ErrorCode.INVALID_ARGUMENT, str(e)) from e

    now = datetime.now(timezone.utc)
    candidates = [
        t
        for t in store.list_for_user(user)
        if _matches_filter(t, params.filter, now, params.tz)
        and (params.query is None or _matches_query(t, params.query))
    ]
    candidates.sort(key=_sort_key)

    offset = _decode_cursor(params.cursor)
    page = candidates[offset : offset + params.limit]
    next_cursor = (
        _encode_cursor(offset + params.limit)
        if offset + params.limit < len(candidates)
        else None
    )
    return ReviewTasksOutput(items=page, next_cursor=next_cursor)


def modify_task(store: TaskStore, params: ModifyTaskInput) -> Task:
    user = _user(params.user_id)
    if params.title is None and not params.description_set and not params.due_at_set:
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            "At least one of title, description, due_at must be provided.",
        )
    task = store.get_for_user(params.id, user)
    if task is None:
        raise ToolError(ErrorCode.NOT_FOUND, f"Task {params.id!r} not found.")

    new_title = params.title if params.title is not None else task.title
    new_desc = params.description if params.description_set else task.description
    new_due = _validate_due_at(params.due_at) if params.due_at_set else task.due_at

    updated = task.model_copy(
        update={
            "title": new_title,
            "description": new_desc,
            "due_at": new_due,
            "updated_at": format_utc(now_utc()),
        }
    )
    return store.replace(updated)


def resolve_task(store: TaskStore, params: ResolveTaskInput) -> Task:
    user = _user(params.user_id)
    task = store.get_for_user(params.id, user)
    if task is None:
        raise ToolError(ErrorCode.NOT_FOUND, f"Task {params.id!r} not found.")

    target_status = (
        TaskStatus.COMPLETED
        if params.outcome is ResolveOutcome.COMPLETED
        else TaskStatus.CANCELLED
    )

    if task.status == target_status.value:
        # Idempotent same-outcome no-op (keep existing note/timestamps).
        return task

    if task.status != TaskStatus.PENDING.value:
        raise ToolError(
            ErrorCode.INVALID_STATE_TRANSITION,
            f"Task is already {task.status!r} and cannot be {target_status.value!r}.",
            "Reopen the task first, then change its outcome.",
        )

    updated = task.model_copy(
        update={
            "status": target_status,
            "note": params.note if params.note is not None else task.note,
            "updated_at": format_utc(now_utc()),
        }
    )
    return store.replace(updated)


def remove_task(store: TaskStore, params: RemoveTaskInput) -> RemoveTaskOutput:
    user = _user(params.user_id)
    store.delete(params.id, user)
    # Idempotent success: report removed=true regardless of prior existence.
    return RemoveTaskOutput(id=params.id)
