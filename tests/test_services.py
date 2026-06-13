import os
import pytest
from unittest.mock import patch, AsyncMock
from backend.services.txdot_service import fetch_live_traffic, fetch_incidents
from backend.services.weather_service import fetch_current_weather
from backend.services.events_service import fetch_upcoming_events
from backend.utils.cache import clear_cache


@pytest.mark.asyncio
async def test_fetch_live_traffic_falls_back_to_simulated():
    clear_cache()
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("network error")
        )
        result = await fetch_live_traffic()

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 5  # one per corridor
    assert result["features"][0]["properties"]["segment_id"] == "i35_downtown"


@pytest.mark.asyncio
async def test_fetch_incidents_falls_back_to_simulated_on_error():
    clear_cache()
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("network error")
        )
        result = await fetch_incidents()

    # The incidents layer always needs data to render, so a failed live feed
    # falls back to simulated incidents rather than an empty collection.
    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) > 0
    assert result["features"][0]["properties"]["incident_type"] in {
        "accident", "construction", "hazard", "closure",
    }


@pytest.mark.asyncio
async def test_fetch_weather_falls_back_to_defaults():
    clear_cache()
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("network error")
        )
        result = await fetch_current_weather()

    assert result["condition"] == "Clear"
    assert result["rain_alert"] is False
    assert result["temperature_f"] == 78.0


@pytest.mark.asyncio
async def test_fetch_events_returns_hardcoded_when_no_api_key():
    clear_cache()
    os.environ.pop("TICKETMASTER_API_KEY", None)
    result = await fetch_upcoming_events(days=365)
    assert isinstance(result, list)
    sources = {e["source"] for e in result}
    assert "austin_fc" in sources or "ut_football" in sources
