"""City-wide corridor congestion prediction served from the trained ML model.

Loads data/models/congestion_model.pkl (built by scripts/train_model.py), then
for a requested future time builds the same feature rows used in training and
returns predicted congestion as GeoJSON LineStrings for every Austin segment.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import pandas as pd

from ..utils.cache import get_cache, set_cache
from ..utils.geojson_builder import build_feature_collection, build_line_feature
from .congestion_features import (
    FEATURE_ORDER,
    WEATHER_PROFILES,
    build_feature_row,
    congestion_level,
)
from .segments_service import load_segments

MODEL_PATH = Path(__file__).resolve().parents[2] / "data" / "models" / "congestion_model.pkl"
META_PATH = Path(__file__).resolve().parents[2] / "data" / "models" / "model_meta.json"

_PREDICTION_CACHE_TTL = 90  # seconds
_DEFAULT_ATTENDANCE = 5000  # for events with no reported attendance

_model = None  # lazy-loaded singleton


def model_is_available() -> bool:
    return MODEL_PATH.exists()


def _load_model():
    global _model
    if _model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model not found at {MODEL_PATH}. Run scripts/train_model.py first."
            )
        _model = joblib.load(MODEL_PATH)
    return _model


def get_model_meta() -> dict:
    if META_PATH.exists():
        return json.loads(META_PATH.read_text(encoding="utf-8"))
    return {}


def _parse_events(raw_events: list[dict]) -> list[dict]:
    """Convert events_service records into the shape the feature code expects."""
    parsed: list[dict] = []
    for ev in raw_events:
        date = ev.get("date", "")
        time = (ev.get("time") or "19:00")[:5]
        try:
            start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        except Exception:
            continue
        lat, lng = ev.get("lat"), ev.get("lng")
        if lat is None or lng is None:
            continue
        parsed.append({
            "lat": float(lat),
            "lng": float(lng),
            "expected_attendance": ev.get("expected_attendance") or _DEFAULT_ATTENDANCE,
            "start_dt": start_dt,
        })
    return parsed


async def predict_segments(
    hours_ahead: float = 2.0,
    include_events: bool = True,
) -> dict:
    """Predict city-wide congestion at now + hours_ahead using the ML model.

    Returns a GeoJSON FeatureCollection of segment LineStrings coloured by
    predicted congestion.
    """
    cache_key = f"ml_pred_{hours_ahead}_{include_events}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    model = _load_model()
    target_dt = datetime.now() + timedelta(hours=hours_ahead)

    # Weather for the window (current conditions as a short-horizon proxy).
    from .weather_service import fetch_current_weather
    weather = await fetch_current_weather()
    condition = weather.get("condition", "Clear")
    profile = WEATHER_PROFILES.get(condition, WEATHER_PROFILES["Clear"])
    weather_code = weather.get("weather_code")
    weather_code = profile[0] if weather_code is None else int(weather_code)
    temp_f = weather.get("temperature_f")
    temp_f = profile[1] if temp_f is None else float(temp_f)
    precip_in = weather.get("precipitation_in")
    precip_in = profile[2] if precip_in is None else float(precip_in)

    events: list[dict] = []
    if include_events:
        from .events_service import fetch_upcoming_events
        events = _parse_events(await fetch_upcoming_events(days=7))

    segments = load_segments()
    if not segments:
        return build_feature_collection([])

    rows = [
        build_feature_row(seg, target_dt, weather_code, temp_f, precip_in, events)
        for seg in segments
    ]
    frame = pd.DataFrame(rows)[FEATURE_ORDER]
    predictions = model.predict(frame)

    features: list[dict] = []
    for seg, row, pct in zip(segments, rows, predictions):
        pct = float(max(0.0, min(100.0, pct)))
        level, index = congestion_level(pct)
        features.append(build_line_feature(seg["coords"], {
            "segment_id": seg["segment_id"],
            "road_name": seg["name"],
            "road_class": seg["road_class"],
            "congestion_pct": round(pct, 1),
            "congestion_level": level,
            "congestion_index": index,
            "nearby_event_attendance": row["nearby_event_attendance"],
            "hours_ahead": hours_ahead,
            "predicted_for": target_dt.isoformat(timespec="minutes"),
        }))

    result = build_feature_collection(features)
    # Top-level timestamps so the UI can label the layer with when it was
    # computed and the future time it predicts for.
    result["generated_at"] = datetime.now().isoformat(timespec="seconds")
    result["predicted_for"] = target_dt.isoformat(timespec="minutes")
    result["hours_ahead"] = hours_ahead
    set_cache(cache_key, result, _PREDICTION_CACHE_TTL)
    return result
