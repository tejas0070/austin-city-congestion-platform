# backend/etl/holiday_impact.py
"""Federal-holiday congestion overlay: fewer people commute, so roads are lighter.

The learned model keys off hour / day-of-week / is_weekend and each corridor's
typical level, so on a WEEKDAY federal holiday it still predicts an ordinary rush
hour — but in reality most people are off work and traffic looks more like a weekend.
This overlay dampens the baseline flow on federal holidays. Like the weather and
event overlays it is an educated-guess multiplier, NOT a learned effect (holidays are
far too rare in the sensor history to learn), and it is applied on top of the model.

Holidays are tiered by how much of the workforce is actually off:

  * MAJOR  — near-universal day off, the commute nearly vanishes: New Year's Day,
             Memorial Day, Independence Day, Labor Day, Thanksgiving, Christmas.
  * MINOR  — government and banks close but many businesses stay open, so the drop
             is milder: MLK Day, Washington's Birthday (Presidents' Day), Juneteenth,
             Columbus Day, Veterans Day.

Observed dates are honored (e.g. a Saturday July 4th shifts the day off to Friday),
because that is when people are actually off the road. Event surges on a holiday (a
July-4th concert) are added separately by the event overlay, so a light-commute day
with a packed venue still reads correctly.
"""
from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache

import holidays

# Multiplier applied to the baseline flow on a federal holiday (< 1 => lighter).
MAJOR_HOLIDAY_MULTIPLIER = 0.55   # near-universal day off; commute largely gone
MINOR_HOLIDAY_MULTIPLIER = 0.8    # banks/govt closed, many businesses still open
NO_HOLIDAY_MULTIPLIER = 1.0

# Substrings matched against the holidays library's names (which may carry an
# "(observed)" suffix), classifying each federal holiday into a tier.
_MAJOR_HOLIDAY_KEYS = (
    "New Year", "Memorial Day", "Independence Day", "Labor Day",
    "Thanksgiving", "Christmas",
)


@lru_cache(maxsize=16)
def _us_holidays(year: int) -> "holidays.HolidayBase":
    """Cached US federal holiday calendar for a year (observed dates included)."""
    return holidays.US(years=year, observed=True)


def federal_holiday_name(d: date) -> str | None:
    """The federal holiday observed on `d`, or None if it is an ordinary day."""
    return _us_holidays(d.year).get(d)


def holiday_congestion_multiplier(dt: datetime | date) -> float:
    """Congestion multiplier for the date of `dt` (1.0 on non-holidays).

    Major holidays return `MAJOR_HOLIDAY_MULTIPLIER`, minor ones
    `MINOR_HOLIDAY_MULTIPLIER`. Applied to the baseline so it naturally trims the
    weekday rush (where congestion is highest) far more than the already-quiet
    overnight hours.
    """
    d = dt.date() if isinstance(dt, datetime) else dt
    name = federal_holiday_name(d)
    if not name:
        return NO_HOLIDAY_MULTIPLIER
    if any(key in name for key in _MAJOR_HOLIDAY_KEYS):
        return MAJOR_HOLIDAY_MULTIPLIER
    return MINOR_HOLIDAY_MULTIPLIER
