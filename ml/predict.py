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
import pandas as pd

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


def _build_row(features: dict[str, Any]) -> pd.DataFrame:
    """Builds the feature DataFrame used by both predict() and predict_with_confidence()."""
    _load_artifacts()
    impact_enc = _encoder.transform([features.get("weather_traffic_impact_level", "Low")])[0]
    return pd.DataFrame([{
        "current_speed_mph":                features.get("current_speed_mph", 0),
        "free_flow_speed_mph":              features.get("free_flow_speed_mph", 0),
        "weather_temp_f":                   features.get("weather_temp_f", 75),
        "weather_humidity_pct":             features.get("weather_humidity_pct", 50),
        "weather_wind_speed_mph":           features.get("weather_wind_speed_mph", 0),
        "weather_cloud_cover_pct":          features.get("weather_cloud_cover_pct", 0),
        "weather_rain_1h_mm":               features.get("weather_rain_1h_mm", 0),
        "nearby_event_count":               features.get("nearby_event_count", 0),
        "hour_of_day":                      features.get("hour_of_day", 12),
        "day_of_week":                      features.get("day_of_week", 0),
        "is_weekend":                       features.get("is_weekend", 0),
        "weather_traffic_impact_level_enc": impact_enc,
    }])


def predict(features: dict[str, Any]) -> float:
    """Predicts congestion_index (0.0–1.0) for a single corridor snapshot."""
    row = _build_row(features)
    return round(max(0.0, min(1.0, float(_model.predict(row)[0]))), 4)


def predict_with_confidence(
    features: dict[str, Any],
) -> tuple[float, float, float]:
    """Returns (index, confidence_low, confidence_high) using RF tree std deviation.

    The standard deviation across all individual tree predictions gives a natural
    uncertainty band without requiring a separate calibration step.
    """
    row = _build_row(features)
    tree_preds = np.array([tree.predict(row)[0] for tree in _model.estimators_])
    mean = float(np.mean(tree_preds))
    std = float(np.std(tree_preds))
    low = round(max(0.0, mean - std), 4)
    high = round(min(1.0, mean + std), 4)
    return round(max(0.0, min(1.0, mean)), 4), low, high


def model_loaded() -> bool:
    try:
        _load_artifacts()
        return True
    except FileNotFoundError:
        return False
