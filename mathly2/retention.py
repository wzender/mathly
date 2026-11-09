"""How long pictures are kept (PRD ANS-3): answer pictures until the end of the school year (31 August), unreferenced pictures for a day,
assignment pages until their assignment is removed. Grades and teachers' notes are never touched: only the pictures go."""
from __future__ import annotations

from datetime import date, timedelta

ORPHAN_AGE = timedelta(hours=24)


def expires_on(day: date) -> date:
    """The last day an answer picture made on `day` is kept: 31 August of its school year (1 September to 31 August)."""
    return date(day.year + 1 if day.month >= 9 else day.year, 8, 31)


def is_expired(created_day: date, today: date) -> bool:
    """An answer picture is removed from 1 September on."""
    return today > expires_on(created_day)
