import pytest
from pydantic import ValidationError

from tasks_mcp.models import (
    CaptureTaskInput,
    ModifyTaskInput,
    ReviewTasksInput,
)


class TestCaptureTaskInput:
    def test_minimal_valid(self) -> None:
        m = CaptureTaskInput(title="Buy milk")
        assert m.title == "Buy milk"
        assert m.user_id is None

    def test_strips_whitespace_and_rejects_blank(self) -> None:
        with pytest.raises(ValidationError):
            CaptureTaskInput(title="   ")

    def test_rejects_overlong_title(self) -> None:
        with pytest.raises(ValidationError):
            CaptureTaskInput(title="x" * 201)

    def test_rejects_naive_due_at(self) -> None:
        # Pattern enforces trailing Z; naive datetime string is rejected here.
        with pytest.raises(ValidationError):
            CaptureTaskInput(title="t", due_at="2026-04-27T17:00:00")

    def test_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError):
            CaptureTaskInput(title="t", foo="bar")  # type: ignore[call-arg]


class TestReviewTasksInput:
    def test_default_limit_and_tz(self) -> None:
        m = ReviewTasksInput(filter="open")  # type: ignore[arg-type]
        assert m.limit == 50
        assert m.tz == "UTC"

    def test_limit_bounds(self) -> None:
        with pytest.raises(ValidationError):
            ReviewTasksInput(filter="open", limit=0)  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            ReviewTasksInput(filter="open", limit=201)  # type: ignore[arg-type]

    def test_unknown_filter(self) -> None:
        with pytest.raises(ValidationError):
            ReviewTasksInput(filter="weird")  # type: ignore[arg-type]


class TestModifyTaskInput:
    def test_tracks_explicit_null(self) -> None:
        m = ModifyTaskInput(id="x", description=None)
        assert m.description_set is True
        assert m.due_at_set is False

    def test_omitted_field_not_set(self) -> None:
        m = ModifyTaskInput(id="x", title="new")
        assert m.description_set is False
        assert m.due_at_set is False
