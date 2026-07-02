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

from ..etl.confidence import (
    absolute_width_anchors,
    apply_density_cap,
    clamp_interval,
    confidence_label,
    conformal_interval,
    expected_value_anchors,
    expected_value_interval,
    modulated_half_width,
    width_to_confidence,
)
from ..etl.event_impact import event_congestion_uplift
from ..etl.holiday_impact import holiday_congestion_multiplier
from ..utils.cache import get_cache, set_cache
from ..utils.clock import austin_now, austin_today
from ..utils.geojson_builder import build_feature_collection, build_line_feature
from .congestion_features import (
    FEATURE_ORDER,
    WEATHER_PROFILES,
    build_feature_row,
    congestion_level,
    weather_congestion_multiplier,
)
from .segments_service import load_display_segments

MODEL_PATH = Path(__file__).resolve().parents[2] / "data" / "models" / "congestion_model.pkl"
META_PATH = Path(__file__).resolve().parents[2] / "data" / "models" / "model_meta.json"
QUANTILES_PATH = Path(__file__).resolve().parents[2] / "data" / "models" / "congestion_quantiles.pkl"
SEASONAL_PRIOR_PATH = Path(__file__).resolve().parents[2] / "data" / "models" / "seasonal_prior.json"

_PREDICTION_CACHE_TTL = 90  # seconds
_DAY_CACHE_TTL = 900  # 15 min — long enough to amortize 24 predictions, short
                      # enough that a proxy day upgrades to forecast as it nears
_DEFAULT_ATTENDANCE = 5000  # for events with no reported attendance

_model = None  # lazy-loaded singleton
_quantiles = None  # lazy-loaded {"low": pipe, "high": pipe}
_seasonal_prior = None  # lazy-loaded {"by_segment":..., "by_road_class":..., "global":...}
# Artifact modification times at load — used to hot-reload after a retrain so the
# running API picks up the self-updater's new model without a restart.
_mtimes: dict[str, float] = {}


def _file_changed(path) -> bool:
    """True if `path` exists and its mtime differs from when we last loaded it."""
    if not path.exists():
        return False
    mtime = path.stat().st_mtime
    if _mtimes.get(str(path)) != mtime:
        _mtimes[str(path)] = mtime
        return True
    return False


def _load_seasonal_prior() -> dict:
    """Load the seasonal-prior artifact (real per-segment hour-of-week congestion).

    Returns an empty structure when the artifact is absent, so predictions fall
    back to the formula-based base_pattern for `seasonal_level`.
    """
    global _seasonal_prior
    if _seasonal_prior is None or _file_changed(SEASONAL_PRIOR_PATH):
        if SEASONAL_PRIOR_PATH.exists():
            _seasonal_prior = json.loads(SEASONAL_PRIOR_PATH.read_text(encoding="utf-8"))
        else:
            _seasonal_prior = {"by_segment": {}, "by_road_class": {}, "global": None}
    return _seasonal_prior


def _resolve_seasonal(segment: dict, target_dt: datetime) -> tuple[float | None, str, int]:
    """Resolve (level, support_tier, support_count) for this segment & hour-of-week.

    Tier 1 "segment": this exact segment's real history (count = readings backing
    it). Tier 2 "road_class": its road-class average. Tier 3 "global": the city
    mean. The tier+count drive the density-aware confidence cap (lever 2) so a
    road can't read more confident than the data supporting it.
    """
    prior = _load_seasonal_prior()
    key = f"{target_dt.hour}_{1 if target_dt.weekday() >= 5 else 0}"
    seg_id = str(segment.get("segment_id"))
    by_seg = prior.get("by_segment", {}).get(seg_id)
    if by_seg and key in by_seg:
        # Default 0 (not 1) when the support count is missing: a segment with a
        # seasonal level but no recorded observation count must not silently earn
        # confidence above the road-class fallback cap.
        count = prior.get("support", {}).get("by_segment", {}).get(seg_id, {}).get(key, 0)
        return by_seg[key], "segment", int(count)
    by_rc = prior.get("by_road_class", {}).get(segment.get("road_class"))
    if by_rc and key in by_rc:
        return by_rc[key], "road_class", 0
    return prior.get("global"), "global", 0


def model_is_available() -> bool:
    return MODEL_PATH.exists()


def _load_model():
    global _model
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}. Run scripts/train_model.py first."
        )
    if _model is None or _file_changed(MODEL_PATH):
        _model = joblib.load(MODEL_PATH)
        # A new model invalidates cached predictions from the old one.
        from ..utils.cache import clear_cache
        clear_cache()
    return _model


