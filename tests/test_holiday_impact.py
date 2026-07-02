# tests/test_holiday_impact.py
"""Federal-holiday congestion overlay.

On a weekday federal holiday most people are off work, so the commute rush the model
would otherwise predict is largely absent. This overlay trims the baseline, tiered by
how much of the workforce is actually off (major holiday vs minor). It's an
educated-guess multiplier, not learned.
"""
from datetime import date, datetime

from backend.etl.holiday_impact import (
    holiday_congestion_multiplier,
    federal_holiday_name,
    MAJOR_HOLIDAY_MULTIPLIER,
    MINOR_HOLIDAY_MULTIPLIER,
    NO_HOLIDAY_MULTIPLIER,
)


def test_ordinary_weekday_is_unaffected():
    # a plain mid-week day in 2026 with no holiday
    assert holiday_congestion_multiplier(date(2026, 7, 8)) == NO_HOLIDAY_MULTIPLIER


def test_major_holiday_cuts_traffic_hardest():
    # Christmas / July 4th: near-universal day off
    assert holiday_congestion_multiplier(date(2026, 12, 25)) == MAJOR_HOLIDAY_MULTIPLIER
    assert holiday_congestion_multiplier(date(2026, 7, 4)) == MAJOR_HOLIDAY_MULTIPLIER


def test_minor_holiday_cuts_traffic_mildly():
    # MLK Day / Columbus Day: banks & govt closed, many still work
    assert holiday_congestion_multiplier(date(2026, 1, 19)) == MINOR_HOLIDAY_MULTIPLIER
    assert holiday_congestion_multiplier(date(2026, 10, 12)) == MINOR_HOLIDAY_MULTIPLIER
    assert MAJOR_HOLIDAY_MULTIPLIER < MINOR_HOLIDAY_MULTIPLIER < NO_HOLIDAY_MULTIPLIER


def test_observed_holiday_is_honored():
    # July 4, 2026 falls on a Saturday -> observed Friday July 3 is the day off
    assert federal_holiday_name(date(2026, 7, 3)) is not None
    assert holiday_congestion_multiplier(date(2026, 7, 3)) == MAJOR_HOLIDAY_MULTIPLIER


def test_accepts_datetime_and_date():
    assert holiday_congestion_multiplier(datetime(2026, 12, 25, 17, 0)) == MAJOR_HOLIDAY_MULTIPLIER
