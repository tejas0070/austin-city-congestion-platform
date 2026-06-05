"""
Analytics Service — flat, aggregated queries for the Power BI analytics API.

All functions return plain list[dict] with scalar values only (no geometry,
no nested objects) so Power BI's Web connector can parse them without
post-processing.

Queries run against merged_features, which is the denormalised table written
by the ETL cycle and is the authoritative analytics source.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Integer, case, cast, func
from sqlalchemy.orm import Session

from backend.app.models import CachedPrediction, MergedFeature

_DAY_NAMES = {
    0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
    4: "Friday", 5: "Saturday", 6: "Sunday",
}


def _f(val, ndigits: int = 4):
    """Round a nullable float result from SQLAlchemy to ndigits decimal places."""
    return round(float(val), ndigits) if val is not None else None


def get_congestion_by_hour(db: Session) -> list[dict[str, Any]]:
    """Average congestion and speed grouped by corridor × hour_of_day × day_of_week."""
    rows = (
        db.query(
            MergedFeature.corridor_name,
            MergedFeature.hour_of_day,
            MergedFeature.day_of_week,
            func.avg(MergedFeature.congestion_index).label("avg_congestion"),
            func.avg(MergedFeature.current_speed_mph).label("avg_speed_mph"),
            func.count().label("sample_count"),
        )
        .filter(MergedFeature.congestion_index.isnot(None))
        .group_by(
            MergedFeature.corridor_name,
            MergedFeature.hour_of_day,
            MergedFeature.day_of_week,
        )
        .order_by(
            MergedFeature.corridor_name,
            MergedFeature.day_of_week,
            MergedFeature.hour_of_day,
        )
        .all()
    )
    return [
        {
            "corridor_name": r.corridor_name,
            "hour_of_day": r.hour_of_day,
            "day_of_week": r.day_of_week,
            "day_name": _DAY_NAMES.get(r.day_of_week, "Unknown"),
            "avg_congestion": _f(r.avg_congestion, 4),
            "avg_speed_mph": _f(r.avg_speed_mph, 2),
            "sample_count": r.sample_count,
        }
        for r in rows
    ]


def get_congestion_by_day(db: Session) -> list[dict[str, Any]]:
    """Average congestion and speed grouped by corridor × day_of_week."""
    rows = (
        db.query(
            MergedFeature.corridor_name,
            MergedFeature.day_of_week,
            func.avg(MergedFeature.congestion_index).label("avg_congestion"),
            func.max(MergedFeature.congestion_index).label("max_congestion"),
            func.avg(MergedFeature.current_speed_mph).label("avg_speed_mph"),
            func.count().label("sample_count"),
        )
        .filter(MergedFeature.congestion_index.isnot(None))
        .group_by(MergedFeature.corridor_name, MergedFeature.day_of_week)
        .order_by(MergedFeature.corridor_name, MergedFeature.day_of_week)
        .all()
    )
    return [
        {
            "corridor_name": r.corridor_name,
            "day_of_week": r.day_of_week,
            "day_name": _DAY_NAMES.get(r.day_of_week, "Unknown"),
            "avg_congestion": _f(r.avg_congestion, 4),
            "max_congestion": _f(r.max_congestion, 4),
            "avg_speed_mph": _f(r.avg_speed_mph, 2),
            "sample_count": r.sample_count,
        }
        for r in rows
    ]


def get_top_congested(db: Session) -> list[dict[str, Any]]:
    """Corridors ranked by average congestion index (highest first)."""
    rows = (
        db.query(
            MergedFeature.corridor_name,
            func.avg(MergedFeature.congestion_index).label("avg_congestion"),
            func.max(MergedFeature.congestion_index).label("max_congestion"),
            func.avg(MergedFeature.current_speed_mph).label("avg_speed_mph"),
            func.count().label("sample_count"),
        )
        .filter(MergedFeature.congestion_index.isnot(None))
        .group_by(MergedFeature.corridor_name)
        .order_by(func.avg(MergedFeature.congestion_index).desc())
        .all()
    )
    return [
        {
            "rank": idx + 1,
            "corridor_name": r.corridor_name,
            "avg_congestion": _f(r.avg_congestion, 4),
            "max_congestion": _f(r.max_congestion, 4),
            "avg_speed_mph": _f(r.avg_speed_mph, 2),
            "sample_count": r.sample_count,
        }
        for idx, r in enumerate(rows)
    ]


def get_current_snapshot(db: Session) -> list[dict[str, Any]]:
    """Latest reading + pre-computed prediction for every corridor."""
    latest_ts_subq = (
        db.query(
            MergedFeature.corridor_name,
            func.max(MergedFeature.timestamp).label("latest_ts"),
        )
        .group_by(MergedFeature.corridor_name)
        .subquery()
    )

    readings = (
        db.query(MergedFeature)
        .join(
            latest_ts_subq,
            (MergedFeature.corridor_name == latest_ts_subq.c.corridor_name)
            & (MergedFeature.timestamp == latest_ts_subq.c.latest_ts),
        )
        .all()
    )

    preds: dict[str, CachedPrediction] = {
        row.corridor_name: row for row in db.query(CachedPrediction).all()
    }

    results = []
    for r in readings:
        cached = preds.get(r.corridor_name)
        results.append({
            "corridor_name": r.corridor_name,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "current_speed_mph": r.current_speed_mph,
            "free_flow_speed_mph": r.free_flow_speed_mph,
            "congestion_index": r.congestion_index,
            "predicted_congestion_index": cached.predicted_congestion_index if cached else None,
            "congestion_label": cached.congestion_label if cached else None,
            "weather_condition": r.weather_condition,
            "weather_temp_f": r.weather_temp_f,
            "weather_rain_1h_mm": r.weather_rain_1h_mm,
            "weather_traffic_impact_level": r.weather_traffic_impact_level,
            "nearby_event_count": r.nearby_event_count,
            "has_high_impact_event": r.has_high_impact_event,
        })
    return results


def get_weather_impact(db: Session) -> list[dict[str, Any]]:
    """Average congestion grouped by weather condition and rain intensity bucket."""
    # Compute rain bucket in Python after fetching to avoid SQLAlchemy type issues
    rows = (
        db.query(
            MergedFeature.weather_condition,
            MergedFeature.weather_rain_1h_mm,
            func.avg(MergedFeature.congestion_index).label("avg_congestion"),
            func.avg(MergedFeature.current_speed_mph).label("avg_speed_mph"),
            func.avg(MergedFeature.weather_temp_f).label("avg_temp_f"),
            func.avg(MergedFeature.weather_wind_speed_mph).label("avg_wind_speed_mph"),
            func.count().label("sample_count"),
        )
        .filter(
            MergedFeature.congestion_index.isnot(None),
            MergedFeature.weather_condition.isnot(None),
        )
        .group_by(
            MergedFeature.weather_condition,
            MergedFeature.weather_rain_1h_mm,
        )
        .all()
    )

    # Bucket and re-aggregate in Python
    buckets: dict[tuple, dict] = {}
    for r in rows:
        rain = r.weather_rain_1h_mm or 0
        if rain == 0:
            bucket = "No Rain"
        elif rain < 2.5:
            bucket = "Light"
        elif rain < 7.6:
            bucket = "Moderate"
        else:
            bucket = "Heavy"

        key = (r.weather_condition, bucket)
        if key not in buckets:
            buckets[key] = {
                "weather_condition": r.weather_condition,
                "rain_bucket": bucket,
                "_congestion_sum": 0.0,
                "_speed_sum": 0.0,
                "_temp_sum": 0.0,
                "_wind_sum": 0.0,
                "sample_count": 0,
            }
        n = r.sample_count or 0
        buckets[key]["_congestion_sum"] += (r.avg_congestion or 0) * n
        buckets[key]["_speed_sum"] += (r.avg_speed_mph or 0) * n
        buckets[key]["_temp_sum"] += (r.avg_temp_f or 0) * n
        buckets[key]["_wind_sum"] += (r.avg_wind_speed_mph or 0) * n
        buckets[key]["sample_count"] += n

    result = []
    for b in sorted(buckets.values(), key=lambda x: x["_congestion_sum"] / max(x["sample_count"], 1), reverse=True):
        n = b["sample_count"] or 1
        result.append({
            "weather_condition": b["weather_condition"],
            "rain_bucket": b["rain_bucket"],
            "avg_congestion": _f(b["_congestion_sum"] / n, 4),
            "avg_speed_mph": _f(b["_speed_sum"] / n, 2),
            "avg_temp_f": _f(b["_temp_sum"] / n, 1),
            "avg_wind_speed_mph": _f(b["_wind_sum"] / n, 2),
            "sample_count": b["sample_count"],
        })
    return result


def get_event_impact(db: Session) -> list[dict[str, Any]]:
    """Average congestion grouped by event presence and high-impact flag per corridor."""
    rows = (
        db.query(
            MergedFeature.corridor_name,
            MergedFeature.nearby_event_count,
            MergedFeature.has_high_impact_event,
            func.avg(MergedFeature.congestion_index).label("avg_congestion"),
            func.avg(MergedFeature.current_speed_mph).label("avg_speed_mph"),
            func.count().label("sample_count"),
        )
        .filter(MergedFeature.congestion_index.isnot(None))
        .group_by(
            MergedFeature.corridor_name,
            MergedFeature.nearby_event_count,
            MergedFeature.has_high_impact_event,
        )
        .all()
    )

    # Re-aggregate into has_any_event / has_high_impact buckets
    buckets: dict[tuple, dict] = {}
    for r in rows:
        has_any = (r.nearby_event_count or 0) > 0
        has_high = bool(r.has_high_impact_event)
        key = (r.corridor_name, has_any, has_high)
        if key not in buckets:
            buckets[key] = {
                "corridor_name": r.corridor_name,
                "has_any_event": has_any,
                "has_high_impact_event": has_high,
                "_congestion_sum": 0.0,
                "_speed_sum": 0.0,
                "sample_count": 0,
            }
        n = r.sample_count or 0
        buckets[key]["_congestion_sum"] += (r.avg_congestion or 0) * n
        buckets[key]["_speed_sum"] += (r.avg_speed_mph or 0) * n
        buckets[key]["sample_count"] += n

    result = []
    for b in sorted(buckets.values(), key=lambda x: (x["corridor_name"], x["has_any_event"], x["has_high_impact_event"])):
        n = b["sample_count"] or 1
        result.append({
            "corridor_name": b["corridor_name"],
            "has_any_event": b["has_any_event"],
            "has_high_impact_event": b["has_high_impact_event"],
            "avg_congestion": _f(b["_congestion_sum"] / n, 4),
            "avg_speed_mph": _f(b["_speed_sum"] / n, 2),
            "sample_count": b["sample_count"],
        })
    return result


def get_event_impact_by_subtype(db: Session) -> list[dict[str, Any]]:
    """Congestion metrics per event subtype, sourced from the events table.

    For each subtype (austin_fc, ut_football, concert, festival, etc.) computes
    average congestion on corridors that had nearby events of that type, compared
    to the baseline (no events). Reads event_subtype from the events table joined
    to merged_features by timestamp proximity (within 3 hours of event start).
    """
    from backend.app.geo_models import Event as EventModel

    # Pull all events that have a subtype set
    events = (
        db.query(
            EventModel.event_subtype,
            EventModel.start_time,
        )
        .filter(EventModel.event_subtype.isnot(None))
        .all()
    )

    if not events:
        return []

    # For each subtype, find merged_feature rows whose timestamp falls within
    # 3 hours before or after any event of that subtype, then average congestion.
    from datetime import timedelta
    subtype_windows: dict[str, list[tuple]] = {}
    for ev in events:
        st = ev.event_subtype
        if st not in subtype_windows:
            subtype_windows[st] = []
        subtype_windows[st].append((
            ev.start_time - timedelta(hours=1),
            ev.start_time + timedelta(hours=3),
        ))

    results = []
    for subtype, windows in sorted(subtype_windows.items()):
        # Build a query that matches any window via OR conditions
        from sqlalchemy import or_
        window_filters = or_(*[
            (MergedFeature.timestamp >= w[0]) & (MergedFeature.timestamp <= w[1])
            for w in windows
        ])

        rows = (
            db.query(
                MergedFeature.corridor_name,
                func.avg(MergedFeature.congestion_index).label("avg_congestion"),
                func.avg(MergedFeature.current_speed_mph).label("avg_speed_mph"),
                func.count().label("sample_count"),
            )
            .filter(
                window_filters,
                MergedFeature.congestion_index.isnot(None),
            )
            .group_by(MergedFeature.corridor_name)
            .all()
        )

        for r in rows:
            results.append({
                "event_subtype": subtype,
                "corridor_name": r.corridor_name,
                "avg_congestion": _f(r.avg_congestion, 4),
                "avg_speed_mph": _f(r.avg_speed_mph, 2),
                "event_count": len(windows),
                "sample_count": r.sample_count,
            })

    return results


def get_forecast(
    db: Session,
    corridor_name: str,
    hours_ahead: int,
) -> list[dict[str, Any]]:
    """Synthesise future feature vectors and run ML inference for each hour."""
    from backend.services.data_service import get_latest_for_corridor
    from ml.predict import model_loaded, predict_with_confidence

    reading = get_latest_for_corridor(db, corridor_name)
    if reading is None or not model_loaded():
        return []

    base_dt = datetime.now(timezone.utc)
    results = []

    for h in range(1, hours_ahead + 1):
        future_dt = base_dt + timedelta(hours=h)
        features = {
            "current_speed_mph": reading.current_speed_mph,
            "free_flow_speed_mph": reading.free_flow_speed_mph,
            "weather_temp_f": reading.weather_temp_f,
            "weather_humidity_pct": reading.weather_humidity_pct,
            "weather_wind_speed_mph": reading.weather_wind_speed_mph,
            "weather_cloud_cover_pct": reading.weather_cloud_cover_pct,
            "weather_rain_1h_mm": reading.weather_rain_1h_mm,
            "nearby_event_count": reading.nearby_event_count,
            "hour_of_day": future_dt.hour,
            "day_of_week": future_dt.weekday(),
            "is_weekend": int(future_dt.weekday() >= 5),
            "weather_traffic_impact_level": reading.weather_traffic_impact_level,
        }
        index, low, high = predict_with_confidence(features)
        results.append({
            "corridor_name": corridor_name,
            "forecast_hour": h,
            "forecast_time": future_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "hour_of_day": future_dt.hour,
            "day_of_week": future_dt.weekday(),
            "day_name": _DAY_NAMES.get(future_dt.weekday(), "Unknown"),
            "predicted_congestion_index": index,
            "confidence_low": low,
            "confidence_high": high,
            "congestion_label": _congestion_label(index),
        })

    return results


def _congestion_label(index: float) -> str:
    if index < 0.2:
        return "Free Flow"
    if index < 0.4:
        return "Light"
    if index < 0.6:
        return "Moderate"
    if index < 0.8:
        return "Heavy"
    return "Severe"
