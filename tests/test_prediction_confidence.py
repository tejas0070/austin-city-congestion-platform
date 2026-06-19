# tests/test_prediction_confidence.py
import asyncio
from backend.services import ml_model


def _run(coro):
    return asyncio.run(coro)


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