def get_model_meta() -> dict:
    if META_PATH.exists():
        return json.loads(META_PATH.read_text(encoding="utf-8"))
    return {}


def quantiles_are_available() -> bool:
    return QUANTILES_PATH.exists()


def _load_quantiles():
    global _quantiles
    if QUANTILES_PATH.exists() and (_quantiles is None or _file_changed(QUANTILES_PATH)):
        _quantiles = joblib.load(QUANTILES_PATH)
    return _quantiles


def _width_anchors() -> tuple[float, float]:
    # Fixed, interpretable anchors (not the model's own width percentiles) so the
    # confidence score is stable across retrains and improves when the model does.
    return absolute_width_anchors()


def _segment_confidences(
    rows: list[dict], predictions=None,
) -> list[tuple[float, float, float]] | None:
    """Per-segment (low, high, confidence) for the displayed prediction.

    Returns one tuple per row, or None when the confidence artifact is missing (so
    callers degrade to predictions without a confidence signal). The density cap
    keyed on each row's support tier/count always applies, so a road can never
    read more confident than the real history backing it. Shared by the
    single-time, whole-day, and whole-week paths.

    Preferred path (lever 3): the EXPECTED-VALUE interval `pred ± ev_q`, calibrated
    so it covers the typical (per corridor x hour-of-week) congestion the app
    actually displays. The calibrated average half-width is then redistributed
    across corridors by each one's learned per-reading spread (`modulated_half_width`)
    so confidence genuinely varies by road and hour instead of being one global
    constant. Falls back to the per-reading 50% band (conformal widened) for older
    artifacts that predate `ev_q`.

    Confidence is derived from the TRUE (unclamped) interval half-width, not the
    width after clipping to [0, 100] — otherwise a near-empty road whose interval
    is clipped at the 0 floor would read spuriously more confident.
    """
    if not rows or not quantiles_are_available():
        return None
    quants = _load_quantiles()
    if quants is None:
        return None
    ev_q = quants.get("ev_q_80") if isinstance(quants, dict) else None
    if ev_q is not None and predictions is not None:
        ev_full, ev_zero = expected_value_anchors()
        ref_width = quants.get("ev_ref_width") if isinstance(quants, dict) else None
        widths = _per_reading_widths(rows, quants) if ref_width else None
        out: list[tuple[float, float, float]] = []
        for i, (pred, row) in enumerate(zip(predictions, rows)):
            width = widths[i] if widths is not None else None
            half = modulated_half_width(float(ev_q), width, ref_width)
            lo, hi = clamp_interval(*expected_value_interval(float(pred), half))
            raw_conf = width_to_confidence(2.0 * half, ev_full, ev_zero)
            tier, count = row.get("_support", ("global", 0))
            out.append((lo, hi, apply_density_cap(raw_conf, tier, count)))
        return out

    # Back-compat: per-reading central 50% band (q25/q75), conformal widened.
    frame = pd.DataFrame(rows)[FEATURE_ORDER]
    low_preds = quants["low"].predict(frame)
    high_preds = quants["high"].predict(frame)
    conformal_q = float(quants.get("conformal_q", 0.0)) if isinstance(quants, dict) else 0.0
    w_low, w_high = _width_anchors()
    out = []
    for lo_raw, hi_raw, row in zip(low_preds, high_preds, rows):
        lo, hi = conformal_interval(float(lo_raw), float(hi_raw), conformal_q)
        raw_conf = width_to_confidence(hi - lo, w_low, w_high)  # true width, pre-clamp
        lo, hi = clamp_interval(lo, hi)
        tier, count = row.get("_support", ("global", 0))
        out.append((lo, hi, apply_density_cap(raw_conf, tier, count)))
    return out


