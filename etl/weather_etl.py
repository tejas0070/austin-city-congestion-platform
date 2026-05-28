import os
import pandas as pd
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load .env from the project root (one level up from /etl)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# OpenWeatherMap Current Weather API
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

# Austin districts to monitor for weather impact on traffic
# Weather conditions like rain, fog, and extreme heat significantly affect driving behavior
AUSTIN_WEATHER_ZONES = {
    "Downtown_Austin":     (30.2672, -97.7431),
    "North_Austin":        (30.4087, -97.7198),
    "South_Austin":        (30.2242, -97.7561),
    "East_Austin":         (30.2583, -97.6987),
    "West_Austin":         (30.2965, -97.8004),
}

# Weather condition codes that are known to negatively impact traffic flow
ADVERSE_CONDITION_CODES = {
    range(200, 300): "Thunderstorm",
    range(300, 400): "Drizzle",
    range(500, 600): "Rain",
    range(600, 700): "Snow/Ice",
    range(700, 800): "Low Visibility (Fog/Smoke/Haze)",
}

def classify_weather_impact(condition_id: int, wind_speed_mph: float, temp_f: float) -> str:
    """
    Classifies the traffic impact level of current weather conditions.
    
    Returns: 'Low', 'Moderate', 'High', or 'Severe'
    """
    is_adverse = any(condition_id in r for r in ADVERSE_CONDITION_CODES)
    
    if condition_id in range(200, 300) or wind_speed_mph > 40:
        return "Severe"
    elif condition_id in range(500, 600) or condition_id in range(600, 700):
        return "High"
    elif is_adverse or wind_speed_mph > 25 or temp_f > 105 or temp_f < 25:
        return "Moderate"
    else:
        return "Low"


def fetch_weather_data():
    """
    Fetches current weather conditions from OpenWeatherMap across key Austin zones,
    classifies the estimated traffic impact per zone, and saves to a timestamped CSV.
    """
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key or "actual" in api_key or api_key == "your_actual_weather_key_here":
        print("[-] Error: A valid 'OPENWEATHER_API_KEY' must be configured in your .env file.")
        print("    Get a free key at: https://openweathermap.org/api")
        return False

    print(f"[{datetime.now()}] Fetching weather conditions across Austin zones from OpenWeatherMap...")

    records = []

    for zone_name, (lat, lon) in AUSTIN_WEATHER_ZONES.items():
        print(f" -> Fetching weather for {zone_name} ({lat}, {lon})...")

        params = {
            "lat":   lat,
            "lon":   lon,
            "appid": api_key,
            "units": "imperial",  # Fahrenheit, MPH
        }

        try:
            response = requests.get(OPENWEATHER_URL, params=params, timeout=10)
            response.raise_for_status()
            d = response.json()

            condition_id = d["weather"][0]["id"]
            condition_desc = d["weather"][0]["description"]
            temp_f = d["main"]["temp"]
            feels_like_f = d["main"]["feels_like"]
            humidity_pct = d["main"]["humidity"]
            visibility_m = d.get("visibility", None)  # Meters, not always present
            visibility_mi = round(visibility_m / 1609.34, 2) if visibility_m else None
            wind_speed_mph = d["wind"]["speed"]
            wind_gust_mph = d["wind"].get("gust", None)
            rain_1h_mm = d.get("rain", {}).get("1h", 0.0)
            snow_1h_mm = d.get("snow", {}).get("1h", 0.0)
            cloud_cover_pct = d["clouds"]["all"]
            sunrise = datetime.fromtimestamp(d["sys"]["sunrise"]).isoformat()
            sunset = datetime.fromtimestamp(d["sys"]["sunset"]).isoformat()

            impact = classify_weather_impact(condition_id, wind_speed_mph, temp_f)

            record = {
                "timestamp":           datetime.now().isoformat(),
                "zone_name":           zone_name,
                "latitude":            lat,
                "longitude":           lon,
                "condition_id":        condition_id,
                "condition":           condition_desc,
                "temp_f":              temp_f,
                "feels_like_f":        feels_like_f,
                "humidity_pct":        humidity_pct,
                "visibility_mi":       visibility_mi,
                "wind_speed_mph":      wind_speed_mph,
                "wind_gust_mph":       wind_gust_mph,
                "rain_1h_mm":          rain_1h_mm,
                "snow_1h_mm":          snow_1h_mm,
                "cloud_cover_pct":     cloud_cover_pct,
                "sunrise":             sunrise,
                "sunset":              sunset,
                "traffic_impact_level": impact,
            }
            records.append(record)
            print(f"    [+] {condition_desc} | {temp_f}°F | Wind: {wind_speed_mph} mph | "
                  f"Traffic Impact: {impact}")

        except Exception as e:
            print(f"   [!] Error fetching weather for {zone_name}: {e}")

    if not records:
        print("[-] No weather records collected. Aborting save.")
        return False

    df = pd.DataFrame(records)

    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(output_dir, f"weather_conditions_{timestamp}.csv")

    df.to_csv(file_path, index=False)
    print(f"\n[+] Saved weather data for {len(df)} Austin zones to {os.path.abspath(file_path)}")
    return True


if __name__ == "__main__":
    fetch_weather_data()
