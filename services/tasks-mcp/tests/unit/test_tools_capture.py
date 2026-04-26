import pytest

from tasks_mcp.errors import ErrorCode, ToolError
from tasks_mcp.models import CaptureTaskInput
from tasks_mcp.store import TaskStore
from tasks_mcp.tools import capture_task


def test_capture_minimal_defaults_user_and_status() -> None:
    store = TaskStore()
    t = capture_task(store, CaptureTaskInput(title="Buy milk"))
    assert t.user_id == "default-user"
    assert t.status == "pending"
    assert t.due_at is None
    assert t.id and t.created_at and t.updated_at == t.created_at


def test_capture_with_user_and_due_at() -> None:
    store = TaskStore()
    t = capture_task(
        store,
        CaptureTaskInput(
            title="Lunch",
            due_at="2026-04-27T17:00:00Z",
            description="with team",
            user_id="alice",
        ),
    )
    assert t.user_id == "alice"
    assert t.due_at == "2026-04-27T17:00:00Z"
    assert t.description == "with team"


def test_capture_rejects_naive_due_at_at_pydantic_layer() -> None:
    # The pattern in CaptureTaskInput rejects naive strings before reaching tool.
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CaptureTaskInput(title="t", due_at="2026-04-27T17:00:00")


def test_capture_rejects_non_z_offset_via_tool() -> None:
    # Bypass model validation to verify defense-in-depth in the tool.
    from tasks_mcp.models import CaptureTaskInput as CTI

    bad = CTI.model_construct(title="t", due_at="2026-04-27T17:00:00+00:00")
    with pytest.raises(ToolError) as excinfo:
        capture_task(TaskStore(), bad)
    assert excinfo.value.code is ErrorCode.INVALID_ARGUMENT