def _per_reading_widths(rows: list[dict], quants: dict) -> list[float] | None:
    """Per-row learned uncertainty: the q75-q25 band width for each feature row.

    This is the model's own estimate of how spread-out readings are for that
    corridor+hour — wider where it is less sure. Returns None (so callers use the
    unmodulated half-width) when the quantile models are absent or fail.
    """
    if not isinstance(quants, dict) or "low" not in quants or "high" not in quants:
        return None
    try:
        frame = pd.DataFrame(rows)[FEATURE_ORDER]
        low_preds = quants["low"].predict(frame)
        high_preds = quants["high"].predict(frame)
    except Exception:  # noqa: BLE001 - degrade to the unmodulated half-width
        return None
    return [abs(float(h) - float(l)) for l, h in zip(low_preds, high_preds)]


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
    weather_mult: float = 1.0,
) -> tuple[list[dict], list[dict], list[float]]:
    """Build feature rows for every segment at target_dt and run the model, then
    apply the weather + event overlays.

    The model itself learns only the BASELINE traffic flow (time, location, road
    class, typical patterns). On top of each baseline prediction we apply the
    weather severity multiplier and add the event-attendance uplift — the two
    educated-guess overlays — so the served congestion is
    `baseline * weather_mult + event_uplift`. Returns (segments, rows, predictions);
    shared by the single-time and whole-day prediction paths.
    """
    segments = load_display_segments()
    if not segments:
        return segments, [], []
    rows = []
    for seg in segments:
        level, tier, count = _resolve_seasonal(seg, target_dt)
        row = build_feature_row(
            seg, target_dt, weather_code, temp_f, precip_in, events,
            seasonal_level=level,
        )
        # Serving-only metadata for the density-aware confidence cap; dropped from
        # the model frame below (it selects FEATURE_ORDER only).
        row["_support"] = (tier, count)
        rows.append(row)
    frame = pd.DataFrame(rows)[FEATURE_ORDER]
    predictions = _load_model().predict(frame)
    # Overlays on the learned baseline flow, none of them learned features — all
    # transparent educated guesses: (1) weather severity and (2) a federal-holiday
    # factor both multiply the baseline (bad weather makes the usual congestion
    # proportionally worse; a holiday trims the commute), and (3) the event surge is
    # added on top. So served congestion = baseline * weather_mult * holiday_mult
    # + event_uplift. Re-centers everything downstream (colour, interval, aggregates)
    # on the overlay-adjusted value. The holiday factor is derived from the date here
    # so every serving path inherits it without extra plumbing.
    holiday_mult = holiday_congestion_multiplier(target_dt)
    adjusted = []
    for pred, row in zip(predictions, rows):
        # Clamp the baseline at 0 before the multipliers so a marginally-negative
        # prediction on a near-empty road can't invert the weather/holiday effect.
        base = max(0.0, float(pred))
        uplift = event_congestion_uplift(row["nearby_event_attendance"])
        row["_event_uplift"] = uplift
        row["_weather_mult"] = weather_mult
        row["_holiday_mult"] = holiday_mult
        adjusted.append(base * weather_mult * holiday_mult + uplift)
    return segments, rows, adjusted


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
    code, temp_f, precip_in, condition = _resolve_weather(weather)

    if events is None:
        events = await _resolve_events(include_events)

    # The model inference + GeoJSON assembly are CPU-bound and synchronous; run
    # them off the event loop so concurrent requests (model info, the day/week
    # panels) are not starved while one prediction is computed.
    return await asyncio.to_thread(
        _build_datetime_fc, target_dt, code, temp_f, precip_in, events, condition
    )


def _build_datetime_fc(
    target_dt: datetime,
    code: int,
    temp_f: float,
    precip_in: float,
    events: list[dict],
    condition: str = "Clear",
) -> dict:
    """Synchronous core of predict_for_datetime (runs in a worker thread)."""
    segments, rows, predictions = _run_predictions(
        target_dt, code, temp_f, precip_in, events,
        weather_congestion_multiplier(condition, temp_f),
    )

    intervals = _segment_confidences(rows, predictions)

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
        if row.get("_event_uplift"):
            # Attribute how much of this segment's congestion is the nearby-event
            # overlay (only present when an event actually affects the road).
            props["event_uplift_pct"] = round(row["_event_uplift"], 1)
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
    result["generated_at"] = austin_now().isoformat(timespec="seconds")
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

    target_dt = austin_now() + timedelta(hours=hours_ahead)
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
            for seg in load_display_segments()
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

    segments = load_display_segments()
    if not segments:
        return {
            "date": target_date.isoformat(),
            "weather_source": "proxy",
            "generated_at": austin_now().isoformat(timespec="seconds"),
            "segments": build_feature_collection([]),
            "hours": [],
            "series": [],
        }

    from .weather_service import fetch_current_weather, fetch_hourly_forecast
    current = await fetch_current_weather()
    forecast = await fetch_hourly_forecast(target_date)

    days_until = (target_date - austin_today()).days
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
        _, rows, predictions = _run_predictions(
            hour_dt, code, temp_f, precip_in, events,
            weather_congestion_multiplier(condition, temp_f),
        )

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

        intervals = _segment_confidences(rows, predictions)
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
        "generated_at": austin_now().isoformat(timespec="seconds"),
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
        "generated_at": austin_now().isoformat(timespec="seconds"),
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
        today = austin_today()
        await predict_day(today)
        monday = today - timedelta(days=today.weekday())
        await predict_week(monday)
    except Exception:  # noqa: BLE001 - warming is best-effort
        pass
