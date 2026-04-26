from tasks_mcp.models import CaptureTaskInput, RemoveTaskInput
from tasks_mcp.store import TaskStore
from tasks_mcp.tools import capture_task, remove_task


def test_remove_existing() -> None:
    store = TaskStore()
    t = capture_task(store, CaptureTaskInput(title="x"))
    out = remove_task(store, RemoveTaskInput(id=t.id))
    assert out.removed is True
    assert out.id == t.id
    assert store.get_for_user(t.id, "default-user") is None


def test_remove_idempotent() -> None:
    store = TaskStore()
    t = capture_task(store, CaptureTaskInput(title="x"))
    remove_task(store, RemoveTaskInput(id=t.id))
    out = remove_task(store, RemoveTaskInput(id=t.id))
    assert out.removed is True


def test_remove_cross_user_silent() -> None:
    store = TaskStore()
    t = capture_task(store, CaptureTaskInput(title="x", user_id="alice"))
    out = remove_task(store, RemoveTaskInput(id=t.id))  # default-user
    assert out.removed is True  # idempotent contract: never reveal existence
    # But the task is still there for alice.
    assert store.get_for_user(t.id, "alice") is not None
