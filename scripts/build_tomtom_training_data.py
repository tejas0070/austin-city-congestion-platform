#!/usr/bin/env python3
"""Convert collected TomTom observations into training rows.

Reads the timestamped real congestion log written by
scripts/collect_tomtom_observations.py, joins historical weather + curated
events, and emits feature rows to data/training/_tomtom_rows.csv, which
build_real_training_data.py merges into the combined real training set (so
TomTom-covered segments gain real `seasonal_level`, raising their confidence).

Run from the project root after collecting some observations:
    python scripts/build_tomtom_training_data.py
    python scripts/build_real_training_data.py    # merges + finalizes
    python scripts/train_model.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd  # noqa: E402

from backend.services.congestion_features import (  # noqa: E402
    FEATURE_ORDER, TARGET_COLUMN, build_feature_row,
)
from backend.services.segments_service import load_segments  # noqa: E402
from backend.services.weather_service import fetch_historical_weather  # noqa: E402
from backend.etl.events_backfill import load_curated_events  # noqa: E402

OBS_PATH = Path(__file__).resolve().parents[1] / "data" / "training" / "tomtom_observations.csv"
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "training" / "_tomtom_rows.csv"
EVENTS_PATH = Path(__file__).resolve().parents[1] / "data" / "events" / "austin_major_events.csv"


def dedup_observations(obs: pd.DataFrame) -> pd.DataFrame:
    """Keep at most one reading per (segment, date, hour).

    This is the honesty guard for confidence: a segment's per-hour-of-week support
    (which lifts its density confidence cap) must count DISTINCT observation days,
    not redundant readings taken minutes apart. Without it, concentrating
    collection on a corridor could manufacture support — and thus confidence —
    without adding real knowledge. Rows with an unparseable timestamp are dropped.
    """
    dt = pd.to_datetime(obs.get("timestamp"), errors="coerce")
    kept = obs[dt.notna()].copy()
    daykey = dt[dt.notna()].dt.strftime("%Y-%m-%dT%H")
    kept["_daykey"] = daykey.values
    kept = kept.drop_duplicates(subset=["segment_id", "_daykey"], keep="first")
    return kept.drop(columns="_daykey")


def main() -> int:
    if not OBS_PATH.exists():
        print(f"[ERROR] {OBS_PATH} not found. Run scripts/collect_tomtom_observations.py first.")
        return 1

    obs = pd.read_csv(OBS_PATH)
    raw_n = len(obs)
    obs = dedup_observations(obs)
    print(f"{len(obs):,} TomTom observations ({raw_n - len(obs)} same day+hour "
          f"duplicates dropped), {obs['segment_id'].nunique()} segments")

    seg_by_id = {s["segment_id"]: s for s in load_segments()}
    events = load_curated_events(EVENTS_PATH)
    dates = pd.to_datetime(obs["timestamp"], errors="coerce")
    span = (dates.min(), dates.max())
    weather = fetch_historical_weather(span[0].date().isoformat(), span[1].date().isoformat()) \
        if dates.notna().any() else {}
    print(f"  {len(events)} curated events, {len(weather)} weather hours")

    rows_out: list[dict] = []
    skipped = 0
    for _, o in obs.iterrows():
        seg = seg_by_id.get(o["segment_id"])
        dt = pd.to_datetime(o["timestamp"], errors="coerce")
        if seg is None or pd.isna(dt):
            skipped += 1
            continue
        dt = dt.to_pydatetime()
        wx = weather.get(dt.strftime("%Y-%m-%dT%H"),
                         {"weather_code": 0, "temperature_f": 78.0, "precipitation_in": 0.0})
        feat = build_feature_row(
            seg, dt, int(wx["weather_code"]), float(wx["temperature_f"]),
            float(wx["precipitation_in"]), events,
        )
        feat[TARGET_COLUMN] = round(float(o["congestion_pct"]), 1)
        feat["_segment_id"] = seg["segment_id"]
        rows_out.append(feat)

    if not rows_out:
        print(f"[ERROR] No rows built (skipped {skipped}). Are segment_ids current?")
        return 1

    df = pd.DataFrame(rows_out)[FEATURE_ORDER + [TARGET_COLUMN, "_segment_id"]]
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(df):,} TomTom rows ({df['_segment_id'].nunique()} segments) -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
