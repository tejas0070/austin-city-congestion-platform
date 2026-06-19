from datetime import date, datetime

import httpx
from ..utils.cache import get_cache, set_cache

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
AUSTIN_LAT = 30.2672
AUSTIN_LNG = -97.7431
CACHE_TTL = 900   # 15 minutes
CACHE_KEY = "weather_current"

# Open-Meteo serves at most 16 forecast days (today + 15).
FORECAST_HORIZON_DAYS = 15
AUSTIN_TZ = "America/Chicago"

WEATHER_CODE_MAP: dict[int, str] = {
    0: "Clear",
    1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy Fog",
    51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
    61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
    71: "Light Snow", 73: "Snow", 75: "Heavy Snow",
    80: "Rain Showers", 81: "Rain Showers", 82: "Heavy Rain Showers",
    95: "Thunderstorm", 96: "Thunderstorm with Hail", 99: "Thunderstorm with Hail",
}


async def fetch_current_weather() -> dict:
    """Return current Austin weather from Open-Meteo, cached 15 min."""
    cached = get_cache(CACHE_KEY)
    if cached:
        return cached

    error = False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(OPEN_METEO_URL, params={
                "latitude": AUSTIN_LAT,
                "longitude": AUSTIN_LNG,
                "current": "temperature_2m,precipitation,wind_speed_10m,weather_code",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
            })
            resp.raise_for_status()
            current = resp.json()["current"]
        result = {
            "temperature_f": current.get("temperature_2m"),
            "precipitation_in": current.get("precipitation"),
            "wind_speed_mph": current.get("wind_speed_10m"),
            "weather_code": current.get("weather_code"),
            "condition": WEATHER_CODE_MAP.get(current.get("weather_code", 0), "Unknown"),
            "rain_alert": (current.get("precipitation") or 0) > 0.004,
        }
    except Exception:
        error = True
        result = {
            "temperature_f": 78.0,
            "precipitation_in": 0.0,
            "wind_speed_mph": 10.0,
            "weather_code": 0,
            "condition": "Clear",
            "rain_alert": False,
        }

    set_cache(CACHE_KEY, result, 30 if error else CACHE_TTL)
    return result


async def fetch_hourly_forecast(target_date: date) -> dict | None:
    """Hourly Open-Meteo forecast for a local Austin date.

    Returns ``{hour 0-23: {weather_code, temperature_f, precipitation_in, condition}}``
    when ``target_date`` falls within the ~16-day forecast horizon, otherwise ``None``.
    Cached 15 min. Returns ``None`` silently on error or out-of-horizon so callers can
    fall back to the current-weather proxy.
    """
    days_ahead = (target_date - datetime.now().date()).days
    if days_ahead < 0 or days_ahead > FORECAST_HORIZON_DAYS:
        return None

    cache_key = f"weather_hourly_{target_date.isoformat()}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(OPEN_METEO_URL, params={
                "latitude": AUSTIN_LAT,
                "longitude": AUSTIN_LNG,
                "hourly": "temperature_2m,precipitation,weather_code",
                "temperature_unit": "fahrenheit",
                "precipitation_unit": "inch",
                "timezone": AUSTIN_TZ,
                "forecast_days": 16,
            })
            resp.raise_for_status()
            hourly = resp.json().get("hourly", {})
    except Exception:
        return None

    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    precs = hourly.get("precipitation", [])
    codes = hourly.get("weather_code", [])
    target_str = target_date.isoformat()

    result: dict[int, dict] = {}
    for i, t in enumerate(times):
        if not t.startswith(target_str):
            continue
        hour = int(t[11:13])
        code = codes[i] if i < len(codes) else 0
        result[hour] = {
            "weather_code": code,
            "temperature_f": temps[i] if i < len(temps) else None,
            "precipitation_in": precs[i] if i < len(precs) else None,
            "condition": WEATHER_CODE_MAP.get(code or 0, "Unknown"),
        }

    if not result:
        return None

    set_cache(cache_key, result, CACHE_TTL)
    return result


ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_historical_weather(start_date: str, end_date: str) -> dict[str, dict]:
    """Hourly Open-Meteo ARCHIVE weather for a past date range (offline/ETL use).

    Returns ``{ "YYYY-MM-DDTHH": {weather_code, temperature_f, precipitation_in} }``.
    Synchronous (httpx.Client) because the ETL script is synchronous. Returns {}
    on error so the caller can fall back to a neutral profile.
    """
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(ARCHIVE_URL, params={
                "latitude": AUSTIN_LAT,
                "longitude": AUSTIN_LNG,
                "start_date": start_date,
                "end_date": end_date,
                "hourly": "temperature_2m,precipitation,weather_code",
                "temperature_unit": "fahrenheit",
                "precipitation_unit": "inch",
                "timezone": AUSTIN_TZ,
            })
            resp.raise_for_status()
            hourly = resp.json().get("hourly", {})
    except Exception:
        return {}

    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    precs = hourly.get("precipitation", [])
    codes = hourly.get("weather_code", [])
    out: dict[str, dict] = {}
    for i, t in enumerate(times):
        key = t[:13]  # "YYYY-MM-DDTHH"
        out[key] = {
            "weather_code": codes[i] if i < len(codes) else 0,
            "temperature_f": temps[i] if i < len(temps) else 78.0,
            "precipitation_in": precs[i] if i < len(precs) else 0.0,
        }
    return out
