#!/usr/bin/env python3
"""
Fetch exact Austin corridor road geometries from OpenStreetMap via the
Overpass API and write them to data/geo/corridors.geojson.

Run once from the project root:
    python scripts/fetch_corridor_geometry.py

Strategy: each corridor is fetched with a union of small around-point queries
rather than a single large bounding-box query.  Large-bbox queries reliably
time out for Austin's major highways; the around approach returns the same
ways but only loads nodes within each small radius.

No extra dependencies -- uses only the Python standard library.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "geo" / "corridors.geojson"

# ---------------------------------------------------------------------------
# Corridor definitions
# Each "seeds" list is a set of (lat, lon) points spaced ~2-3 km along the
# road.  The Overpass union fetches ways matching the filter within `radius`
# metres of each seed.  Confirmed OSM ref/name tags from live probes on
# 2026-06-10.
# ---------------------------------------------------------------------------
CORRIDORS: list[dict] = [
    {
        "name": "I-35_Downtown",
        "label": "I-35 (Downtown)",
        # Confirmed: ref contains "I 35", highway=motorway.
        "filter": 'way["ref"~"I 35"]["highway"="motorway"]',
        "radius": 400,
        "seeds": [
            (30.223, -97.732),
            (30.245, -97.733),
            (30.265, -97.734),
            (30.283, -97.732),
            (30.310, -97.729),
        ],
    },
    {
        "name": "Mopac_Expressway_Downtown",
        "label": "MoPac (Loop 1)",
        # Confirmed: ref=Loop 1, highway=motorway.
        # MoPac curves east as it goes north: lon moves from -97.783 at lat 30.267
        # to -97.759 at lat 30.300.  Seeds updated from live probe on 2026-06-10.
        "filter": 'way["ref"="Loop 1"]["highway"="motorway"]',
        "radius": 250,
        "seeds": [
            (30.220, -97.795),
            (30.250, -97.786),
            (30.267, -97.782),
            (30.285, -97.764),
            (30.300, -97.758),
            (30.340, -97.751),
            (30.370, -97.747),
        ],
    },
    {
        "name": "US-183_North",
        "label": "US-183 (Research Blvd)",
        # Centroid per CLAUDE.md: (30.3877, -97.7232).  US 183 / Research Blvd
        # runs roughly N-S in NW Austin; seeds placed on confirmed highway corridor.
        "filter": 'way["ref"~"US 183"]',
        "radius": 400,
        "seeds": [
            (30.315, -97.726),
            (30.345, -97.730),
            (30.376, -97.724),
            (30.400, -97.717),
        ],
    },
    {
        "name": "Loop-360_West",
        "label": "Loop 360 (Capital of Texas Hwy)",
        # Confirmed: ref=Loop 360, highway=trunk.  Probe on 2026-06-10 confirmed
        # road at lat 30.327-30.333, lon -97.815 to -97.770.
        "filter": 'way["ref"~"Loop 360"]["highway"~"trunk|primary|secondary"]',
        "radius": 1200,
        "seeds": [
            (30.265, -97.803),
            (30.295, -97.801),
            (30.330, -97.793),
            (30.358, -97.778),
            (30.382, -97.759),
        ],
    },
    {
        "name": "Congress_Ave_Downtown",
        "label": "Congress Ave (Downtown)",
        "filter": 'way["name"="Congress Avenue"]["highway"~"primary|secondary|tertiary"]',
        "radius": 200,
        "seeds": [
            (30.257, -97.743),
            (30.268, -97.743),
            (30.279, -97.742),
        ],
    },
]

# ---------------------------------------------------------------------------
# Overpass helpers
# ---------------------------------------------------------------------------

def _build_query(corridor: dict, seed: tuple[float, float] | None = None) -> str:
    """Build one Overpass QL statement.

    If `seed` is given, query only that one point.
    Otherwise build a union over all seeds.
    Uses `out geom;` so coordinates are inline — no node recursion needed.
    """
    seeds = [seed] if seed else corridor["seeds"]
    parts = [
        f'{corridor["filter"]}(around:{corridor["radius"]},{lat},{lon});'
        for lat, lon in seeds
    ]
    body = "\n  ".join(parts)
    return f"[out:json][timeout:35];\n(\n  {body}\n);\nout geom;"


def _fetch(query: str) -> dict:
    payload = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        OVERPASS_URL,
        data=payload,
        method="POST",
        headers={"User-Agent": "austin-traffic-intelligence/1.0 corridor-fetch"},
    )
    with urllib.request.urlopen(req, timeout=55) as resp:
        return json.loads(resp.read().decode())


# _GeomWay = list of (lat, lon) pairs from an `out geom;` element
_GeomWay = list[tuple[float, float]]


def _parse(data: dict) -> list[_GeomWay]:
    """Extract ordered (lat, lon) sequences from `out geom;` response elements."""
    ways: list[_GeomWay] = []
    for el in data.get("elements", []):
        if el.get("type") != "way":
            continue
        geom = el.get("geometry", [])
        pts = [(g["lat"], g["lon"]) for g in geom if "lat" in g and "lon" in g]
        if len(pts) >= 2:
            ways.append(pts)
    return ways


def _deduplicate(ways: list[_GeomWay]) -> list[_GeomWay]:
    seen: set[tuple[float, float]] = set()
    unique: list[_GeomWay] = []
    for w in ways:
        key = (w[0], w[-1])
        if key not in seen:
            rev_key = (w[-1], w[0])
            if rev_key not in seen:
                seen.add(key)
                unique.append(w)
    return unique


def _assemble(ways: list[_GeomWay]) -> list[tuple[float, float]]:
    """Chain geometry-bearing ways into one ordered coordinate sequence."""
    if not ways:
        return []
    if len(ways) == 1:
        return ways[0]

    # Build endpoint → way-index lookup using rounded coords as keys
    def _ep(pt: tuple[float, float]) -> tuple[float, float]:
        return (round(pt[0], 6), round(pt[1], 6))

    endpoints: dict[tuple[float, float], list[int]] = defaultdict(list)
    for i, w in enumerate(ways):
        endpoints[_ep(w[0])].append(i)
        endpoints[_ep(w[-1])].append(i)

    # Prefer a terminal endpoint (only one way uses it)
    start_ep = _ep(ways[0][0])
    for ep, idxs in endpoints.items():
        if len(idxs) == 1:
            start_ep = ep
            break

    first = endpoints[start_ep][0]
    if _ep(ways[first][-1]) == start_ep:
        ways[first] = ways[first][::-1]

    coords: list[tuple[float, float]] = []
    used: set[int] = set()
    current: int | None = first

    while current is not None and current not in used:
        used.add(current)
        offset = 1 if coords else 0
        coords.extend(ways[current][offset:])
        tail = _ep(ways[current][-1])
        nxt: int | None = None
        for wi in endpoints[tail]:
            if wi not in used:
                if _ep(ways[wi][-1]) == tail:
                    ways[wi] = ways[wi][::-1]
                nxt = wi
                break
        current = nxt

    return coords


def _feature(corridor: dict, coords: list[tuple[float, float]]) -> dict:
    return {
        "type": "Feature",
        "properties": {"name": corridor["name"], "label": corridor["label"]},
        "geometry": {
            "type": "LineString",
            "coordinates": [[lon, lat] for lat, lon in coords],
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("Fetching Austin corridor geometries from OpenStreetMap...\n")
    sys.stdout.flush()

    existing_features: dict[str, dict] = {}
    if OUT_PATH.exists():
        try:
            existing = json.loads(OUT_PATH.read_text(encoding="utf-8"))
            for f in existing.get("features", []):
                existing_features[f["properties"]["name"]] = f
        except Exception as exc:
            print(f"Warning: could not read existing {OUT_PATH.name}: {exc}")

    features: list[dict] = []
    any_failure = False

    # Corridors with more than 5 seeds are fetched per-seed to avoid Overpass
    # union 504 timeouts; the threshold is a property of the API, not the corridor.
    _SEQUENTIAL_SEED_THRESHOLD = 5

    for idx, corridor in enumerate(CORRIDORS):
        if idx > 0:
            time.sleep(3)
        name = corridor["name"]
        print(f"  {name} ...", end=" ", flush=True)
        try:
            seeds = corridor["seeds"]
            if len(seeds) > _SEQUENTIAL_SEED_THRESHOLD:
                all_ways: list[_GeomWay] = []
                for i, seed in enumerate(seeds):
                    if i > 0:
                        time.sleep(2)
                    all_ways.extend(_parse(_fetch(_build_query(corridor, seed))))
                raw_ways = all_ways
            else:
                raw_ways = _parse(_fetch(_build_query(corridor)))
            ways = _deduplicate(raw_ways)
            coords = _assemble(ways)

            if len(coords) < 2:
                raise ValueError(
                    f"got {len(ways)} way(s) but only {len(coords)} usable point(s); "
                    "check filter tag or seed coordinates in CORRIDORS"
                )

            features.append(_feature(corridor, coords))
            print(f"OK ({len(coords)} pts, {len(ways)} ways)")

        except Exception as exc:
            any_failure = True
            print(f"FAILED: {exc}")
            if name in existing_features:
                features.append(existing_features[name])
                print(f"    -> kept existing geometry for {name}")
            else:
                print(f"    -> no fallback; corridor will be missing from map")

    if not features:
        print("\nNothing collected -- corridors.geojson not updated.")
        return 1

    geojson = {"type": "FeatureCollection", "features": features}
    OUT_PATH.write_text(json.dumps(geojson, indent=2), encoding="utf-8")
    print(f"\nWrote {len(features)} corridor(s) to {OUT_PATH}")
    if any_failure:
        print("Some corridors used fallback geometry. Re-run to retry.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
