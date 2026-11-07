from datetime import date, datetime, timezone

import pytest

from mathly2 import clock


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_just_before_midnight_in_israel_is_still_today():
    # 2026-11-10 21:59 UTC = 23:59 in Israel (UTC+2 in winter)
    assert clock.school_day(utc(2026, 11, 10, 21, 59)) == date(2026, 11, 10)


def test_just_after_midnight_in_israel_is_tomorrow():
    # 2026-11-10 22:01 UTC = 00:01 on the 11th in Israel
    assert clock.school_day(utc(2026, 11, 10, 22, 1)) == date(2026, 11, 11)


def test_summer_time_shifts_the_boundary():
    # UTC+3 in summer: 21:00 UTC is already the next day
    assert clock.school_day(utc(2026, 7, 10, 20, 59)) == date(2026, 7, 10)
    assert clock.school_day(utc(2026, 7, 10, 21, 0)) == date(2026, 7, 11)


def test_naive_time_is_refused():
    with pytest.raises(ValueError):
        clock.school_day(datetime(2026, 11, 10, 12, 0))


def test_now_has_a_timezone():
    assert clock.now().tzinfo is not None
