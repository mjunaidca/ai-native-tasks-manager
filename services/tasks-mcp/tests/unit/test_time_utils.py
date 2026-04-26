from datetime import datetime, timezone

import pytest

from tasks_mcp.time_utils import (
    day_bounds_utc,
    format_utc,
    parse_utc_iso,
)


class TestParseUtcIso:
    def test_accepts_z_suffix(self) -> None:
        dt = parse_utc_iso("2026-04-27T17:00:00Z")
        assert dt == datetime(2026, 4, 27, 17, 0, 0, tzinfo=timezone.utc)

    def test_rejects_naive(self) -> None:
        with pytest.raises(ValueError):
            parse_utc_iso("2026-04-27T17:00:00")

    def test_rejects_non_utc_offset(self) -> None:
        with pytest.raises(ValueError):
            parse_utc_iso("2026-04-27T17:00:00+02:00")

    def test_rejects_garbage(self) -> None:
        with pytest.raises(ValueError):
            parse_utc_iso("not-a-date")


class TestFormatUtc:
    def test_emits_z_suffix(self) -> None:
        dt = datetime(2026, 4, 27, 17, 0, 0, tzinfo=timezone.utc)
        assert format_utc(dt) == "2026-04-27T17:00:00Z"

    def test_strips_microseconds(self) -> None:
        dt = datetime(2026, 4, 27, 17, 0, 0, 500_000, tzinfo=timezone.utc)
        assert format_utc(dt) == "2026-04-27T17:00:00Z"


class TestDayBoundsUtc:
    def test_utc_today(self) -> None:
        now = datetime(2026, 4, 27, 14, 0, 0, tzinfo=timezone.utc)
        start, end = day_bounds_utc(now, "UTC")
        assert start == datetime(2026, 4, 27, 0, 0, 0, tzinfo=timezone.utc)
        assert end == datetime(2026, 4, 28, 0, 0, 0, tzinfo=timezone.utc)

    def test_other_tz_shifts_window(self) -> None:
        # 2026-04-27 14:00 UTC == 2026-04-27 19:00 Asia/Karachi (UTC+5)
        now = datetime(2026, 4, 27, 14, 0, 0, tzinfo=timezone.utc)
        start, end = day_bounds_utc(now, "Asia/Karachi")
        assert start == datetime(2026, 4, 26, 19, 0, 0, tzinfo=timezone.utc)
        assert end == datetime(2026, 4, 27, 19, 0, 0, tzinfo=timezone.utc)

    def test_invalid_tz_raises(self) -> None:
        with pytest.raises(ValueError):
            day_bounds_utc(datetime.now(timezone.utc), "Not/A/Zone")
