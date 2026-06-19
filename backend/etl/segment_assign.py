# backend/etl/segment_assign.py
"""Assign a reading's lat/lng to the nearest Austin road segment (for road_class)."""
from __future__ import annotations

from backend.services.congestion_features import haversine_km


def nearest_segment(lat: float, lng: float, segments: list[dict]) -> dict | None:
    """Return the segment whose centroid is closest to (lat, lng)."""
    best = None
    best_d = float("inf")
    for seg in segments:
        d = haversine_km(lat, lng, seg["centroid_lat"], seg["centroid_lng"])
        if d < best_d:
            best_d = d
            best = seg
    return best
