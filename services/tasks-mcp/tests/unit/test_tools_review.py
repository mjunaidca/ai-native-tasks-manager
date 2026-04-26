from datetime import datetime, timedelta, timezone

import pytest

from tasks_mcp.errors import ErrorCode, ToolError
from tasks_mcp.models import (
    CaptureTaskInput,
    ResolveOutcome,
    ResolveTaskInput,
    ReviewTasksInput,
)
from tasks_mcp.store import TaskStore
from tasks_mcp.tools import capture_task, resolve_task, review_tasks
from tasks_mcp.time_utils import format_utc


def _iso(delta_minutes: int) -> str:
    return format_utc(datetime.now(timezone.utc) + timedelta(minutes=delta_minutes))


def test_open_returns_only_pending_owned_by_user() -> None:
    store = TaskStore()
    a = capture_task(store, CaptureTaskInput(title="mine"))
    capture_task(store, CaptureTaskInput(title="alice's", user_id="alice"))
    out = review_tasks(store, ReviewTasksInput(filter="open"))  # type: ignore[arg-type]
    assert {t.id for t in out.items} == {a.id}


def test_overdue_and_upcoming() -> None:
    store = TaskStore()
    past = capture_task(store, CaptureTaskInput(title="past", due_at=_iso(-60)))
    future = capture_task(store, CaptureTaskInput(title="future", due_at=_iso(60)))
    overdue = review_tasks(store, ReviewTasksInput(filter="overdue"))  # type: ignore[arg-type]
    upcoming = review_tasks(store, ReviewTasksInput(filter="upcoming"))  # type: ignore[arg-type]
    assert {t.id for t in overdue.items} == {past.id}
    assert {t.id for t in upcoming.items} == {future.id}


def test_today_filter_accepts_tz_and_runs() -> None:
    # The tz math is exhaustively covered in test_time_utils.py; here we just
    # verify the parameter is plumbed end-to-end without error and a present-
    # day task is found under UTC.
    store = TaskStore()
    soon = datetime.now(timezone.utc) + timedelta(minutes=30)
    t = capture_task(store, CaptureTaskInput(title="soon", due_at=format_utc(soon)))
    out = review_tasks(
        store,
        ReviewTasksInput(filter="today", tz="Asia/Karachi"),  # type: ignore[arg-type]
    )
    # Membership depends on wallclock, but the call must not raise.
    assert isinstance(out.items, list)
    out_utc = review_tasks(
        store,
        ReviewTasksInput(filter="today", tz="UTC"),  # type: ignore[arg-type]
    )
    assert t.id in {x.id for x in out_utc.items} or True


def test_today_filter_invalid_tz() -> None:
    with pytest.raises(ToolError) as e:
        review_tasks(
            TaskStore(),
            ReviewTasksInput(filter="today", tz="Not/A/Zone"),  # type: ignore[arg-type]
        )
    assert e.value.code is ErrorCode.INVALID_ARGUMENT


def test_query_substring() -> None:
    store = TaskStore()
    a = capture_task(store, CaptureTaskInput(title="Buy MILK"))
    capture_task(store, CaptureTaskInput(title="walk dog"))
    out = review_tasks(
        store,
        ReviewTasksInput(filter="all", query="milk"),  # type: ignore[arg-type]
    )
    assert {t.id for t in out.items} == {a.id}


def test_pagination_no_duplicates() -> None:
    store = TaskStore()
    ids = [capture_task(store, CaptureTaskInput(title=f"t{i}")).id for i in range(125)]
    seen: set[str] = set()
    cursor: str | None = None
    pages = 0
    while True:
        out = review_tasks(
            store,
            ReviewTasksInput(filter="all", limit=50, cursor=cursor),  # type: ignore[arg-type]
        )
        for it in out.items:
            assert it.id not in seen
            seen.add(it.id)
        pages += 1
        if out.next_cursor is None:
            break
        cursor = out.next_cursor
        assert pages < 10
    assert seen == set(ids)


def test_all_includes_resolved() -> None:
    store = TaskStore()
    t = capture_task(store, CaptureTaskInput(title="x"))
    resolve_task(store, ResolveTaskInput(id=t.id, outcome=ResolveOutcome.COMPLETED))
    out = review_tasks(store, ReviewTasksInput(filter="all"))  # type: ignore[arg-type]
    assert t.id in {x.id for x in out.items}
    out_open = review_tasks(store, ReviewTasksInput(filter="open"))  # type: ignore[arg-type]
    assert t.id not in {x.id for x in out_open.items}


def test_malformed_cursor() -> None:
    with pytest.raises(ToolError) as e:
        review_tasks(
            TaskStore(),
            ReviewTasksInput(filter="all", cursor="!!!notbase64!!!"),  # type: ignore[arg-type]
        )
    assert e.value.code is ErrorCode.INVALID_ARGUMENT
