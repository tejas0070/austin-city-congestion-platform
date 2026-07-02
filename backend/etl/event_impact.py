# backend/etl/event_impact.py
"""Event-impact overlay: attendance/proximity/time-weighted congestion uplift.

The ML model is blind to events. The real sensor-history training windows contain
**zero** event examples, so `nearby_event_attendance` has a learned importance of
exactly 0.000 (see docs/radar_ablation.md) — the model cannot forecast what a
concert or a stadium crowd does to nearby roads.

Event impact is therefore modeled explicitly here, as a transparent domain-rule
overlay layered on top of the ML baseline:

  * crowd size (attendance) sets the MAGNITUDE of the uplift, and
  * proximity + time-to-event set WHICH roads and WHEN — those are already baked
    into the per-segment `attendance_signal` that
    `congestion_features.nearby_event_attendance` computes (distance-weighted to
    8 km, time-weighted to +/-3 h of the event).

So a road on top of a 15k-seat venue at showtime gets a large uplift that decays
smoothly to zero as you move away from the venue or away from the event time. This
is a deliberate modeling choice, not a learned effect, and is labeled as such
wherever it surfaces in the UI.
"""
from __future__ import annotations

import math

# One congestion-point of uplift per this many attendance-signal units, capped.
# Calibrated to domain expectation, not fit to data (there is none): a ~15k crowd
# essentially on top of a corridor at showtime adds ~10 pts; a ~100k UT-football
# crowd saturates the cap. Matches the curve the synthetic generator has always
# used, so real-data serving and synthetic labels stay consistent.
EVENT_SIGNAL_PER_PCT = 1500.0
EVENT_MAX_UPLIFT_PCT = 45.0


def event_congestion_uplift(attendance_signal: float) -> float:
    """Congestion-percent uplift for a segment's distance/time-weighted crowd signal.

    Returns 0 for no nearby/on-time event; grows linearly with the weighted crowd
    size; saturates at `EVENT_MAX_UPLIFT_PCT` so even a stadium cannot push a road
    past a realistic ceiling. The distance and timing decay live in the caller's
    `attendance_signal` (nearby_event_attendance), so this is purely the magnitude.
    """
    signal = float(attendance_signal)
    if signal <= 0:
        return 0.0
    return round(min(EVENT_MAX_UPLIFT_PCT, signal / EVENT_SIGNAL_PER_PCT), 2)


# How far an event's congestion reaches scales with the crowd: a 2k club show is a
# local bump, a ~100k stadium game floods a wide area. Reach (km) grows with the
# square root of attendance (crowd spills roughly with area, not linearly) between
# a tight local floor and a metro-wide ceiling. Big games therefore back up many
# more corridors than small concerts — addressed first, without ignoring the
# smaller venues, which still register a real local effect.
EVENT_REACH_MIN_KM = 2.5    # smallest venues: a few blocks around the door
EVENT_REACH_MAX_KM = 15.0   # a stadium-scale crowd floods a wide ring of roads


def event_reach_km(attendance: float) -> float:
    """Radius (km) over which an event of this crowd size measurably backs up roads.

    Anchored to real Austin venues: ~3 km for a 2k club show (Stubbs), ~6 km for a
    15k arena night (Moody Center), ~14 km for a 100k UT-football Saturday.
    """
    reach = 1.2 + 0.04 * math.sqrt(max(0.0, float(attendance)))
    return round(min(EVENT_REACH_MAX_KM, max(EVENT_REACH_MIN_KM, reach)), 2)


# How many hours BEFORE/after the event traffic is affected also scales with the
# crowd: a club show builds ~2.5 h out, a stadium game snarls traffic ~6 h out (and
# lingers after) as tens of thousands arrive early and leave together. Same
# √attendance shape as the reach, so "bigger events first" is consistent.
EVENT_WINDOW_MIN_HOURS = 2.5
EVENT_WINDOW_MAX_HOURS = 6.0


def event_time_window_hours(attendance: float) -> float:
    """Hours around showtime over which an event of this crowd size affects traffic.

    ~2.5 h for a small concert, ~3 h for a 15k arena night, ~6 h for a 100k game.
    """
    window = 1.5 + 0.014 * math.sqrt(max(0.0, float(attendance)))
    return round(min(EVENT_WINDOW_MAX_HOURS, max(EVENT_WINDOW_MIN_HOURS, window)), 2)
