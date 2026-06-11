import httpx
from ..utils.cache import get_cache, set_cache

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
AUSTIN_LAT = 30.2672
AUSTIN_LNG = -97.7431
CACHE_TTL = 900   # 15 minutes
CACHE_KEY = "weather_current"

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
        result = {
            "temperature_f": 78.0,
            "precipitation_in": 0.0,
            "wind_speed_mph": 10.0,
            "weather_code": 0,
            "condition": "Clear",
            "rain_alert": False,
        }

    set_cache(CACHE_KEY, result, CACHE_TTL)
    return result
