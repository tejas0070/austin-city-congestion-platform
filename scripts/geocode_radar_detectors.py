#!/usr/bin/env python3
"""Geocode the Austin Radar Traffic Counts detectors (dataset i626-g7ub).

The radar dataset names intersections (e.g. "LAMARMANCHACA") but carries no
coordinates. There are only ~19 distinct intersections, so we geocode them once
to data/geo/radar_detector_locations.json ({int_id: [lat, lng]}).

Geocoding uses the OpenStreetMap Overpass API, which (unlike Nominatim) can find
the node where two named streets cross — the actual intersection. Each detector
maps to a curated (primary, cross) street regex pair. Results outside Austin
bounds are rejected.

Run from the project root (one-time / when detectors change):
    python scripts/geocode_radar_detectors.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx  # noqa: E402

RADAR_URL = "https://data.austintexas.gov/resource/i626-g7ub.json"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "geo" / "radar_detector_locations.json"

# Austin bounding box (south, west, north, east) — also rejects bad geocodes.
BBOX = (30.10, -98.05, 30.55, -97.55)
LAT_MIN, LNG_MIN, LAT_MAX, LNG_MAX = BBOX[0], BBOX[1], BBOX[2], BBOX[3]

# Curated (primary-street regex, cross-street regex) for each mashed intersection
# name. Regexes are matched against OSM way `name` (case-insensitive). TEST
# sensors and intersections without a confident split are omitted.
STREETS_BY_INTNAME: dict[str, tuple[str, str]] = {
    "LAMARMANCHACA": ("Lamar", "Me?nchaca"),  # Austin renamed Manchaca -> Menchaca
    "LAMARSHOALCREEK": ("Lamar", "Shoal Creek"),
    "CONGRESSBARTON SPRINGS": ("Congress", "Barton Springs"),
    "LOOP 360WALSH TARLTON": ("Capital of Texas", "Walsh Tarlton"),
    "BurnetRutland": ("Burnet", "Rutland"),
    "Robert E LeeBarton Springs": ("Azie Morton", "Barton Springs"),
    "N Lamar15th": ("Lamar", "15th"),
    "CongressJohanna": ("Congress", "Johanna"),
    "KINNEYLAMAR": ("Kinney", "Lamar"),
    "LAMARCOLLIER": ("Lamar", "Collier"),
    "BURNETPALM WAY": ("Burnet", "Palm Way"),
    "LOOP 360LAKEWOOD": ("Capital of Texas", "Lakewood"),
    "LAMARZENNIA": ("Lamar", "Zennia"),
    "LAMARSANDRA MURAIDA": ("Lamar", "Sandra Muraida"),
}


def _fetch_detectors() -> list[dict]:
    with httpx.Client(timeout=40.0) as c:
        resp = c.get(RADAR_URL, params={
            "$select": "int_id,intname", "$group": "int_id,intname",
            "$order": "int_id", "$limit": 500,
        })
        resp.raise_for_status()
        return resp.json()


def _overpass_intersection(primary: str, cross: str) -> tuple[float, float] | None:
    """Find a node where a way named ~primary crosses a way named ~cross."""
    s, w, n, e = BBOX
    query = f"""
    [out:json][timeout:25];
    way[highway][name~"{primary}",i]({s},{w},{n},{e})->.a;
    way[highway][name~"{cross}",i]({s},{w},{n},{e})->.b;
    node(w.a)(w.b);
    out 1;
    """
    elements: list[dict] = []
    with httpx.Client(timeout=40.0, headers={"User-Agent": "austin-traffic-intelligence/1.0"}) as c:
        for attempt in range(4):  # retry on rate-limit (429) with backoff
            resp = c.post(OVERPASS_URL, data={"data": query})
            if resp.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            break
    for el in elements:
        lat, lng = el.get("lat"), el.get("lon")
        if lat is None or lng is None:
            continue
        if LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX:
            return float(lat), float(lng)
    return None


def main() -> int:
    detectors = _fetch_detectors()
    print(f"{len(detectors)} distinct intersections in the radar dataset")

    # Resume from any prior run so we only query the intersections still missing.
    locations: dict[str, list[float]] = {}
    if OUT_PATH.exists():
        locations = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        print(f"  resuming: {len(locations)} already cached")

    for det in detectors:
        intname = (det.get("intname") or "").strip()
        int_id = str(det.get("int_id"))
        if int_id in locations:
            continue
        pair = STREETS_BY_INTNAME.get(intname)
        if not pair:
            print(f"  skip {int_id} '{intname}' (no curated street split)")
            continue
        try:
            coord = _overpass_intersection(*pair)
        except Exception as exc:  # noqa: BLE001 - network hiccup, keep going
            print(f"  ERR   {int_id} '{intname}': {exc}")
            coord = None
        time.sleep(2.0)  # be gentle with the public Overpass endpoint
        if coord is None:
            print(f"  FAIL  {int_id} '{intname}' -> {pair}")
            continue
        locations[int_id] = [round(coord[0], 6), round(coord[1], 6)]
        print(f"  ok    {int_id} '{intname}' -> {coord[0]:.5f}, {coord[1]:.5f}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(locations, indent=2), encoding="utf-8")
    print(f"Geocoded {len(locations)} intersections -> {OUT_PATH}")
    return 0 if locations else 1


if __name__ == "__main__":
    sys.exit(main())
