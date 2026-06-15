"""City-wide corridor congestion prediction served from the trained ML model.

Loads data/models/congestion_model.pkl (built by scripts/train_model.py), then
for a requested future time builds the same feature rows used in training and
returns predicted congestion as GeoJSON LineStrings for every Austin segment.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
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
_DAY_CACHE_TTL = 900  # 15 min — long enough to amortize 24 predictions, short
                      # enough that a proxy day upgrades to forecast as it nears
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


def _resolve_weather(weather: dict | None) -> tuple[int, float, float, str]:
    """Normalize a weather dict into (code, temp_f, precip_in, condition).

    Missing fields fall back to the condition's typical profile, so callers can
    pass either a current-weather record or a forecast hour.
    """
    weather = weather or {}
    condition = weather.get("condition", "Clear")
    profile = WEATHER_PROFILES.get(condition, WEATHER_PROFILES["Clear"])
    code = weather.get("weather_code")
    code = profile[0] if code is None else int(code)
    temp = weather.get("temperature_f")
    temp = profile[1] if temp is None else float(temp)
    precip = weather.get("precipitation_in")
    precip = profile[2] if precip is None else float(precip)
    return code, temp, precip, condition


def _run_predictions(
    target_dt: datetime,
    weather_code: int,
    temp_f: float,
    precip_in: float,
    events: list[dict],
) -> tuple[list[dict], list[dict], list[float]]:
    """Build feature rows for every segment at target_dt and run the model.

    Returns (segments, rows, predictions). Shared by the single-time and
    whole-day prediction paths.
    """
    segments = load_segments()
    if not segments:
        return segments, [], []
    rows = [
        build_feature_row(seg, target_dt, weather_code, temp_f, precip_in, events)
        for seg in segments
    ]
    frame = pd.DataFrame(rows)[FEATURE_ORDER]
    predictions = _load_model().predict(frame)
    return segments, rows, predictions


async def _resolve_events(include_events: bool, days: int = 7) -> list[dict]:
    if not include_events:
        return []
    from .events_service import fetch_upcoming_events
    return _parse_events(await fetch_upcoming_events(days=days))


async def predict_for_datetime(
    target_dt: datetime,
    weather: dict | None = None,
    include_events: bool = True,
    events: list[dict] | None = None,
) -> dict:
    """Predict city-wide congestion at an absolute datetime.

    Returns a GeoJSON FeatureCollection of segment LineStrings coloured by
    predicted congestion. `weather`/`events` may be pre-fetched by the caller
    (the whole-day path does this once); otherwise current weather/events are
    fetched here.
    """
    if weather is None:
        from .weather_service import fetch_current_weather
        weather = await fetch_current_weather()
    code, temp_f, precip_in, _ = _resolve_weather(weather)

    if events is None:
        events = await _resolve_events(include_events)

    segments, rows, predictions = _run_predictions(target_dt, code, temp_f, precip_in, events)

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
            "predicted_for": target_dt.isoformat(timespec="minutes"),
        }))

    result = build_feature_collection(features)
    result["generated_at"] = datetime.now().isoformat(timespec="seconds")
    result["predicted_for"] = target_dt.isoformat(timespec="minutes")
    return result


async def predict_segments(
    hours_ahead: float = 2.0,
    include_events: bool = True,
) -> dict:
    """Predict city-wide congestion at now + hours_ahead (back-compat wrapper)."""
    cache_key = f"ml_pred_{hours_ahead}_{include_events}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    target_dt = datetime.now() + timedelta(hours=hours_ahead)
    result = await predict_for_datetime(target_dt, include_events=include_events)
    result["hours_ahead"] = hours_ahead
    set_cache(cache_key, result, _PREDICTION_CACHE_TTL)
    return result


def _hour_label(hour: int) -> str:
    """Format an hour (0-23) as a 12-hour clock label, e.g. 17 -> '5:00 PM'."""
    period = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{hour12}:00 {period}"


def _segments_geometry_fc() -> dict:
    """GeoJSON of segment geometry + static props only (sent once per day response)."""
    features = [
        build_line_feature(seg["coords"], {
            "segment_id": seg["segment_id"],
            "road_name": seg["name"],
            "road_class": seg["road_class"],
        })
        for seg in load_segments()
    ]
    return build_feature_collection(features)


async def predict_day(target_date: date, include_events: bool = True) -> dict:
    """Predict city-wide congestion for all 24 hours of a calendar date.

    Returns a compact payload: geometry once + a per-hour congestion-index matrix
    (`series`) + per-hour metadata (`hours`). Weather uses the real hourly forecast
    when the date is within the forecast horizon, else the current-weather proxy.
    """
    cache_key = f"ml_day_{target_date.isoformat()}_{include_events}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    _load_model()  # surfaces FileNotFoundError before doing work

    segments = load_segments()
    if not segments:
        return {
            "date": target_date.isoformat(),
            "weather_source": "proxy",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "segments": build_feature_collection([]),
            "hours": [],
            "series": [],
        }

    from .weather_service import fetch_current_weather, fetch_hourly_forecast
    current = await fetch_current_weather()
    forecast = await fetch_hourly_forecast(target_date)

    days_until = (target_date - datetime.now().date()).days
    events = await _resolve_events(include_events, days=max(7, days_until + 1))

    hours_meta: list[dict] = []
    series: list[list[int]] = []
    sources: set[str] = set()

    for hour in range(24):
        hour_dt = datetime(target_date.year, target_date.month, target_date.day, hour)
        if forecast and hour in forecast:
            weather, source = forecast[hour], "forecast"
        else:
            weather, source = current, "proxy"
        sources.add(source)

        code, temp_f, precip_in, condition = _resolve_weather(weather)
        _, _, predictions = _run_predictions(hour_dt, code, temp_f, precip_in, events)

        indices: list[int] = []
        total_pct = 0.0
        for pct in predictions:
            pct = float(max(0.0, min(100.0, pct)))
            _, index = congestion_level(pct)
            indices.append(index)
            total_pct += pct
        avg_pct = round(total_pct / len(predictions), 1) if len(predictions) else 0.0
        avg_level, _ = congestion_level(avg_pct)

        series.append(indices)
        hours_meta.append({
            "hour": hour,
            "label": _hour_label(hour),
            "predicted_for": hour_dt.isoformat(timespec="minutes"),
            "avg_pct": avg_pct,
            "avg_level": avg_level,
            "temperature_f": round(temp_f, 1),
            "condition": condition,
            "weather_source": source,
        })

    weather_source = "mixed" if len(sources) > 1 else next(iter(sources), "proxy")
    result = {
        "date": target_date.isoformat(),
        "weather_source": weather_source,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "segments": _segments_geometry_fc(),
        "hours": hours_meta,
        "series": series,
    }
    set_cache(cache_key, result, _DAY_CACHE_TTL)
    return result
