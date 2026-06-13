"""City-wide Austin road segments: geometry + live (simulated) congestion.

Loads data/geo/austin_network.geojson once, precomputes per-segment metadata
(centroid, distance to downtown), and produces a live-congestion GeoJSON.

Live congestion is currently SIMULATED from the deterministic base pattern plus
noise, because there is no real per-segment speed feed yet. Swapping in a real
feed only requires replacing `_live_congestion_pct` / `build_live_segments`
with the real source keyed on `segment_id` — the GeoJSON contract stays the same.
"""
from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path

from ..utils.cache import get_cache, set_cache
from ..utils.geojson_builder import build_feature_collection, build_line_feature
from .congestion_features import (
    base_pattern,
    congestion_level,
    dist_to_downtown_km,
)

NETWORK_PATH = Path(__file__).resolve().parents[2] / "data" / "geo" / "austin_network.geojson"

LIVE_CACHE_KEY = "segments_live"
LIVE_CACHE_TTL = 90  # seconds

_segments: list[dict] | None = None


def _centroid(coords: list[list[float]]) -> tuple[float, float]:
    """Approximate segment centroid as its middle vertex (lng/lat order in input)."""
    mid = coords[len(coords) // 2]
    return mid[1], mid[0]  # lat, lng


def load_segments() -> list[dict]:
    """Load and cache the segment list with precomputed metadata."""
    global _segments
    if _segments is not None:
        return _segments

    try:
        raw = json.loads(NETWORK_PATH.read_text(encoding="utf-8"))
    except Exception:
        _segments = []
        return _segments

    segments: list[dict] = []
    for feature in raw.get("features", []):
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            continue
        clat, clng = _centroid(coords)
        segments.append({
            "segment_id": props.get("segment_id", ""),
            "name": props.get("name", "Road"),
            "road_class": props.get("road_class", "secondary"),
            "coords": coords,
            "centroid_lat": clat,
            "centroid_lng": clng,
            "dist_downtown_km": dist_to_downtown_km(clat, clng),
        })

    _segments = segments
    return _segments


def segment_count() -> int:
    return len(load_segments())


def _live_congestion_pct(segment: dict, now: datetime) -> float:
    """Simulated current congestion for a segment (base pattern + bounded noise)."""
    base = base_pattern(segment["road_class"], segment["dist_downtown_km"], now)
    jitter = random.uniform(-3.0, 4.0)
    return max(0.0, min(100.0, base + jitter))


def build_live_segments() -> dict:
    """Return city-wide live-congestion GeoJSON (LineStrings), cached 90 s."""
    cached = get_cache(LIVE_CACHE_KEY)
    if cached:
        return cached

    now = datetime.now()
    rng = random.Random(int(now.timestamp()) // LIVE_CACHE_TTL)  # stable within a cache window
    features: list[dict] = []
    for seg in load_segments():
        base = base_pattern(seg["road_class"], seg["dist_downtown_km"], now)
        pct = max(0.0, min(100.0, base + rng.uniform(-3.0, 4.0)))
        level, index = congestion_level(pct)
        features.append(build_line_feature(seg["coords"], {
            "segment_id": seg["segment_id"],
            "road_name": seg["name"],
            "road_class": seg["road_class"],
            "congestion_pct": round(pct, 1),
            "congestion_level": level,
            "congestion_index": index,
        }))

    result = build_feature_collection(features)
    # Timestamp the snapshot so the UI can show "as of <time>" for the live
    # layer. Frozen for the cache window, which is when it was actually built.
    result["generated_at"] = now.isoformat(timespec="seconds")
    set_cache(LIVE_CACHE_KEY, result, LIVE_CACHE_TTL)
    return result
