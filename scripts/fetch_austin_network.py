#!/usr/bin/env python3
"""Fetch Austin's major road network from OpenStreetMap (Overpass).

Tiles the Austin bounding box and pulls every motorway / trunk / primary /
secondary way, then writes them as individual LineString segments to
data/geo/austin_network.geojson with properties:

    segment_id   stable id ("seg_000123")
    name         road name (or class label if unnamed)
    road_class   motorway | trunk | primary | secondary
    length_km    approximate segment length

Run once from the project root (re-run to refresh):
    python scripts/fetch_austin_network.py

Standard library only.
"""
from __future__ import annotations

import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "geo" / "austin_network.geojson"

# Greater-Austin bounding box (south, west, north, east).
BBOX = (30.10, -97.95, 30.52, -97.56)
TILES_LAT = 3
TILES_LON = 3

ROAD_CLASSES = ["motorway", "trunk", "primary", "secondary"]
# Keep the network legible: cap very long ways by splitting, and drop tiny stubs.
MAX_PTS_PER_SEGMENT = 60
MIN_SEGMENT_KM = 0.15


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi = math.radians(b[0] - a[0])
    dlmb = math.radians(b[1] - a[1])
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _line_length_km(coords: list[list[float]]) -> float:
    total = 0.0
    for i in range(1, len(coords)):
        total += _haversine_km(
            (coords[i - 1][1], coords[i - 1][0]),
            (coords[i][1], coords[i][0]),
        )
    return total


def _tiles() -> list[tuple[float, float, float, float]]:
    s, w, n, e = BBOX
    dlat = (n - s) / TILES_LAT
    dlon = (e - w) / TILES_LON
    out = []
    for i in range(TILES_LAT):
        for j in range(TILES_LON):
            out.append((s + i * dlat, w + j * dlon, s + (i + 1) * dlat, w + (j + 1) * dlon))
    return out


def _build_query(tile: tuple[float, float, float, float]) -> str:
    classes = "|".join(ROAD_CLASSES)
    s, w, n, e = tile
    return (
        "[out:json][timeout:60];\n"
        f'(way["highway"~"^({classes})$"]({s},{w},{n},{e}););\n'
        "out geom;"
    )


def _fetch(query: str) -> dict:
    payload = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        OVERPASS_URL,
        data=payload,
        method="POST",
        headers={"User-Agent": "austin-traffic-intelligence/2.0 network-fetch"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode())


def _split(coords: list[list[float]]) -> list[list[list[float]]]:
    """Split a long polyline into chunks of <= MAX_PTS_PER_SEGMENT (overlapping by 1)."""
    if len(coords) <= MAX_PTS_PER_SEGMENT:
        return [coords]
    chunks = []
    i = 0
    while i < len(coords) - 1:
        chunk = coords[i:i + MAX_PTS_PER_SEGMENT]
        if len(chunk) >= 2:
            chunks.append(chunk)
        i += MAX_PTS_PER_SEGMENT - 1
    return chunks


def main() -> int:
    print("Fetching Austin road network from OpenStreetMap...\n")
    seen_ways: set[int] = set()
    features: list[dict] = []
    seq = 0

    tiles = _tiles()
    for idx, tile in enumerate(tiles):
        if idx > 0:
            time.sleep(2)
        print(f"  tile {idx + 1}/{len(tiles)} {tile} ...", end=" ", flush=True)
        try:
            data = _fetch(_build_query(tile))
        except Exception as exc:
            print(f"FAILED: {exc}")
            continue

        added = 0
        for el in data.get("elements", []):
            if el.get("type") != "way":
                continue
            way_id = el.get("id")
            if way_id in seen_ways:
                continue
            seen_ways.add(way_id)

            geom = el.get("geometry", [])
            coords = [[g["lon"], g["lat"]] for g in geom if "lon" in g and "lat" in g]
            if len(coords) < 2:
                continue

            tags = el.get("tags", {})
            road_class = tags.get("highway", "secondary")
            name = tags.get("name") or tags.get("ref") or road_class.title()

            for chunk in _split(coords):
                length = _line_length_km(chunk)
                if length < MIN_SEGMENT_KM:
                    continue
                features.append({
                    "type": "Feature",
                    "properties": {
                        "segment_id": f"seg_{seq:06d}",
                        "name": name,
                        "road_class": road_class,
                        "length_km": round(length, 3),
                    },
                    "geometry": {"type": "LineString", "coordinates": chunk},
                })
                seq += 1
                added += 1
        print(f"OK (+{added} segments, {len(features)} total)")

    if not features:
        print("\nNo segments collected — network file not written.")
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}),
        encoding="utf-8",
    )

    by_class: dict[str, int] = {}
    for f in features:
        c = f["properties"]["road_class"]
        by_class[c] = by_class.get(c, 0) + 1
    print(f"\nWrote {len(features)} segments to {OUT_PATH}")
    print("By road class:", by_class)
    return 0


if __name__ == "__main__":
    sys.exit(main())
