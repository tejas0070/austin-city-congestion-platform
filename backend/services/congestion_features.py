"""Shared feature engineering for the city-wide congestion ML model.

Single source of truth used by BOTH:
  - scripts/generate_training_data.py  (synthesize labelled history)
  - backend/services/ml_model.py       (build features at predict time)

The model is segment-agnostic: instead of per-corridor curves it learns from
generalizable features (road class, distance to downtown, time, weather, and
nearby event attendance), so it covers every segment in the Austin network.
"""
from __future__ import annotations

import math
from datetime import datetime

# Austin city centre — congestion intensity scales with proximity to it.
DOWNTOWN_LAT = 30.2672
DOWNTOWN_LNG = -97.7431

# Peak-hour baseline congestion (%) per road class, before time/weather/events.
ROAD_CLASS_PEAK: dict[str, float] = {
    "motorway": 42.0,
    "trunk": 36.0,
    "primary": 27.0,
    "secondary": 18.0,
    "tertiary": 12.0,
}

# Fraction of peak congestion by hour of day (AM + PM rush). Index = hour 0-23.
DIURNAL = [
    0.10, 0.07, 0.05, 0.05, 0.07, 0.15, 0.35, 0.70,
    0.95, 0.80, 0.55, 0.50, 0.55, 0.55, 0.60, 0.75,
    0.92, 1.00, 0.88, 0.65, 0.45, 0.32, 0.22, 0.15,
]

# Venue location + typical attendance — used to synthesize training events.
VENUE_INFO: dict[str, dict] = {
    "austin_fc":    {"lat": 30.3872, "lng": -97.7188, "typical": 20738},
    "ut_football":  {"lat": 30.2836, "lng": -97.7320, "typical": 100119},
    "moody_center": {"lat": 30.2850, "lng": -97.7280, "typical": 15000},
    "stubbs":       {"lat": 30.2680, "lng": -97.7336, "typical": 2200},
    "acl_live":     {"lat": 30.2639, "lng": -97.7467, "typical": 2750},
    "convention":   {"lat": 30.2628, "lng": -97.7402, "typical": 10000},
}

# Weather condition -> (weather_code, typical_temp_f, typical_precip_in, congestion_multiplier)
WEATHER_PROFILES: dict[str, tuple[int, float, float, float]] = {
    "Clear":      (0,  78.0, 0.00, 1.00),
    "Rain":       (63, 66.0, 0.15, 1.20),
    "Heavy Rain": (65, 62.0, 0.45, 1.45),
    "Storm":      (95, 60.0, 0.80, 1.70),
}

_PROXIMITY_RADIUS_KM = 8.0
_TIME_WINDOW_HOURS = 3.0

NUMERIC_FEATURES: list[str] = [
    "hour",
    "day_of_week",
    "is_weekend",
    "month",
    "weather_code",
    "temperature_f",
    "precipitation_in",
    "dist_downtown_km",
    "nearby_event_attendance",
    "base_pattern",
    # Data-driven autoregressive prior: this segment's REAL typical congestion at
    # this hour-of-week, learned from history. It carries segment-specific signal
    # the formula-based base_pattern cannot, which sharpens predictions (and thus
    # tightens the confidence interval) where real history exists. At predict time
    # it is supplied from a seasonal-prior lookup; in training it is the segment's
    # observed hour-of-week mean. Falls back to base_pattern when unknown.
    "seasonal_level",
]
CATEGORICAL_FEATURES: list[str] = ["road_class"]
FEATURE_ORDER: list[str] = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET_COLUMN = "congestion_pct"


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def dist_to_downtown_km(lat: float, lng: float) -> float:
    return haversine_km(lat, lng, DOWNTOWN_LAT, DOWNTOWN_LNG)


def _diurnal_factor(dt: datetime) -> float:
    """Smooth diurnal congestion fraction (linear interp between hourly anchors)."""
    h = dt.hour
    frac = dt.minute / 60.0
    nxt = (h + 1) % 24
    return DIURNAL[h] * (1 - frac) + DIURNAL[nxt] * frac


