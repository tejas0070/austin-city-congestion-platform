# tests/test_expected_value_interval.py
"""Expected-value interval (the confidence lever).

The app displays the model's estimate of the TYPICAL congestion for a
(corridor, hour-of-week). The honest interval to attach is therefore one that
covers that typical value, not the wide spread of individual 15-min readings.
`compute_conformal_q` (reused with low==high==prediction) calibrates a symmetric
half-width `q` so `pred ± q` covers the true bucket mean at the nominal rate;
`expected_value_interval` applies it; new EV width anchors map the (much tighter)
width to a confidence score.
"""
import pytest

from backend.etl.confidence import (
    compute_conformal_q,
    expected_value_interval,
    expected_value_anchors,
    modulated_half_width,
    width_to_confidence,
    EV_WIDTH_FULL_CONF,
    EV_WIDTH_ZERO_CONF,
    EV_SCALE_MIN,
    EV_SCALE_MAX,
)


def _coverage(preds, q, truths):
    lo = [p - q for p in preds]
    hi = [p + q for p in preds]
    return sum(1 for l, h, y in zip(lo, hi, truths) if l <= y <= h) / len(truths)


def test_expected_value_interval_is_symmetric_around_prediction():
    assert expected_value_interval(30.0, 4.0) == (26.0, 34.0)


def test_expected_value_interval_zero_q_is_a_point():
    assert expected_value_interval(12.5, 0.0) == (12.5, 12.5)


def test_conformal_q_calibrates_point_interval_to_nominal_coverage():
    # 200 buckets: true means spread symmetrically around their predictions with
    # residuals in [-10, 10]. An 80% interval should need q ~= 8 and then cover
    # ~80% of the true means.
    preds = [50.0] * 200
    truths = [50.0 + ((i % 21) - 10) for i in range(200)]  # residuals -10..10
    q = compute_conformal_q(preds, preds, truths, coverage=0.8)
    assert q > 0
    assert _coverage(preds, q, truths) >= 0.8
    # and the 80% half-width is materially tighter than the full residual range
    assert q < 10.0


def test_perfectly_predicted_means_give_zero_width_full_confidence():
    preds = [10.0, 20.0, 30.0, 40.0]
    q = compute_conformal_q(preds, preds, preds, coverage=0.8)
    assert q == pytest.approx(0.0)
    lo, hi = expected_value_interval(20.0, q)
    conf = width_to_confidence(hi - lo, *expected_value_anchors())
    assert conf == 100.0


def test_ev_anchors_map_tight_width_high_and_wide_width_low():
    full, zero = expected_value_anchors()
    assert full == EV_WIDTH_FULL_CONF
    assert zero == EV_WIDTH_ZERO_CONF
    assert full < zero
    tight = width_to_confidence(full, full, zero)
    wide = width_to_confidence(zero, full, zero)
    assert tight == 100.0
    assert wide == 0.0
    # a mid expected-value width still reads high (typical values are known well)
    mid = width_to_confidence((full + zero) / 2, full, zero)
    assert mid == pytest.approx(50.0)


def test_ev_anchors_are_tighter_than_per_reading_anchors():
    # The whole point of the lever: the expected value is known far more tightly
    # than an individual reading, so its anchors live on a smaller scale.
    from backend.etl.confidence import ABS_WIDTH_FULL_CONF, ABS_WIDTH_ZERO_CONF
    assert EV_WIDTH_ZERO_CONF < ABS_WIDTH_ZERO_CONF


# --- per-corridor modulation of the calibrated half-width -------------------

def test_modulation_average_row_is_unchanged():
    # A corridor with the population-average learned width keeps the calibrated q.
    assert modulated_half_width(4.0, 10.0, 10.0) == pytest.approx(4.0)


def test_modulation_widens_uncertain_and_tightens_confident():
    ev_q = 4.0
    ref = 10.0
    confident = modulated_half_width(ev_q, 6.0, ref)   # narrower learned band
    uncertain = modulated_half_width(ev_q, 16.0, ref)  # wider learned band
    assert confident < ev_q < uncertain
    # translated to confidence, the low-uncertainty corridor reads higher
    anchors = expected_value_anchors()
    conf_confident = width_to_confidence(2 * confident, *anchors)
    conf_uncertain = width_to_confidence(2 * uncertain, *anchors)
    assert conf_confident > conf_uncertain


def test_modulation_is_bounded():
    ev_q = 4.0
    ref = 10.0
    # an extremely wide/narrow learned band is clamped to the scale bounds
    assert modulated_half_width(ev_q, 1000.0, ref) == pytest.approx(ev_q * EV_SCALE_MAX)
    assert modulated_half_width(ev_q, 0.0, ref) == pytest.approx(ev_q * EV_SCALE_MIN)


def test_modulation_falls_back_to_ev_q_without_reference():
    # older artifacts have no ev_ref_width -> serve the unmodulated half-width
    assert modulated_half_width(4.0, 12.0, None) == 4.0
    assert modulated_half_width(4.0, None, 10.0) == 4.0
    assert modulated_half_width(4.0, 12.0, 0.0) == 4.0
