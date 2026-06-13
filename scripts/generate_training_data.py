#!/usr/bin/env python3
"""Synthesize labelled congestion history across the Austin road network.

Samples a stratified set of real segments (by road class) from
data/geo/austin_network.geojson and generates hourly readings over ~90 days with
random weather and random events. Labels come from the shared
`synthetic_congestion` function so the model has a real relationship to learn.

Run from the project root (after fetching the network):
    python scripts/fetch_austin_network.py
    python scripts/generate_training_data.py

Output: data/training/congestion_history.csv

Stand-in until real per-segment speed history is loaded; swapping in real data
only requires producing a CSV with the same feature + target columns.
"""
from __future__ import annotations

import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd  # noqa: E402

from backend.services.congestion_features import (  # noqa: E402
    FEATURE_ORDER,
    TARGET_COLUMN,
    VENUE_INFO,
    WEATHER_PROFILES,
    build_feature_row,
    synthetic_congestion,
)
from backend.services.segments_service import load_segments  # noqa: E402

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "training" / "congestion_history.csv"

HISTORY_DAYS = 90
SLOT_HOURS = 1                 # hourly readings
SAMPLES_PER_CLASS = 70         # segments sampled per road class
RANDOM_SEED = 42

_WEATHER_CHOICES = ["Clear", "Rain", "Heavy Rain", "Storm"]
_WEATHER_WEIGHTS = [0.62, 0.22, 0.10, 0.06]


def _sample_segments() -> list[dict]:
    """Stratified sample of segments by road class for balanced training."""
    by_class: dict[str, list[dict]] = defaultdict(list)
    for seg in load_segments():
        by_class[seg["road_class"]].append(seg)

    sampled: list[dict] = []
    for road_class, segs in by_class.items():
        k = min(SAMPLES_PER_CLASS, len(segs))
        sampled.extend(random.sample(segs, k))
    return sampled


def _generate_day_events(day: datetime) -> list[dict]:
    events: list[dict] = []
    num = random.choices([0, 1, 2], weights=[0.55, 0.33, 0.12], k=1)[0]
    for venue_key in random.sample(list(VENUE_INFO.keys()), k=num):
        venue = VENUE_INFO[venue_key]
        start_hour = random.choice([17, 18, 19, 19, 20])
        events.append({
            "lat": venue["lat"],
            "lng": venue["lng"],
            "expected_attendance": int(venue["typical"] * random.uniform(0.75, 1.05)),
            "start_dt": day.replace(hour=start_hour, minute=0, second=0, microsecond=0),
        })
    return events


def main() -> int:
    random.seed(RANDOM_SEED)
    segments = _sample_segments()
    if not segments:
        print("[ERROR] No segments found. Run scripts/fetch_austin_network.py first.")
        return 1

    print(f"Synthesizing {HISTORY_DAYS} days x {24 // SLOT_HOURS} slots "
          f"x {len(segments)} segments ...")

    start_day = (datetime.now() - timedelta(days=HISTORY_DAYS)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    rows: list[dict] = []
    for d in range(HISTORY_DAYS):
        day = start_day + timedelta(days=d)
        condition = random.choices(_WEATHER_CHOICES, weights=_WEATHER_WEIGHTS, k=1)[0]
        weather_code, temp_f, precip_in, _ = WEATHER_PROFILES[condition]
        day_events = _generate_day_events(day)

        for hour in range(0, 24, SLOT_HOURS):
            ts = day + timedelta(hours=hour)
            for seg in segments:
                row = build_feature_row(seg, ts, weather_code, temp_f, precip_in, day_events)
                noise = random.gauss(0.0, 2.5)
                row[TARGET_COLUMN] = round(synthetic_congestion(seg, ts, condition, day_events, noise), 2)
                rows.append(row)

    df = pd.DataFrame(rows)
    missing = {*FEATURE_ORDER, TARGET_COLUMN} - set(df.columns)
    if missing:
        print(f"[ERROR] generated frame missing columns: {missing}")
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    print(f"Wrote {len(df):,} rows to {OUT_PATH}")
    print("\nTarget congestion_pct distribution:")
    print(df[TARGET_COLUMN].describe().round(2).to_string())
    print("\nRows with event pressure (>0):", int((df["nearby_event_attendance"] > 0).sum()))
    print("Road-class mix:", df["road_class"].value_counts().to_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main())
