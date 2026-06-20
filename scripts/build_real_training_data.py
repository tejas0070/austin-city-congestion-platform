#!/usr/bin/env python3
"""Build real training data from City of Austin travel-sensor speed history.

Pipeline (all OFFLINE — never runs in the API):
  1. Pull TMSR speed records (v7zg-5jg9), sampled across the date range.
  2. Pull Travel Sensors locations (6yd9-yz29) -> reader -> (lat,lng) map.
  3. Per reader, compute free-flow speed; per reading, congestion_pct.
  4. Geolocate each reading; assign nearest-segment road_class + dist-downtown.
  5. Join historical weather (Open-Meteo archive) + curated events.
  6. Write data/training/congestion_history.csv (same contract as before).

Run from the project root:
    python scripts/build_real_training_data.py
Then:
    python scripts/train_model.py

Note on reader/location join:
    The Travel Sensors locations dataset (6yd9-yz29) covers only ~8 of the 261
    TMSR origin readers by exact reader_id. A roadway-name fallback is applied
    to cover Lamar, Congress, Riverside, Loop 360, and other major corridors
    (~70% of TMSR rows) by mapping abbreviated TMSR roadway names to their
    full forms in the locations table.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx  # noqa: E402
import pandas as pd  # noqa: E402

from backend.services.congestion_features import (  # noqa: E402
    FEATURE_ORDER, TARGET_COLUMN, build_feature_row, dist_to_downtown_km,
)
from backend.services.segments_service import load_segments  # noqa: E402
from backend.services.weather_service import fetch_historical_weather  # noqa: E402
from backend.etl.congestion import free_flow_speed, congestion_pct_from_speed  # noqa: E402
from backend.etl.sensor_locations import build_reader_location_map, normalize_reader_key  # noqa: E402
from backend.etl.segment_assign import nearest_segment  # noqa: E402
from backend.etl.events_backfill import load_curated_events  # noqa: E402

TMSR_URL = "https://data.austintexas.gov/resource/v7zg-5jg9.json"
LOCATIONS_URL = "https://data.austintexas.gov/resource/6yd9-yz29.json"
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "training" / "congestion_history.csv"
EVENTS_PATH = Path(__file__).resolve().parents[1] / "data" / "events" / "austin_major_events.csv"

MAX_READINGS = 120_000          # cap rows pulled (keeps ETL + CSV bounded)
PAGE = 50_000                   # Socrata page size
# Minimum Bluetooth matches per 15-min reading. Low-sample readings (especially
# overnight, where avg samples drop below 1) are a single noisy match and read
# as spuriously slow → spuriously congested. Requiring >=3 samples yields a
# realistic diurnal curve (night free-flows, rush hours congest); without it the
# model learns inverted "congested at 2 AM" noise.
MIN_SAMPLES = 3
APP_TOKEN = os.environ.get("SOCRATA_APP_TOKEN") or None

# Map TMSR abbreviated roadway names -> prefixes of normalized primary_st in
# the locations dataset.  Used as a fallback when reader_id and exact pair
# matching both fail.  Covers ~70 % of TMSR rows by volume.
ROADWAY_ALIAS: dict[str, str] = {
    "lamar":      "lamarblvd",
    "lamar_all":  "lamarblvd",
    "congress":   "congressave",
    "riverside":  "riversidedr",
    "loop 360":   "capitaloftexashwy",
    "loop360":    "capitaloftexashwy",
    "7th st":     "5thst",       # nearest available corridor; ~0.5 km offset acceptable
    "7th":        "5thst",
    "51st":       "airportblvd", # nearest east-side arterial with a sensor
    "us 183":     "airportblvd", # Airport Blvd / 183 corridor overlap
    "us183":      "airportblvd",
    "ben white":  "riversidedr", # Ben White Blvd runs parallel; Riverside is nearest
    "benwhite":   "riversidedr",
    "burleson":   "airportblvd", # SE sector fallback
}


def _headers() -> dict:
    return {"X-App-Token": APP_TOKEN} if APP_TOKEN else {}


def _fetch_locations() -> tuple[dict, dict]:
    """Return (loc_map, roadway_centroid_map).

    loc_map        : normalized reader_id / street-pair -> (lat, lng)  [exact join]
    roadway_centroid_map : normalized primary_st prefix -> first (lat, lng) seen
    """
    with httpx.Client(timeout=60.0) as c:
        resp = c.get(LOCATIONS_URL, params={"$limit": 5000}, headers=_headers())
        resp.raise_for_status()
        records = resp.json()

    loc_map = build_reader_location_map(records)

    # Build roadway-centroid map: first location for each unique normalized primary_st.
    roadway_centroid: dict[str, tuple[float, float]] = {}
    for rec in records:
        loc = rec.get("location") or {}
        coords = loc.get("coordinates") if isinstance(loc, dict) else None
        if not coords or len(coords) < 2:
            continue
        lng, lat = float(coords[0]), float(coords[1])
        pst = normalize_reader_key((rec.get("primary_st") or "").strip())
        if pst and pst not in roadway_centroid:
            roadway_centroid[pst] = (lat, lng)

    return loc_map, roadway_centroid


def _fetch_tmsr() -> list[dict]:
    rows: list[dict] = []
    with httpx.Client(timeout=120.0) as c:
        offset = 0
        while len(rows) < MAX_READINGS:
            resp = c.get(TMSR_URL, params={
                "$select": "origin_reader_identifier,origin_roadway,origin_cross_street,"
                           "average_speed_mph,number_samples,timestamp",
                "$where": f"average_speed_mph IS NOT NULL AND number_samples >= {MIN_SAMPLES}",
                "$order": "timestamp",
                "$limit": PAGE,
                "$offset": offset,
            }, headers=_headers())
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            rows.extend(batch)
            offset += PAGE
    return rows[:MAX_READINGS]


def _locate(
    row: dict,
    loc_map: dict,
    roadway_centroid: dict,
) -> tuple[float, float] | None:
    """Return (lat, lng) for a TMSR row via a three-tier lookup.

    Tier 1: Exact normalized reader_id match.
    Tier 2: Exact normalized (roadway, cross_street) pair match.
    Tier 3: Roadway-alias fallback -> approximate centroid for that corridor.
    """
    reader = row.get("origin_reader_identifier", "")
    roadway = row.get("origin_roadway", "") or ""
    cross = row.get("origin_cross_street", "") or ""

    # Tier 1 — reader_id exact
    key = normalize_reader_key(reader)
    if key in loc_map:
        return loc_map[key]

    # Tier 2 — normalized (roadway, cross) pair, both orderings
    pair = normalize_reader_key(roadway, cross)
    if pair in loc_map:
        return loc_map[pair]
    pair_rev = normalize_reader_key(cross, roadway)
    if pair_rev in loc_map:
        return loc_map[pair_rev]

    # Tier 3 — roadway-alias -> centroid lookup
    rw_norm = roadway.strip().lower()
    alias_key = ROADWAY_ALIAS.get(rw_norm) or ROADWAY_ALIAS.get(normalize_reader_key(roadway))
    if alias_key and alias_key in roadway_centroid:
        return roadway_centroid[alias_key]

    # Tier 3b — prefix scan: if TMSR roadway normalized is a prefix of any
    # location primary_st key, use that location.
    rw_prefix = normalize_reader_key(roadway)
    if len(rw_prefix) >= 4:
        for pst_key, coord in roadway_centroid.items():
            if pst_key.startswith(rw_prefix):
                return coord

    return None


def main() -> int:
    segments = load_segments()
    if not segments:
        print("[ERROR] No segments. Run scripts/fetch_austin_network.py first.")
        return 1

    print("Fetching sensor locations ...")
    loc_map, roadway_centroid = _fetch_locations()
    print(f"  {len(loc_map)} exact location keys")
    print(f"  {len(roadway_centroid)} roadway-centroid keys")

    print("Fetching TMSR speed records ...")
    raw = _fetch_tmsr()
    print(f"  {len(raw)} readings")
    if not raw:
        print("[ERROR] No TMSR rows returned.")
        return 1

    # Free-flow speed per reader (needs all of a reader's speeds first).
    speeds_by_reader: dict[str, list[float]] = defaultdict(list)
    for r in raw:
        try:
            speeds_by_reader[r["origin_reader_identifier"]].append(float(r["average_speed_mph"]))
        except (KeyError, ValueError, TypeError):
            continue
    free_flow = {rid: free_flow_speed(s) for rid, s in speeds_by_reader.items()}

    events = load_curated_events(EVENTS_PATH)
    print(f"  {len(events)} curated events")

    # Historical weather for the data's full span, fetched once.
    stamps = [r["timestamp"][:10] for r in raw if r.get("timestamp")]
    weather = fetch_historical_weather(min(stamps), max(stamps)) if stamps else {}
    print(f"  {len(weather)} weather hours")

    rows_out: list[dict] = []
    skipped = 0
    skip_reasons: dict[str, int] = {"no_ff": 0, "no_loc": 0, "no_ts": 0, "parse_err": 0, "no_seg": 0}

    for r in raw:
        ff = free_flow.get(r.get("origin_reader_identifier"))
        if not ff:
            skip_reasons["no_ff"] += 1
            skipped += 1
            continue
        loc = _locate(r, loc_map, roadway_centroid)
        if loc is None:
            skip_reasons["no_loc"] += 1
            skipped += 1
            continue
        ts = r.get("timestamp")
        if not ts:
            skip_reasons["no_ts"] += 1
            skipped += 1
            continue
        try:
            dt = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
            speed = float(r["average_speed_mph"])
        except (ValueError, TypeError):
            skip_reasons["parse_err"] += 1
            skipped += 1
            continue
        lat, lng = loc
        seg = nearest_segment(lat, lng, segments)
        if seg is None:
            skip_reasons["no_seg"] += 1
            skipped += 1
            continue
        wx = weather.get(ts[:13], {"weather_code": 0, "temperature_f": 78.0, "precipitation_in": 0.0})
        reading_segment = {
            "road_class": seg["road_class"],
            "centroid_lat": lat,
            "centroid_lng": lng,
            "dist_downtown_km": dist_to_downtown_km(lat, lng),
        }
        feat = build_feature_row(
            reading_segment, dt,
            int(wx["weather_code"]), float(wx["temperature_f"]), float(wx["precipitation_in"]),
            events,
        )
        feat[TARGET_COLUMN] = congestion_pct_from_speed(speed, ff)
        rows_out.append(feat)

    print(f"  built {len(rows_out)} rows, skipped {skipped} (reasons: {skip_reasons})")
    if not rows_out:
        print("[ERROR] No rows built — check the reader/location join.")
        return 1

    df = pd.DataFrame(rows_out)[FEATURE_ORDER + [TARGET_COLUMN]]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(df):,} rows -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
