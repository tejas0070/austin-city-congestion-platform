from backend.app.models import MergedFeature
from ml.predict import model_loaded, predict


def predict_congestion(reading: MergedFeature) -> dict:
    """
    Runs the ML model against a MergedFeature row and returns the prediction
    along with a human-readable congestion label.
    """
    if not model_loaded():
        return {
            "predicted_congestion_index": None,
            "congestion_label": "unavailable",
            "model_ready": False,
        }

    features = {
        "current_speed_mph": reading.current_speed_mph,
        "free_flow_speed_mph": reading.free_flow_speed_mph,
        "weather_temp_f": reading.weather_temp_f,
        "weather_humidity_pct": reading.weather_humidity_pct,
        "weather_wind_speed_mph": reading.weather_wind_speed_mph,
        "weather_cloud_cover_pct": reading.weather_cloud_cover_pct,
        "weather_rain_1h_mm": reading.weather_rain_1h_mm,
        "nearby_event_count": reading.nearby_event_count,
        "hour_of_day": reading.hour_of_day,
        "day_of_week": reading.day_of_week,
        "is_weekend": reading.is_weekend,
        "weather_traffic_impact_level": reading.weather_traffic_impact_level,
    }

    index = predict(features)
    label = _label(index)
    return {
        "predicted_congestion_index": index,
        "congestion_label": label,
        "model_ready": True,
    }


def _label(index: float) -> str:
    if index < 0.2:
        return "Free Flow"
    if index < 0.4:
        return "Light"
    if index < 0.6:
        return "Moderate"
    if index < 0.8:
        return "Heavy"
    return "Severe"
