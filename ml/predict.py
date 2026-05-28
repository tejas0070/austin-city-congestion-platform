"""
ML Inference — Austin City Congestion Platform

Loads the trained model from ml/models/ and exposes a single predict() function
for the FastAPI backend to call.  The model is loaded once at module import
to avoid per-request disk reads.
"""

import os
from typing import Any

import joblib
import numpy as np

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODELS_DIR, "congestion_rf.joblib")
ENCODER_PATH = os.path.join(MODELS_DIR, "impact_encoder.joblib")

_model = None
_encoder = None


def _load_artifacts() -> None:
    global _model, _encoder
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Model not found at {MODEL_PATH}. Run ml/train.py first."
            )
        _model = joblib.load(MODEL_PATH)
        _encoder = joblib.load(ENCODER_PATH)


def predict(features: dict[str, Any]) -> float:
    """
    Predicts the congestion_index (0.0–1.0) for a single corridor snapshot.

    Required keys in `features`:
        current_speed_mph, free_flow_speed_mph, weather_temp_f,
        weather_humidity_pct, weather_wind_speed_mph, weather_cloud_cover_pct,
        weather_rain_1h_mm, nearby_event_count, hour_of_day, day_of_week,
        is_weekend, weather_traffic_impact_level
    """
    _load_artifacts()

    impact_enc = _encoder.transform([features.get("weather_traffic_impact_level", "Low")])[0]

    row = np.array([[
        features.get("current_speed_mph", 0),
        features.get("free_flow_speed_mph", 0),
        features.get("weather_temp_f", 75),
        features.get("weather_humidity_pct", 50),
        features.get("weather_wind_speed_mph", 0),
        features.get("weather_cloud_cover_pct", 0),
        features.get("weather_rain_1h_mm", 0),
        features.get("nearby_event_count", 0),
        features.get("hour_of_day", 12),
        features.get("day_of_week", 0),
        features.get("is_weekend", 0),
        impact_enc,
    ]])

    prediction = float(_model.predict(row)[0])
    return round(max(0.0, min(1.0, prediction)), 4)


def model_loaded() -> bool:
    try:
        _load_artifacts()
        return True
    except FileNotFoundError:
        return False
