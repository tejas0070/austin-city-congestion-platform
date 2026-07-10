"""Wall-clock time in Austin's local timezone.

The app serves naive, Austin-local ISO timestamps and the frontend parses them
as local wall-clock, so the prediction paths must reason in Austin time
regardless of the server's own timezone. Cloud hosts (incl. HF Spaces) run in
UTC, so a bare ``datetime.now()`` there computes the wrong hour-of-day and shifts every
"+Nh" forecast (and can flip "today" across the UTC/Central date boundary). These
helpers pin the reference to America/Chicago and return it *naive* so the existing
ISO contract — Austin wall-clock shown to every viewer — is unchanged.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

AUSTIN_TZ = ZoneInfo("America/Chicago")


def austin_now() -> datetime:
    """Current Austin wall-clock time as a naive datetime (no tzinfo)."""
    return datetime.now(AUSTIN_TZ).replace(tzinfo=None)


def austin_today() -> date:
    """Current Austin calendar date."""
    return austin_now().date()
