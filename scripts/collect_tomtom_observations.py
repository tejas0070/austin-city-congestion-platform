#!/usr/bin/env python3
"""Collect real per-segment congestion from TomTom and append to a log.

The free TomTom tier (~2,500 requests/day) can't refresh all ~3,800 segments
live, so this samples a budget-bounded, randomly-rotated subset each run and
appends timestamped real congestion to data/training/tomtom_observations.csv.
Run it on a schedule (e.g. a few times a day across different hours); over time
the log accumulates real hour-of-week coverage for many segments, which
build_real_training_data.py folds into `seasonal_level` — raising honest
confidence on those roads.

Setup:
    1. Get a free key at https://developer.tomtom.com (Traffic Flow API).
    2. Put TOMTOM_API_KEY=... in the project .env (already gitignored).
    3. python scripts/collect_tomtom_observations.py        # one sample run

Env knobs: TOMTOM_SAMPLE (segments per run, default 400), TOMTOM_DELAY (seconds
between calls, default 0.2).
"""
from __future__ import annotations

import csv
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()  # read TOMTOM_API_KEY from the project .env

from backend.services.segments_service import load_segments  # noqa: E402
from backend.services.tomtom_service import fetch_flow_segment, tomtom_available  # noqa: E402
from backend.services.tomtom_budget import reserve, remaining_today, DAILY_LIMIT  # noqa: E402

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "training" / "tomtom_observations.csv"
SAMPLE = int(os.environ.get("TOMTOM_SAMPLE", "400"))
DELAY = float(os.environ.get("TOMTOM_DELAY", "0.2"))
FIELDS = ["timestamp", "segment_id", "road_class", "lat", "lng", "congestion_pct", "confidence"]


def _sample_segments(segments: list[dict], n: int) -> list[dict]:
    """Random subset (rotates coverage across runs). Majors are weighted in by
    listing them twice so corridors get sampled a bit more often."""
    weighted = list(segments)
    weighted += [s for s in segments if s["road_class"] in ("motorway", "trunk", "primary")]
    random.shuffle(weighted)
    seen, picked = set(), []
    for s in weighted:
        if s["segment_id"] in seen:
            continue
        seen.add(s["segment_id"])
        picked.append(s)
        if len(picked) >= n:
            break
    return picked


def main() -> int:
    if not tomtom_available():
        print("[ERROR] TOMTOM_API_KEY not set. Add it to .env (see script docstring).")
        return 1

    segments = load_segments()
    if not segments:
        print("[ERROR] No segments. Run scripts/fetch_austin_network.py first.")
        return 1

    # Reserve from the hard daily budget FIRST — never exceed the free tier.
    want = min(SAMPLE, len(segments))
    granted = reserve(want)
    if granted <= 0:
        # Exit code 2 signals "budget spent, nothing collected" so the self-updater
        # can skip the redundant retrain (no new data) — but ONLY in this case.
        print(f"[STOP] Daily TomTom budget exhausted ({DAILY_LIMIT}/day). "
              f"Try again tomorrow.")
        return 2
    if granted < want:
        print(f"[NOTE] Capping this run to {granted} to stay under the daily budget.")

    sample = _sample_segments(segments, granted)
    print(f"Sampling {len(sample)} of {len(segments)} segments "
          f"(reserved {granted}; {remaining_today()} left in today's budget)")

    now = datetime.now().isoformat(timespec="minutes")
    rows, failures = [], 0
    with httpx.Client(timeout=15.0) as client:
        for seg in sample:
            flow = fetch_flow_segment(seg["centroid_lat"], seg["centroid_lng"], client=client)
            if flow is None:
                failures += 1
            else:
                rows.append({
                    "timestamp": now,
                    "segment_id": seg["segment_id"],
                    "road_class": seg["road_class"],
                    "lat": round(seg["centroid_lat"], 6),
                    "lng": round(seg["centroid_lng"], 6),
                    "congestion_pct": flow["congestion_pct"],
                    "confidence": flow["confidence"],
                })
            time.sleep(DELAY)

    if not rows:
        print(f"[ERROR] No readings collected ({failures} failures). Check the key/network.")
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_file = not OUT_PATH.exists()
    with OUT_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)

    total = sum(1 for _ in OUT_PATH.open(encoding="utf-8")) - 1
    print(f"Appended {len(rows)} readings ({failures} failures) -> {OUT_PATH}")
    print(f"  log now holds {total:,} observations across runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
