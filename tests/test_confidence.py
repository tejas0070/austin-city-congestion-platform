# tests/test_confidence.py
import pytest
from backend.etl.confidence import (
    width_to_confidence,
    confidence_label,
    clamp_interval,
)


def test_tight_band_is_high_confidence():
    # width at/below the low anchor -> ~100
    assert width_to_confidence(2.0, low_anchor=5.0, high_anchor=40.0) == 100.0


def test_wide_band_is_low_confidence():
    # width at/above the high anchor -> ~0
    assert width_to_confidence(50.0, low_anchor=5.0, high_anchor=40.0) == 0.0


def test_midpoint_band_is_mid_confidence():
    # halfway between anchors -> 50
    assert width_to_confidence(22.5, low_anchor=5.0, high_anchor=40.0) == 50.0


def test_equal_anchors_do_not_divide_by_zero():
    assert width_to_confidence(10.0, low_anchor=10.0, high_anchor=10.0) == 100.0


@pytest.mark.parametrize("pct,label", [(90, "High"), (60, "Medium"), (10, "Low")])
def test_confidence_label_bands(pct, label):
    assert confidence_label(pct) == label


def test_clamp_interval_orders_and_bounds():
    # crossing quantiles get reordered; values clamp to [0, 100]
    assert clamp_interval(120.0, -5.0) == (0.0, 100.0)
    assert clamp_interval(80.0, 60.0) == (60.0, 80.0)
