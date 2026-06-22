"""Tests for aggregated forecast confidence: whole-day and whole-week averages.

The single-time path already reports a city-wide `confidence_avg`. These cover the
new aggregations: a per-hour + whole-day average (predict_day) and a 7-day
Mon..Sun average (predict_week), plus the graceful no-quantiles fallback.
"""
from datetime import date, timedelta
from unittest.mock import patch, AsyncMock

import pytest
from fastapi import HTTPException

from backend.services import ml_model
from backend.services.ml_model import predict_day, predict_week
from backend.api.routes.traffic import get_corridors_week
from backend.utils.cache import clear_cache


_CURRENT_WEATHER = {
    "condition": "Clear", "weather_code": 0, "temperature_f": 80.0,
    "precipitation_in": 0.0, "rain_alert": False,
}

_LABELS = {"High", "Medium", "Low"}


def _patched_weather_and_events():
    """Patch weather (proxy) + events (none) so predict_day/week run offline."""
    return [
        patch("backend.services.weather_service.fetch_current_weather",
              AsyncMock(return_value=_CURRENT_WEATHER)),
        patch("backend.services.weather_service.fetch_hourly_forecast",
              AsyncMock(return_value=None)),
        patch("backend.services.events_service.fetch_upcoming_events",
              AsyncMock(return_value=[])),
    ]


# --- predict_day confidence ----------------------------------------------

@pytest.mark.asyncio
async def test_predict_day_reports_whole_day_confidence():
    if not ml_model.quantiles_are_available():
        pytest.skip("quantile models not trained in this environment")
    clear_cache()
    patches = _patched_weather_and_events()
    for p in patches:
        p.start()
    try:
        result = await predict_day(date.today())
    finally:
        for p in patches:
            p.stop()

    # Whole-day average present and in range.
    assert isinstance(result["confidence_avg"], (int, float))
    assert 0.0 <= result["confidence_avg"] <= 100.0
    assert result["confidence_label"] in _LABELS

    # Every hour carries its own average confidence.
    assert len(result["hours"]) == 24
    for hour in result["hours"]:
        assert 0.0 <= hour["confidence_avg"] <= 100.0
        assert hour["confidence_label"] in _LABELS

    # The whole-day average equals the mean of the 24 hourly averages.
    hourly = [h["confidence_avg"] for h in result["hours"]]
    expected = round(sum(hourly) / len(hourly), 1)
    assert result["confidence_avg"] == pytest.approx(expected, abs=0.1)


@pytest.mark.asyncio
async def test_predict_day_reports_whole_day_congestion():
    clear_cache()
    patches = _patched_weather_and_events()
    for p in patches:
        p.start()
    try:
        result = await predict_day(date.today())
    finally:
        for p in patches:
            p.stop()

    # Whole-day congestion average present and in range.
    assert 0.0 <= result["congestion_avg"] <= 100.0
    assert result["congestion_level"] in ("green", "yellow", "red")

    # It equals the mean of the 24 hourly avg_pct values.
    hourly = [h["avg_pct"] for h in result["hours"]]
    expected = round(sum(hourly) / len(hourly), 1)
    assert result["congestion_avg"] == pytest.approx(expected, abs=0.1)


@pytest.mark.asyncio
async def test_predict_day_omits_confidence_without_quantiles(monkeypatch):
    clear_cache()
    monkeypatch.setattr(ml_model, "quantiles_are_available", lambda: False)
    monkeypatch.setattr(ml_model, "_quantiles", None, raising=False)
    monkeypatch.setattr(ml_model, "get_cache", lambda key: None)

    patches = _patched_weather_and_events()
    for p in patches:
        p.start()
    try:
        result = await predict_day(date.today())
    finally:
        for p in patches:
            p.stop()

    assert "confidence_avg" not in result
    assert "confidence_label" not in result
    assert all("confidence_avg" not in h for h in result["hours"])


# --- predict_week confidence ---------------------------------------------

@pytest.mark.asyncio
async def test_predict_week_aggregates_seven_days():
    if not ml_model.quantiles_are_available():
        pytest.skip("quantile models not trained in this environment")
    clear_cache()
    start = date.today()
    patches = _patched_weather_and_events()
    for p in patches:
        p.start()
    try:
        result = await predict_week(start)
    finally:
        for p in patches:
            p.stop()

    assert result["start_date"] == start.isoformat()
    assert result["end_date"] == (start + timedelta(days=6)).isoformat()
    assert len(result["days"]) == 7

    for i, day in enumerate(result["days"]):
        assert day["date"] == (start + timedelta(days=i)).isoformat()
        assert 0.0 <= day["confidence_avg"] <= 100.0
        assert day["confidence_label"] in _LABELS
        assert "weekday" in day
        # Each day also carries its congestion average for the UI's congestion row.
        assert 0.0 <= day["congestion_avg"] <= 100.0
        assert day["congestion_level"] in ("green", "yellow", "red")

    # Week average equals the mean of the 7 daily averages.
    daily = [d["confidence_avg"] for d in result["days"]]
    expected = round(sum(daily) / len(daily), 1)
    assert result["confidence_avg"] == pytest.approx(expected, abs=0.1)
    assert result["confidence_label"] in _LABELS

    # Week congestion average equals the mean of the 7 daily congestion averages.
    daily_cong = [d["congestion_avg"] for d in result["days"]]
    expected_cong = round(sum(daily_cong) / len(daily_cong), 1)
    assert result["congestion_avg"] == pytest.approx(expected_cong, abs=0.1)
    assert result["congestion_level"] in ("green", "yellow", "red")


# --- /week route validation ----------------------------------------------

@pytest.mark.asyncio
async def test_week_route_rejects_malformed_start():
    with pytest.raises(HTTPException) as exc:
        await get_corridors_week(start="06-30-2026", include_events=True)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_week_route_rejects_too_far_past_start():
    # The current week's Monday can be up to 6 days back, so only starts earlier
    # than that are rejected.
    too_far = (date.today() - timedelta(days=8)).isoformat()
    with pytest.raises(HTTPException) as exc:
        await get_corridors_week(start=too_far, include_events=True)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_week_route_rejects_out_of_range_start():
    # Far enough that the 7-day window's last day exceeds the preview horizon.
    far = (date.today() + timedelta(days=200)).isoformat()
    with pytest.raises(HTTPException) as exc:
        await get_corridors_week(start=far, include_events=True)
    assert exc.value.status_code == 400
