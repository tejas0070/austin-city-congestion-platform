# backend/etl/sensor_locations.py
"""Build a reader -> (lat, lng) lookup from the Travel Sensors locations dataset.

TMSR speed records carry no coordinates, only reader identifiers and roadway/
cross-street names. We index each location record under BOTH its normalized
reader_id and its normalized (primary_st, cross_st) pair so a TMSR row can be
matched on whichever key is cleaner.
"""
from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]")


def normalize_reader_key(*parts: str) -> str:
    """Lowercase, strip every non-alphanumeric char, concatenate the parts."""
    return "".join(_NON_ALNUM.sub("", (p or "").lower()) for p in parts)


def build_reader_location_map(records: list[dict]) -> dict[str, tuple[float, float]]:
    """Map normalized keys -> (lat, lng). Records lacking a Point are skipped."""
    out: dict[str, tuple[float, float]] = {}
    for rec in records:
        loc = rec.get("location") or {}
        coords = loc.get("coordinates") if isinstance(loc, dict) else None
        if not coords or len(coords) < 2:
            continue
        lng, lat = float(coords[0]), float(coords[1])
        reader_id = rec.get("reader_id")
        if reader_id:
            out[normalize_reader_key(reader_id)] = (lat, lng)
        pair = normalize_reader_key(rec.get("primary_st", ""), rec.get("cross_st", ""))
        if pair:
            out[pair] = (lat, lng)
    return out
