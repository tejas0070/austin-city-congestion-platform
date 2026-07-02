#!/usr/bin/env python3
"""Build training rows from Austin Radar Traffic Counts (dataset i626-g7ub).

These radar detectors sit at ~13 geocoded intersections (see
scripts/geocode_radar_detectors.py) but carry millions of dense readings, which
greatly enriches the model's hour/weather/road-class calibration. This script
pulls a bounded sample balanced across several PRE-COVID years (2020-2021 traffic
was atypically light and biases the learned patterns), derives congestion from
speed (vs each detector's free-flow), assigns each to the nearest OSM segment,
and writes a RAW rows CSV:

    data/training/_radar_rows.csv

`build_real_training_data.py` then concatenates it with the Bluetooth readings
and computes the shared `seasonal_level` + prior over the combined set.

Env knobs: RADAR_YEARS (default "2017,2018,2019"), RADAR_MAX_READINGS (default
300000, split evenly across the years).

Run from the project root:
    python scripts/geocode_radar_detectors.py     # once
    python scripts/build_radar_training_data.py
    python scripts/build_real_training_data.py     # merges + finalizes
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
from backend.etl.segment_assign import nearest_segment  # noqa: E402
from backend.etl.events_backfill import load_curated_events  # noqa: E402
import json  # noqa: E402

RADAR_URL = "https://data.austintexas.gov/resource/i626-g7ub.json"
LOC_PATH = Path(__file__).resolve().parents[1] / "data" / "geo" / "radar_detector_locations.json"
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "training" / "_radar_rows.csv"
EVENTS_PATH = Path(__file__).resolve().parents[1] / "data" / "events" / "austin_major_events.csv"

# The dataset spans 2017-2021. 2020 (COVID lockdown) and 2021 (partial recovery)
# have atypically light traffic that biases the learned congestion patterns, so
# the default pulls the PRE-COVID years (2017 partial + full 2018/2019). Override
# with RADAR_YEARS="2018,2019".
DEFAULT_RADAR_YEARS = [2017, 2018, 2019]


def parse_years(raw: str) -> list[int]:
    """Parse a comma-separated RADAR_YEARS string; fall back to the pre-COVID set."""
    years = [int(p) for p in raw.split(",") if p.strip()]
    return years or list(DEFAULT_RADAR_YEARS)


RADAR_YEARS = parse_years(os.environ.get("RADAR_YEARS", ""))
MAX_READINGS = int(os.environ.get("RADAR_MAX_READINGS", "300000"))  # total, split across years
PAGE = 50_000
MIN_VOLUME = 2   # low-volume bins give noisy single-vehicle speeds
APP_TOKEN = os.environ.get("SOCRATA_APP_TOKEN") or None


def _headers() -> dict:
    return {"X-App-Token": APP_TOKEN} if APP_TOKEN else {}


def _fetch_readings(int_ids: list[str], years: list[int]) -> list[dict]:
    """Pull a balanced sample across `years` (each year gets an equal share of the
    total cap) so no single year dominates the learned pattern."""
    id_list = ",".join(int_ids)
    per_year = max(1, MAX_READINGS // len(years))
    rows: list[dict] = []
    with httpx.Client(timeout=120.0) as c:
        for yr in years:
            got, offset = 0, 0
            while got < per_year:
                resp = c.get(RADAR_URL, params={
                    "$select": "int_id,detid,speed,volume,year,month,day,hour,minute,day_of_week",
                    "$where": f"int_id in ({id_list}) AND speed > 0 AND volume >= {MIN_VOLUME} "
                              f"AND year = {yr}",
                    "$order": "month,day,hour,minute",
                    "$limit": min(PAGE, per_year - got),
                    "$offset": offset,
                }, headers=_headers())
                resp.raise_for_status()
                batch = resp.json()
                if not batch:
                    break
                rows.extend(batch)
                got += len(batch)
                offset += len(batch)
            print(f"  {yr}: {got:,} readings")
    return rows


def _to_dt(r: dict) -> datetime | None:
    """Date each reading by its OWN year (rows now span multiple years)."""
    try:
        return datetime(int(r["year"]), int(r["month"]), int(r["day"]),
                        int(r["hour"]), int(r.get("minute", 0)))
    except (KeyError, ValueError, TypeError):
        return None


def main() -> int:
    if not LOC_PATH.exists():
        print(f"[ERROR] {LOC_PATH} missing. Run scripts/geocode_radar_detectors.py first.")
        return 1
    locations = {str(k): tuple(v) for k, v in json.loads(LOC_PATH.read_text()).items()}
    print(f"{len(locations)} geocoded radar intersections")

    segments = load_segments()
    if not segments:
        print("[ERROR] No segments. Run scripts/fetch_austin_network.py first.")
        return 1

    print(f"Fetching radar readings for years {RADAR_YEARS} ...")
    raw = _fetch_readings(list(locations.keys()), RADAR_YEARS)
    print(f"  {len(raw)} readings total")
    if not raw:
        print("[ERROR] No radar rows returned.")
        return 1

    # Free-flow speed per detector lane (detid).
    speeds_by_det: dict[str, list[float]] = defaultdict(list)
    for r in raw:
        try:
            speeds_by_det[r["detid"]].append(float(r["speed"]))
        except (KeyError, ValueError, TypeError):
            continue
    free_flow = {d: free_flow_speed(s) for d, s in speeds_by_det.items()}

    events = load_curated_events(EVENTS_PATH)
    stamps = [f"{int(r['year'])}-{int(r['month']):02d}-{int(r['day']):02d}" for r in raw
              if r.get("year") and r.get("month") and r.get("day")]
    weather = fetch_historical_weather(min(stamps), max(stamps)) if stamps else {}
    print(f"  {len(events)} curated events, {len(weather)} weather hours")

    # Cache the nearest segment per intersection (all its detectors share it).
    seg_by_int: dict[str, dict] = {}
    for int_id, (lat, lng) in locations.items():
        seg = nearest_segment(lat, lng, segments)
        if seg is not None:
            seg_by_int[int_id] = {
                "road_class": seg["road_class"], "centroid_lat": lat, "centroid_lng": lng,
                "dist_downtown_km": dist_to_downtown_km(lat, lng), "segment_id": seg["segment_id"],
            }

    rows_out: list[dict] = []
    skipped = 0
    for r in raw:
        ff = free_flow.get(r.get("detid"))
        seg = seg_by_int.get(str(r.get("int_id")))
        dt = _to_dt(r)
        if not ff or seg is None or dt is None:
            skipped += 1
            continue
        wx_key = f"{int(r['year'])}-{int(r['month']):02d}-{int(r['day']):02d}T{int(r['hour']):02d}"
        wx = weather.get(wx_key[:13], {"weather_code": 0, "temperature_f": 78.0, "precipitation_in": 0.0})
        feat = build_feature_row(
            seg, dt, int(wx["weather_code"]), float(wx["temperature_f"]), float(wx["precipitation_in"]),
            events,
        )
        feat[TARGET_COLUMN] = congestion_pct_from_speed(float(r["speed"]), ff)
        feat["_segment_id"] = seg["segment_id"]
        rows_out.append(feat)

    print(f"  built {len(rows_out)} rows, skipped {skipped}")
    if not rows_out:
        print("[ERROR] No rows built.")
        return 1

    df = pd.DataFrame(rows_out)[FEATURE_ORDER + [TARGET_COLUMN, "_segment_id"]]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(df):,} radar rows -> {OUT_PATH}")
    print(f"  distinct segments from radar: {df['_segment_id'].nunique()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
