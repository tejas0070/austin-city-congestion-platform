# tests/test_event_impact.py
"""Event-impact overlay: a rule-based congestion uplift on top of the ML baseline.

The model is blind to events (no event examples in the sensor-history training
data), so `event_congestion_uplift` turns each segment's distance/time-weighted
crowd signal into congestion points. These tests lock in the curve's shape and
prove the serving path makes roads NEAR a venue back up around SHOWTIME while
leaving distant/off-time roads unchanged.
"""
from datetime import datetime

import pytest

from backend.etl.event_impact import (
    event_congestion_uplift,
    event_reach_km,
    event_time_window_hours,
    EVENT_MAX_UPLIFT_PCT,
    EVENT_SIGNAL_PER_PCT,
    EVENT_REACH_MIN_KM,
    EVENT_REACH_MAX_KM,
    EVENT_WINDOW_MIN_HOURS,
    EVENT_WINDOW_MAX_HOURS,
)


# --- time window scales with crowd (big games build up earlier) -------------

def test_time_window_grows_with_crowd_but_is_bounded():
    small = event_time_window_hours(2200)
    arena = event_time_window_hours(15000)
    stadium = event_time_window_hours(100000)
    assert EVENT_WINDOW_MIN_HOURS <= small < arena < stadium <= EVENT_WINDOW_MAX_HOURS
    assert stadium >= 5.0  # a 100k game snarls traffic hours before kickoff


def test_time_window_floor_and_ceiling():
    assert event_time_window_hours(0) == EVENT_WINDOW_MIN_HOURS
    assert event_time_window_hours(10_000_000) == EVENT_WINDOW_MAX_HOURS


# --- reach scales with crowd size (bigger events first, small ones still count) -

def test_reach_grows_with_crowd_but_is_bounded():
    small = event_reach_km(2200)      # Stubbs-sized club show
    arena = event_reach_km(15000)     # Moody Center
    stadium = event_reach_km(100000)  # UT football
    assert EVENT_REACH_MIN_KM <= small < arena < stadium <= EVENT_REACH_MAX_KM
    # a small venue stays local; a stadium floods a wide ring
    assert small < 4.0
    assert stadium > 10.0


def test_reach_floor_and_ceiling():
    assert event_reach_km(0) == EVENT_REACH_MIN_KM
    assert event_reach_km(10_000_000) == EVENT_REACH_MAX_KM


# --- the uplift curve -------------------------------------------------------

def test_no_event_no_uplift():
    assert event_congestion_uplift(0) == 0.0
    assert event_congestion_uplift(-5) == 0.0


def test_uplift_scales_with_crowd():
    small = event_congestion_uplift(3000)
    big = event_congestion_uplift(15000)
    assert 0 < small < big
    assert big == pytest.approx(15000 / EVENT_SIGNAL_PER_PCT)


def test_uplift_saturates_at_cap():
    # a stadium-scale crowd cannot push a road past the realistic ceiling
    assert event_congestion_uplift(1_000_000) == EVENT_MAX_UPLIFT_PCT


# --- serving path: which roads, and when ------------------------------------

def _venue_event(lat, lng, attendance, when):
    return {"lat": lat, "lng": lng, "expected_attendance": attendance, "start_dt": when}


def test_nearby_roads_back_up_but_distant_ones_do_not():
    """A big concert must raise predicted congestion on roads near the venue and
    leave roads across town unchanged."""
    from backend.services import ml_model
    if not ml_model.model_is_available():
        pytest.skip("model not trained in this environment")

    from backend.services.congestion_features import nearby_event_attendance
    from backend.services.segments_service import load_display_segments

    show_dt = datetime(2026, 7, 3, 20, 0)  # 8 PM show
    segs = load_display_segments()
    # Anchor the event on a real segment's centroid so at least one road is on top.
    venue = segs[0]
    event = _venue_event(venue["centroid_lat"], venue["centroid_lng"], 20000, show_dt)

    # A segment is "near" if the weighting gives it a non-zero crowd signal.
    near = [s for s in segs
            if nearby_event_attendance(s["centroid_lat"], s["centroid_lng"], show_dt, [event]) > 0]
    assert near, "expected at least one segment near the venue"

    # Predict the same time with and without the event.
    segs_base, rows_base, preds_base = ml_model._run_predictions(show_dt, 0, 78.0, 0.0, [])
    segs_evt, rows_evt, preds_evt = ml_model._run_predictions(show_dt, 0, 78.0, 0.0, [event])

    idx_by_id = {s["segment_id"]: i for i, s in enumerate(segs_evt)}
    i = idx_by_id[near[0]["segment_id"]]
    assert preds_evt[i] > preds_base[i]  # the near road backs up
    assert rows_evt[i]["_event_uplift"] > 0

    # A far-away segment (zero crowd signal) is unchanged.
    far = [s for s in segs
           if nearby_event_attendance(s["centroid_lat"], s["centroid_lng"], show_dt, [event]) == 0]
    if far:
        j = idx_by_id[far[0]["segment_id"]]
        assert preds_evt[j] == pytest.approx(preds_base[j])


def test_timing_matters_closer_to_showtime_is_worse():
    """The same event should back a road up MORE near showtime than hours before."""
    from backend.services import ml_model
    if not ml_model.model_is_available():
        pytest.skip("model not trained in this environment")
    from backend.services.congestion_features import nearby_event_attendance
    from backend.services.segments_service import load_display_segments

    show_dt = datetime(2026, 7, 3, 20, 0)
    segs = load_display_segments()
    venue = segs[0]
    event = _venue_event(venue["centroid_lat"], venue["centroid_lng"], 20000, show_dt)

    near = next((s for s in segs
                 if nearby_event_attendance(s["centroid_lat"], s["centroid_lng"], show_dt, [event]) > 0), None)
    if near is None:
        pytest.skip("no segment near the synthetic venue")
    idx = {s["segment_id"]: i for i, s in enumerate(segs)}[near["segment_id"]]

    _, rows_at, _ = ml_model._run_predictions(show_dt, 0, 78.0, 0.0, [event])
    _, rows_early, _ = ml_model._run_predictions(show_dt.replace(hour=17, minute=1), 0, 78.0, 0.0, [event])
    assert rows_at[idx]["_event_uplift"] > rows_early[idx]["_event_uplift"]
