# tests/test_confidence_calibration.py
"""Conformal interval calibration + density-aware confidence cap.

Lever 1 (calibration): widen the q25/q75 band so its empirical coverage hits the
nominal 50%, instead of the ~44% it covered uncalibrated.
Lever 2 (density cap): a prediction can be no more confident than the real history
backing it, so fallback roads never out-confidence well-measured ones.
"""
import pytest

from backend.etl.confidence import (
    compute_conformal_q,
    conformal_interval,
    density_confidence_cap,
    apply_density_cap,
    ROAD_CLASS_CONF_CAP,
    GLOBAL_CONF_CAP,
    SUPPORT_FULL,
)


# --- conformal calibration --------------------------------------------------

def _coverage(lo, hi, ys):
    return sum(1 for y in ys if lo <= y <= hi) / len(ys)


def test_conformal_q_widens_an_undercovering_band():
    # band [4, 6] but truths spread 0..10 -> mostly outside -> must widen (q > 0)
    ys = [i / 10.0 for i in range(0, 101)]  # 0.0 .. 10.0
    lo = [4.0] * len(ys)
    hi = [6.0] * len(ys)
    q = compute_conformal_q(lo, hi, ys, coverage=0.5)
    assert q > 0
    # after widening, the band should cover at least ~50%
    new_lo, new_hi = conformal_interval(4.0, 6.0, q)
    assert _coverage(new_lo, new_hi, ys) >= 0.5


def test_conformal_q_narrows_an_overcovering_band():
    # band [0, 10] but truths cluster 4..6 -> over-covers -> q < 0 (narrow)
    ys = [4.0 + (i % 21) / 10.0 for i in range(200)]  # 4.0 .. 6.0
    lo = [0.0] * len(ys)
    hi = [10.0] * len(ys)
    q = compute_conformal_q(lo, hi, ys, coverage=0.5)
    assert q < 0


def test_conformal_interval_orders_inputs():
    # crossed quantiles get ordered before widening
    assert conformal_interval(6.0, 4.0, 1.0) == (3.0, 7.0)


def test_conformal_q_empty_is_zero():
    assert compute_conformal_q([], [], [], coverage=0.5) == 0.0


# --- density-aware cap ------------------------------------------------------

def test_dense_segment_history_is_uncapped():
    # a road with >= SUPPORT_FULL real readings can read up to 100
    assert density_confidence_cap("segment", SUPPORT_FULL) == pytest.approx(100.0)
    assert apply_density_cap(95.0, "segment", SUPPORT_FULL + 5) == 95.0


def test_single_reading_segment_is_capped_near_road_class():
    # one snapshot is barely-known -> cap just above the road-class cap
    cap = density_confidence_cap("segment", 1)
    assert ROAD_CLASS_CONF_CAP < cap < 100.0
    assert cap < ROAD_CLASS_CONF_CAP + (100.0 - ROAD_CLASS_CONF_CAP) * 0.5


def test_road_class_fallback_capped():
    assert density_confidence_cap("road_class") == ROAD_CLASS_CONF_CAP
    assert apply_density_cap(98.0, "road_class", 0) == ROAD_CLASS_CONF_CAP


def test_global_fallback_capped_lowest():
    assert density_confidence_cap("global") == GLOBAL_CONF_CAP
    assert apply_density_cap(98.0, "global", 0) == GLOBAL_CONF_CAP
    assert GLOBAL_CONF_CAP < ROAD_CLASS_CONF_CAP


def test_cap_never_raises_confidence():
    # an already-low confidence is unchanged by the cap
    assert apply_density_cap(20.0, "global", 0) == 20.0
    assert apply_density_cap(30.0, "road_class", 0) == 30.0


def test_well_measured_road_outranks_fallback():
    """The core fix: a well-measured road must read higher than an unknown one,
    even when both have the same raw (width-based) confidence."""
    raw = 96.0
    covered = apply_density_cap(raw, "segment", 50)      # dense real history
    unknown = apply_density_cap(raw, "global", 0)        # no history at all
    assert covered > unknown
