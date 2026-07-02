# tests/test_prediction_confidence.py
import asyncio
from backend.services import ml_model


def _run(coro):
    return asyncio.run(coro)


def test_near_zero_prediction_is_not_over_confident(monkeypatch):
    """The clamp-artifact fix: confidence comes from the true interval half-width,
    not the width after clipping to [0, 100]. A near-empty road (interval clipped
    at the 0 floor) must NOT read more confident than a mid-range one with the
    same uncertainty."""
    # No ev_ref_width -> unmodulated constant half-width, so any confidence
    # difference between the two rows could ONLY come from the clamp.
    monkeypatch.setattr(ml_model, "quantiles_are_available", lambda: True)
    monkeypatch.setattr(ml_model, "_load_quantiles", lambda: {"ev_q_80": 4.0})
    rows = [{"_support": ("segment", 50)}, {"_support": ("segment", 50)}]
    predictions = [1.0, 50.0]  # near-zero (would be clipped) vs mid-range
    intervals = ml_model._segment_confidences(rows, predictions)
    near_zero_conf = intervals[0][2]
    mid_conf = intervals[1][2]
    assert near_zero_conf == mid_conf


def test_predicted_features_carry_confidence_when_quantiles_present():
    if not ml_model.model_is_available() or not ml_model.quantiles_are_available():
        import pytest
        pytest.skip("models not trained in this environment")
    fc = _run(ml_model.predict_segments(hours_ahead=2.0, include_events=False))
    assert "confidence_avg" in fc
    assert fc["confidence_label"] in {"High", "Medium", "Low"}
    props = fc["features"][0]["properties"]
    for key in ("congestion_low", "congestion_high", "confidence_pct", "confidence_label"):
        assert key in props
    assert props["congestion_low"] <= props["congestion_high"]


def test_fallback_when_quantiles_missing(monkeypatch):
    # Force the "no quantile models" path; predictions must still work, sans confidence.
    monkeypatch.setattr(ml_model, "quantiles_are_available", lambda: False)
    monkeypatch.setattr(ml_model, "_quantiles", None, raising=False)
    # Bypass cache so a previous cached result (with confidence) doesn't leak in.
    # get_cache/set_cache are imported directly into ml_model's namespace, so patch there.
    monkeypatch.setattr(ml_model, "get_cache", lambda key: None)
    if not ml_model.model_is_available():
        import pytest
        pytest.skip("point model not trained")
    fc = _run(ml_model.predict_segments(hours_ahead=2.0, include_events=False))
    assert "confidence_avg" not in fc
    assert "confidence_pct" not in fc["features"][0]["properties"]
