"""Time helpers. Everything is stored in UTC; Cairo time is only for display (ARCHITECTURE.md A1)."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

CAIRO_TZ = ZoneInfo("Africa/Cairo")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """Normalise a naive-or-aware datetime to timezone-aware UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_cairo(value: datetime | None) -> datetime | None:
    utc_value = as_utc(value)
    return utc_value.astimezone(CAIRO_TZ) if utc_value else None
