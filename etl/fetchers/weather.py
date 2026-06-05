"""
Weather fetcher — OpenWeatherMap Current Weather API.

Fetches all five Austin monitoring zones concurrently and returns a
list of WeatherSnapshot ORM objects ready for database insertion.
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from backend.app.geo_models import WeatherSnapshot
from ._http import get_json

logger = logging.getLogger(__name__)

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

# Five zones distributed across the Austin metro for spatial weather coverage.
# Each zone gets its own API call so spatial queries can find the nearest
# snapshot to any road segment.
AUSTIN_WEATHER_ZONES: dict[str, tuple[float, float]] = {
    "Downtown_Austin": (30.2672, -97.7431),
    "North_Austin":    (30.4087, -97.7198),
    "South_Austin":    (30.2242, -97.7561),
    "East_Austin":     (30.2583, -97.6987),
    "West_Austin":     (30.2965, -97.8004),
}


def _classify_impact(condition_id: int, wind_mph: float, temp_f: float) -> str:
    """Map raw weather values to a traffic-impact tier."""
    if condition_id in range(200, 300) or wind_mph > 40:
        return "Severe"
    if condition_id in range(500, 700):
        return "High"
    if condition_id in range(300, 500) or wind_mph > 25 or temp_f > 105 or temp_f < 25:
        return "Moderate"
    return "Low"


async def _fetch_zone(
    client: httpx.AsyncClient,
    api_key: str,
    zone_name: str,
    lat: float,
    lon: float,
) -> WeatherSnapshot:
    """Fetch one weather zone and return a WeatherSnapshot ORM object."""
    data = await get_json(client, OPENWEATHER_URL, {
        "lat":   lat,
        "lon":   lon,
        "appid": api_key,
        "units": "imperial",   # Fahrenheit, mph
    })

    w    = data["weather"][0]
    main = data["main"]
    wind = data["wind"]

    temp_f    = main["temp"]
    wind_mph  = wind["speed"]
    impact    = _classify_impact(w["id"], wind_mph, temp_f)

    logger.debug("%s: %s %.1f°F wind=%.1f mph impact=%s",
                 zone_name, w["description"], temp_f, wind_mph, impact)

    return WeatherSnapshot(
        timestamp=datetime.now(timezone.utc),
        location=f"SRID=4326;POINT({lon} {lat})",
        zone_name=zone_name,
        temp_f=temp_f,
        precip_1h_mm=data.get("rain", {}).get("1h", 0.0),
        condition=w["description"],
        wind_speed_mph=wind_mph,
        humidity_pct=main["humidity"],
        traffic_impact_level=impact,
    )


async def fetch_all_zones(
    client: httpx.AsyncClient,
    api_key: str,
) -> list[WeatherSnapshot]:
    """
    Fetch all five Austin weather zones concurrently.

    Individual zone failures are logged and skipped so a single bad
    API response never aborts the entire weather collection.

    Returns:
        List of WeatherSnapshot objects (0–5 items).
    """
    tasks = [
        _fetch_zone(client, api_key, name, lat, lon)
        for name, (lat, lon) in AUSTIN_WEATHER_ZONES.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    snapshots: list[WeatherSnapshot] = []
    for zone_name, result in zip(AUSTIN_WEATHER_ZONES, results):
        if isinstance(result, Exception):
            logger.warning("weather zone %s failed: %s", zone_name, result)
        else:
            snapshots.append(result)

    return snapshots
