"""City-wide corridor congestion prediction served from the trained ML model.

Loads data/models/congestion_model.pkl (built by scripts/train_model.py), then
for a requested future time builds the same feature rows used in training and
returns predicted congestion as GeoJSON LineStrings for every Austin segment.
"""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import joblib
import pandas as pd

from ..etl.confidence import clamp_interval, confidence_label, width_to_confidence
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
QUANTILES_PATH = Path(__file__).resolve().parents[2] / "data" / "models" / "congestion_quantiles.pkl"

_PREDICTION_CACHE_TTL = 90  # seconds
_DAY_CACHE_TTL = 900  # 15 min — long enough to amortize 24 predictions, short
                      # enough that a proxy day upgrades to forecast as it nears
_DEFAULT_ATTENDANCE = 5000  # for events with no reported attendance

_model = None  # lazy-loaded singleton
_quantiles = None  # lazy-loaded {"q10": pipe, "q90": pipe}


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


def quantiles_are_available() -> bool:
    return QUANTILES_PATH.exists()


def _load_quantiles():
    global _quantiles
    if _quantiles is None and QUANTILES_PATH.exists():
        _quantiles = joblib.load(QUANTILES_PATH)
    return _quantiles


def _width_anchors() -> tuple[float, float]:
    meta = get_model_meta().get("width_anchors", {})
    return float(meta.get("p5", 5.0)), float(meta.get("p95", 40.0))


def _segment_confidences(rows: list[dict]) -> list[tuple[float, float, float]] | None:
    """Per-segment (low, high, confidence) from the q10/q90 interval widths.

    Returns one tuple per row, or None when quantile models are unavailable (so
    callers degrade to predictions without a confidence signal). Confidence is
    the single source of truth shared by the single-time, whole-day, and
    whole-week paths.
    """
    if not rows or not quantiles_are_available():
        return None
    quants = _load_quantiles()
    if quants is None:
        return None
    frame = pd.DataFrame(rows)[FEATURE_ORDER]
    low_preds = quants["q10"].predict(frame)
    high_preds = quants["q90"].predict(frame)
    w_low, w_high = _width_anchors()
    out: list[tuple[float, float, float]] = []
    for lo_raw, hi_raw in zip(low_preds, high_preds):
        lo, hi = clamp_interval(float(lo_raw), float(hi_raw))
        out.append((lo, hi, width_to_confidence(hi - lo, w_low, w_high)))
    return out


def _mean_confidence(confidences: list[float]) -> float:
    """City-wide average confidence (rounded to 0.1) over a list of segments."""
    return round(sum(confidences) / len(confidences), 1) if confidences else 0.0


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

    # The model inference + GeoJSON assembly are CPU-bound and synchronous; run
    # them off the event loop so concurrent requests (model info, the day/week
    # panels) are not starved while one prediction is computed.
    return await asyncio.to_thread(
        _build_datetime_fc, target_dt, code, temp_f, precip_in, events
    )


def _build_datetime_fc(
    target_dt: datetime,
    code: int,
    temp_f: float,
    precip_in: float,
    events: list[dict],
) -> dict:
    """Synchronous core of predict_for_datetime (runs in a worker thread)."""
    segments, rows, predictions = _run_predictions(target_dt, code, temp_f, precip_in, events)

    intervals = _segment_confidences(rows)

    confidences: list[float] = []
    features: list[dict] = []
    for i, (seg, row, pct) in enumerate(zip(segments, rows, predictions)):
        pct = float(max(0.0, min(100.0, pct)))
        level, index = congestion_level(pct)
        props = {
            "segment_id": seg["segment_id"],
            "road_name": seg["name"],
            "road_class": seg["road_class"],
            "congestion_pct": round(pct, 1),
            "congestion_level": level,
            "congestion_index": index,
            "nearby_event_attendance": row["nearby_event_attendance"],
            "predicted_for": target_dt.isoformat(timespec="minutes"),
        }
        if intervals is not None:
            lo, hi, conf = intervals[i]
            confidences.append(conf)
            props.update({
                "congestion_low": round(lo, 1),
                "congestion_high": round(hi, 1),
                "confidence_pct": conf,
                "confidence_label": confidence_label(conf),
            })
        features.append(build_line_feature(seg["coords"], props))

    result = build_feature_collection(features)
    result["generated_at"] = datetime.now().isoformat(timespec="seconds")
    result["predicted_for"] = target_dt.isoformat(timespec="minutes")
    if confidences:
        avg = _mean_confidence(confidences)
        result["confidence_avg"] = avg
        result["confidence_label"] = confidence_label(avg)
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


_geometry_fc_cache: dict | None = None


def _segments_geometry_fc() -> dict:
    """GeoJSON of segment geometry + static props only (sent once per day response).

    Memoized: the segment network is static, so building the ~3,800-feature
    collection once and reusing it avoids rebuilding it on every day prediction
    (the week path would otherwise rebuild it 7×).
    """
    global _geometry_fc_cache
    if _geometry_fc_cache is None:
        features = [
            build_line_feature(seg["coords"], {
                "segment_id": seg["segment_id"],
                "road_name": seg["name"],
                "road_class": seg["road_class"],
            })
            for seg in load_segments()
        ]
        _geometry_fc_cache = build_feature_collection(features)
    return _geometry_fc_cache


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

    # All 24 hours of model inference are CPU-bound; compute them in a worker
    # thread so the event loop stays responsive to other requests.
    result = await asyncio.to_thread(
        _compute_day, target_date, current, forecast, events
    )
    set_cache(cache_key, result, _DAY_CACHE_TTL)
    return result


