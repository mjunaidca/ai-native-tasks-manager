import pytest

from tasks_mcp.errors import ErrorCode, ToolError
from tasks_mcp.models import CaptureTaskInput, ModifyTaskInput
from tasks_mcp.store import TaskStore
from tasks_mcp.tools import capture_task, modify_task


def test_modify_title() -> None:
    store = TaskStore()
    t = capture_task(store, CaptureTaskInput(title="old", description="d"))
    out = modify_task(store, ModifyTaskInput(id=t.id, title="new"))
    assert out.title == "new"
    assert out.description == "d"


def test_modify_clears_description_with_explicit_null() -> None:
    store = TaskStore()
    t = capture_task(store, CaptureTaskInput(title="t", description="keep"))
    out = modify_task(store, ModifyTaskInput(id=t.id, description=None))
    assert out.description is None


def test_modify_no_fields_provided() -> None:
    store = TaskStore()
    t = capture_task(store, CaptureTaskInput(title="t"))
    with pytest.raises(ToolError) as e:
        modify_task(store, ModifyTaskInput(id=t.id))
    assert e.value.code is ErrorCode.INVALID_ARGUMENT


def test_modify_not_found() -> None:
    with pytest.raises(ToolError) as e:
        modify_task(TaskStore(), ModifyTaskInput(id="missing", title="x"))
    assert e.value.code is ErrorCode.NOT_FOUND


def test_modify_cross_user_returns_not_found() -> None:
    store = TaskStore()
    t = capture_task(store, CaptureTaskInput(title="x", user_id="alice"))
    with pytest.raises(ToolError) as e:
        modify_task(store, ModifyTaskInput(id=t.id, title="y"))  # default-user
    assert e.value.code is ErrorCode.NOT_FOUND
