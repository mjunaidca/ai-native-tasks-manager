import pytest

from tasks_mcp.errors import ErrorCode, ToolError
from tasks_mcp.models import (
    CaptureTaskInput,
    ResolveOutcome,
    ResolveTaskInput,
)
from tasks_mcp.store import TaskStore
from tasks_mcp.tools import capture_task, resolve_task


def test_complete_pending() -> None:
    store = TaskStore()
    t = capture_task(store, CaptureTaskInput(title="x"))
    out = resolve_task(
        store, ResolveTaskInput(id=t.id, outcome=ResolveOutcome.COMPLETED, note="done")
    )
    assert out.status == "completed"
    assert out.note == "done"


def test_idempotent_same_outcome() -> None:
    store = TaskStore()
    t = capture_task(store, CaptureTaskInput(title="x"))
    a = resolve_task(store, ResolveTaskInput(id=t.id, outcome=ResolveOutcome.COMPLETED))
    b = resolve_task(store, ResolveTaskInput(id=t.id, outcome=ResolveOutcome.COMPLETED))
    assert a.status == b.status == "completed"
    assert a.updated_at == b.updated_at  # second call is a true no-op


def test_conflict_completed_then_cancelled() -> None:
    store = TaskStore()
    t = capture_task(store, CaptureTaskInput(title="x"))
    resolve_task(store, ResolveTaskInput(id=t.id, outcome=ResolveOutcome.COMPLETED))
    with pytest.raises(ToolError) as e:
        resolve_task(store, ResolveTaskInput(id=t.id, outcome=ResolveOutcome.CANCELLED))
    assert e.value.code is ErrorCode.INVALID_STATE_TRANSITION
    assert e.value.suggestion is not None


def test_resolve_not_found() -> None:
    with pytest.raises(ToolError) as e:
        resolve_task(
            TaskStore(),
            ResolveTaskInput(id="missing", outcome=ResolveOutcome.COMPLETED),
        )
    assert e.value.code is ErrorCode.NOT_FOUND