def _compute_day(
    target_date: date,
    current: dict,
    forecast: dict | None,
    events: list[dict],
) -> dict:
    """Synchronous core of predict_day (runs in a worker thread)."""
    hours_meta: list[dict] = []
    series: list[list[int]] = []
    sources: set[str] = set()
    hourly_confidences: list[float] = []  # one city-wide average per hour
    hourly_congestions: list[float] = []  # one city-wide congestion avg per hour

    for hour in range(24):
        hour_dt = datetime(target_date.year, target_date.month, target_date.day, hour)
        if forecast and hour in forecast:
            weather, source = forecast[hour], "forecast"
        else:
            weather, source = current, "proxy"
        sources.add(source)

        code, temp_f, precip_in, condition = _resolve_weather(weather)
        _, rows, predictions = _run_predictions(hour_dt, code, temp_f, precip_in, events)

        indices: list[int] = []
        total_pct = 0.0
        for pct in predictions:
            pct = float(max(0.0, min(100.0, pct)))
            _, index = congestion_level(pct)
            indices.append(index)
            total_pct += pct
        avg_pct = round(total_pct / len(predictions), 1) if len(predictions) else 0.0
        avg_level, _ = congestion_level(avg_pct)
        hourly_congestions.append(avg_pct)

        series.append(indices)
        meta = {
            "hour": hour,
            "label": _hour_label(hour),
            "predicted_for": hour_dt.isoformat(timespec="minutes"),
            "avg_pct": avg_pct,
            "avg_level": avg_level,
            "temperature_f": round(temp_f, 1),
            "condition": condition,
            "weather_source": source,
        }

        intervals = _segment_confidences(rows)
        if intervals is not None:
            hour_conf = _mean_confidence([conf for _, _, conf in intervals])
            hourly_confidences.append(hour_conf)
            meta["confidence_avg"] = hour_conf
            meta["confidence_label"] = confidence_label(hour_conf)

        hours_meta.append(meta)

    weather_source = "mixed" if len(sources) > 1 else next(iter(sources), "proxy")
    result = {
        "date": target_date.isoformat(),
        "weather_source": weather_source,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "segments": _segments_geometry_fc(),
        "hours": hours_meta,
        "series": series,
    }
    # Whole-day confidence = mean of the 24 hourly city-wide averages. Each hour
    # is weighted equally, so the day score reflects the average across time.
    if hourly_confidences:
        day_avg = _mean_confidence(hourly_confidences)
        result["confidence_avg"] = day_avg
        result["confidence_label"] = confidence_label(day_avg)
    # Whole-day congestion = mean of the 24 hourly city-wide congestion averages.
    if hourly_congestions:
        cong_avg = round(sum(hourly_congestions) / len(hourly_congestions), 1)
        result["congestion_avg"] = cong_avg
        result["congestion_level"] = congestion_level(cong_avg)[0]
    return result


_WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday",
                  "Friday", "Saturday", "Sunday")
_WEEK_LENGTH = 7


async def predict_week(start_date: date, include_events: bool = True) -> dict:
    """Aggregate whole-day confidence across the 7 days starting at start_date.

    Reuses predict_day per day (so each day's own 15-min cache is shared with the
    day-preview view), then averages the daily confidence scores into one
    Mon..Sun-style week summary. The payload is intentionally compact — daily
    summaries only, no geometry — so the week view stays cheap to fetch.
    """
    _load_model()  # surface FileNotFoundError before doing work

    days: list[dict] = []
    daily_confidences: list[float] = []
    daily_congestions: list[float] = []
    for offset in range(_WEEK_LENGTH):
        target = start_date + timedelta(days=offset)
        day = await predict_day(target, include_events=include_events)
        entry = {
            "date": target.isoformat(),
            "weekday": _WEEKDAY_NAMES[target.weekday()],
            "weather_source": day.get("weather_source"),
        }
        if "confidence_avg" in day:
            entry["confidence_avg"] = day["confidence_avg"]
            entry["confidence_label"] = day["confidence_label"]
            daily_confidences.append(day["confidence_avg"])
        if "congestion_avg" in day:
            entry["congestion_avg"] = day["congestion_avg"]
            entry["congestion_level"] = day["congestion_level"]
            daily_congestions.append(day["congestion_avg"])
        days.append(entry)

    result = {
        "start_date": start_date.isoformat(),
        "end_date": (start_date + timedelta(days=_WEEK_LENGTH - 1)).isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "days": days,
    }
    if daily_confidences:
        week_avg = _mean_confidence(daily_confidences)
        result["confidence_avg"] = week_avg
        result["confidence_label"] = confidence_label(week_avg)
    if daily_congestions:
        week_cong = round(sum(daily_congestions) / len(daily_congestions), 1)
        result["congestion_avg"] = week_cong
        result["congestion_level"] = congestion_level(week_cong)[0]
    return result


async def warm_caches() -> None:
    """Precompute the predictions the UI loads first — the +2h forecast, today's
    whole day, and the current Mon–Sun week — so the first page load hits warm
    caches instead of waiting on cold, CPU-bound inference. Best-effort: any
    failure is swallowed so it can never block or crash startup.
    """
    if not model_is_available():
        return
    try:
        await predict_segments(hours_ahead=2.0)
        today = date.today()
        await predict_day(today)
        monday = today - timedelta(days=today.weekday())
        await predict_week(monday)
    except Exception:  # noqa: BLE001 - warming is best-effort
        pass