def _downtown_factor(dist_downtown_km: float) -> float:
    return max(0.45, min(1.2, 1.2 - dist_downtown_km / 20.0))


def base_pattern(road_class: str, dist_downtown_km: float, dt: datetime) -> float:
    """Deterministic congestion baseline for a segment at a given time."""
    peak = ROAD_CLASS_PEAK.get(road_class, 15.0)
    weekend = 0.65 if dt.weekday() >= 5 else 1.0
    return peak * _diurnal_factor(dt) * _downtown_factor(dist_downtown_km) * weekend


def _proximity_weight(distance_km: float) -> float:
    if distance_km >= _PROXIMITY_RADIUS_KM:
        return 0.0
    return 1.0 - (distance_km / _PROXIMITY_RADIUS_KM)


def _time_weight(hours_diff: float) -> float:
    h = abs(hours_diff)
    if h >= _TIME_WINDOW_HOURS:
        return 0.0
    return 1.0 - (h / _TIME_WINDOW_HOURS)


def nearby_event_attendance(
    centroid_lat: float,
    centroid_lng: float,
    dt: datetime,
    events: list[dict],
) -> float:
    """Distance- and time-weighted sum of attendance for events near a segment.

    Each event dict must have lat, lng, expected_attendance, and `start_dt`.
    """
    total = 0.0
    for ev in events:
        start_dt = ev.get("start_dt")
        if start_dt is None:
            continue
        tw = _time_weight((dt - start_dt).total_seconds() / 3600.0)
        if tw <= 0:
            continue
        pw = _proximity_weight(
            haversine_km(centroid_lat, centroid_lng, ev["lat"], ev["lng"])
        )
        if pw <= 0:
            continue
        total += (ev.get("expected_attendance") or 0) * pw * tw
    return round(total, 1)


def synthetic_congestion(
    segment: dict,
    dt: datetime,
    weather_condition: str,
    events: list[dict],
    noise: float = 0.0,
) -> float:
    """Ground-truth congestion the GENERATOR labels rows with."""
    base = base_pattern(segment["road_class"], segment["dist_downtown_km"], dt)
    _, _, _, weather_mult = WEATHER_PROFILES.get(weather_condition, WEATHER_PROFILES["Clear"])
    signal = nearby_event_attendance(
        segment["centroid_lat"], segment["centroid_lng"], dt, events
    )
    event_boost_pct = min(45.0, signal / 1500.0)
    return max(0.0, min(100.0, base * weather_mult + event_boost_pct + noise))


def congestion_level(pct: float) -> tuple[str, int]:
    """Map a congestion percentage to a (level, index) pair for colouring."""
    if pct < 15:
        return "green", 0
    if pct < 30:
        return "yellow", 1
    return "red", 2


def build_feature_row(
    segment: dict,
    dt: datetime,
    weather_code: int,
    temperature_f: float,
    precipitation_in: float,
    events: list[dict],
    seasonal_level: float | None = None,
) -> dict:
    """Construct one model feature row for a segment at a given time.

    `segment` must provide: road_class, centroid_lat, centroid_lng, dist_downtown_km.
    `seasonal_level` is the segment's data-driven typical congestion for this
    hour-of-week; when None it falls back to the formula-based base_pattern so the
    feature is always populated.
    """
    base = round(base_pattern(segment["road_class"], segment["dist_downtown_km"], dt), 3)
    return {
        "hour": dt.hour,
        "day_of_week": dt.weekday(),
        "is_weekend": 1 if dt.weekday() >= 5 else 0,
        "month": dt.month,
        "weather_code": weather_code,
        "temperature_f": round(temperature_f, 1),
        "precipitation_in": round(precipitation_in, 3),
        "dist_downtown_km": round(segment["dist_downtown_km"], 3),
        "nearby_event_attendance": nearby_event_attendance(
            segment["centroid_lat"], segment["centroid_lng"], dt, events
        ),
        "base_pattern": base,
        "seasonal_level": base if seasonal_level is None else round(float(seasonal_level), 3),
        "road_class": segment["road_class"],
    }
