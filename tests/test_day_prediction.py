"""Tests for whole-day prediction: forecast weather, compact day payload, and route validation."""
from datetime import date, datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from backend.services.weather_service import fetch_hourly_forecast
from backend.services.ml_model import predict_day, predict_segments, predict_for_datetime
from backend.api.routes.traffic import get_corridors_day
from backend.utils.cache import clear_cache
from fastapi import HTTPException


def _forecast_hour(temp=75.0):
    return {"weather_code": 0, "temperature_f": temp, "precipitation_in": 0.0, "condition": "Clear"}


_CURRENT_WEATHER = {
    "condition": "Clear", "weather_code": 0, "temperature_f": 80.0,
    "precipitation_in": 0.0, "rain_alert": False,
}


# --- fetch_hourly_forecast ------------------------------------------------

@pytest.mark.asyncio
async def test_hourly_forecast_none_beyond_horizon():
    clear_cache()
    far = date.today() + timedelta(days=40)
    # No network call should be needed; it is out of the 16-day window.
    assert await fetch_hourly_forecast(far) is None


@pytest.mark.asyncio
async def test_hourly_forecast_none_on_http_error():
    clear_cache()
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("network error")
        )
        assert await fetch_hourly_forecast(date.today() + timedelta(days=2)) is None


@pytest.mark.asyncio
async def test_hourly_forecast_parses_in_window():
    clear_cache()
    target = date.today() + timedelta(days=2)
    target_str = target.isoformat()
    # Two days of hourly data; only the target date should be returned.
    times, temps, precs, codes = [], [], [], []
    for d in (target, target + timedelta(days=1)):
        for h in range(24):
            times.append(f"{d.isoformat()}T{h:02d}:00")
            temps.append(70.0 + h)
            precs.append(0.0)
            codes.append(0)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={
        "hourly": {"time": times, "temperature_2m": temps, "precipitation": precs, "weather_code": codes}
    })
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        result = await fetch_hourly_forecast(target)

    assert result is not None
    assert set(result.keys()) == set(range(24))
    assert result[5]["temperature_f"] == 75.0  # 70 + hour 5
    assert result[5]["condition"] == "Clear"


# --- predict_day ----------------------------------------------------------

@pytest.mark.asyncio
async def test_predict_day_shape_with_proxy_weather():
    clear_cache()
    with patch("backend.services.weather_service.fetch_current_weather",
               AsyncMock(return_value=_CURRENT_WEATHER)), \
         patch("backend.services.weather_service.fetch_hourly_forecast",
               AsyncMock(return_value=None)), \
         patch("backend.services.events_service.fetch_upcoming_events",
               AsyncMock(return_value=[])):
        result = await predict_day(date.today())

    assert result["weather_source"] == "proxy"
    assert len(result["hours"]) == 24
    assert len(result["series"]) == 24

    seg_count = len(result["segments"]["features"])
    assert seg_count > 0
    assert all(len(row) == seg_count for row in result["series"])
    assert all(v in (0, 1, 2) for row in result["series"] for v in row)

    h8 = result["hours"][8]
    assert h8["hour"] == 8 and h8["label"] == "8:00 AM"
    assert h8["avg_level"] in ("green", "yellow", "red")
    assert h8["weather_source"] == "proxy"


@pytest.mark.asyncio
async def test_predict_day_uses_forecast_when_available():
    clear_cache()
    forecast = {h: _forecast_hour() for h in range(24)}
    with patch("backend.services.weather_service.fetch_current_weather",
               AsyncMock(return_value=_CURRENT_WEATHER)), \
         patch("backend.services.weather_service.fetch_hourly_forecast",
               AsyncMock(return_value=forecast)), \
         patch("backend.services.events_service.fetch_upcoming_events",
               AsyncMock(return_value=[])):
        result = await predict_day(date.today() + timedelta(days=1))

    assert result["weather_source"] == "forecast"
    assert all(h["weather_source"] == "forecast" for h in result["hours"])


@pytest.mark.asyncio
async def test_predict_day_mixed_weather_source():
    clear_cache()
    forecast = {h: _forecast_hour() for h in range(12)}  # morning only
    with patch("backend.services.weather_service.fetch_current_weather",
               AsyncMock(return_value=_CURRENT_WEATHER)), \
         patch("backend.services.weather_service.fetch_hourly_forecast",
               AsyncMock(return_value=forecast)), \
         patch("backend.services.events_service.fetch_upcoming_events",
               AsyncMock(return_value=[])):
        result = await predict_day(date.today() + timedelta(days=1))

    assert result["weather_source"] == "mixed"
    assert result["hours"][3]["weather_source"] == "forecast"
    assert result["hours"][20]["weather_source"] == "proxy"


# --- predict_for_datetime parity -----------------------------------------

@pytest.mark.asyncio
async def test_predict_for_datetime_returns_colored_features():
    clear_cache()
    with patch("backend.services.weather_service.fetch_current_weather",
               AsyncMock(return_value=_CURRENT_WEATHER)), \
         patch("backend.services.events_service.fetch_upcoming_events",
               AsyncMock(return_value=[])):
        result = await predict_for_datetime(datetime.now() + timedelta(hours=2))

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) > 0
    props = result["features"][0]["properties"]
    assert props["congestion_index"] in (0, 1, 2)
    assert "predicted_for" in result


# --- route validation -----------------------------------------------------

@pytest.mark.asyncio
async def test_route_rejects_malformed_date():
    with pytest.raises(HTTPException) as exc:
        await get_corridors_day(date="06-14-2026", include_events=True)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_route_rejects_out_of_range_date():
    far = (date.today() + timedelta(days=200)).isoformat()
    with pytest.raises(HTTPException) as exc:
        await get_corridors_day(date=far, include_events=True)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_route_rejects_past_date():
    past = (date.today() - timedelta(days=1)).isoformat()
    with pytest.raises(HTTPException) as exc:
        await get_corridors_day(date=past, include_events=True)
    assert exc.value.status_code == 400
