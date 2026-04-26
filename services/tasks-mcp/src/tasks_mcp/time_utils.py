from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def parse_utc_iso(value: str) -> datetime:
    """Parse an ISO-8601 datetime that MUST be UTC.

    Accepts only the trailing-`Z` form. Naive datetimes and non-UTC offsets
    are rejected so the server never has to guess timezone.
    """
    if not value.endswith("Z"):
        raise ValueError(
            "Datetime must be ISO-8601 UTC with trailing 'Z' (e.g. '2026-04-27T17:00:00Z')."
        )
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError(f"Could not parse datetime: {value!r}") from e
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError("Datetime must be in UTC.")
    return dt.astimezone(timezone.utc)


def format_utc(dt: datetime) -> str:
    """Format a UTC datetime as ISO-8601 with trailing `Z`, no microseconds."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def day_bounds_utc(now: datetime, tz_name: str) -> tuple[datetime, datetime]:
    """Return the [start, end) of *today* in tz_name, expressed in UTC."""
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as e:
        raise ValueError(f"Unknown timezone: {tz_name!r}") from e
    local = now.astimezone(tz)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
