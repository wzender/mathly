"""Server time. Every rule that depends on days (mastery, the countdown, the simulation window) uses this,
never the device's clock."""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

ISRAEL = ZoneInfo("Asia/Jerusalem")


def now() -> datetime:
    return datetime.now(timezone.utc)


def school_day(moment: datetime | None = None) -> date:
    """The calendar day in Israel at `moment` (default: now)."""
    moment = moment or now()
    if moment.tzinfo is None:
        raise ValueError("moment must have a timezone")
    return moment.astimezone(ISRAEL).date()
