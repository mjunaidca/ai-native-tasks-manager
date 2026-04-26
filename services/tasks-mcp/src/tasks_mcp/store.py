from threading import Lock

from tasks_mcp.models import Task


class TaskStore:
    """In-memory task store with per-user scoping. Single-replica only."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = Lock()

    def add(self, task: Task) -> Task:
        with self._lock:
            self._tasks[task.id] = task
            return task

    def get_for_user(self, task_id: str, user_id: str) -> Task | None:
        with self._lock:
            t = self._tasks.get(task_id)
            if t is None or t.user_id != user_id:
                return None
            return t

    def replace(self, task: Task) -> Task:
        with self._lock:
            self._tasks[task.id] = task
            return task

    def delete(self, task_id: str, user_id: str) -> bool:
        """Remove a task. Returns True if a task was actually removed.

        Cross-user deletes are silent: returns False, leaving the task in place.
        """
        with self._lock:
            t = self._tasks.get(task_id)
            if t is None:
                return False
            if t.user_id != user_id:
                return False
            del self._tasks[task_id]
            return True

    def list_for_user(self, user_id: str) -> list[Task]:
        with self._lock:
            return [t for t in self._tasks.values() if t.user_id == user_id]

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()
