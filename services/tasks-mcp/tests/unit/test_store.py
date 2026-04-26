from tasks_mcp.models import Task, TaskStatus
from tasks_mcp.store import TaskStore


def make_task(id: str = "t1", user: str = "u") -> Task:
    return Task(
        id=id,
        user_id=user,
        title="x",
        description=None,
        status=TaskStatus.PENDING,
        due_at=None,
        note=None,
        created_at="2026-04-27T00:00:00Z",
        updated_at="2026-04-27T00:00:00Z",
    )


def test_add_and_get_scoped() -> None:
    s = TaskStore()
    s.add(make_task("a", "alice"))
    assert s.get_for_user("a", "alice") is not None
    assert s.get_for_user("a", "bob") is None


def test_delete_cross_user_silent() -> None:
    s = TaskStore()
    s.add(make_task("a", "alice"))
    assert s.delete("a", "bob") is False
    assert s.get_for_user("a", "alice") is not None


def test_delete_owner() -> None:
    s = TaskStore()
    s.add(make_task("a", "alice"))
    assert s.delete("a", "alice") is True
    assert s.get_for_user("a", "alice") is None


def test_delete_missing() -> None:
    assert TaskStore().delete("x", "u") is False


def test_list_per_user() -> None:
    s = TaskStore()
    s.add(make_task("a", "alice"))
    s.add(make_task("b", "alice"))
    s.add(make_task("c", "bob"))
    assert {t.id for t in s.list_for_user("alice")} == {"a", "b"}
    assert {t.id for t in s.list_for_user("bob")} == {"c"}
