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
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()  # read TOMTOM_API_KEY from the project .env

from backend.services.segments_service import load_display_segments  # noqa: E402
from backend.services.tomtom_service import fetch_flow_segment, tomtom_available  # noqa: E402
from backend.services.tomtom_budget import reserve, remaining_today, DAILY_LIMIT  # noqa: E402

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "training" / "tomtom_observations.csv"
SAMPLE = int(os.environ.get("TOMTOM_SAMPLE", "400"))
DELAY = float(os.environ.get("TOMTOM_DELAY", "0.2"))
FIELDS = ["timestamp", "segment_id", "road_class", "lat", "lng", "congestion_pct", "confidence"]

# Corridors worth building real per-segment diurnal depth on. Concentrating the
# budget here (rather than sampling the whole city shallowly) is what lets a road
# accumulate enough real hour-of-week history to honestly leave the confidence
# fallback cap (backend/etl/confidence.density_confidence_cap).
PRIORITY_CLASSES = ("motorway", "trunk", "primary")
PRIORITY_FRACTION = float(os.environ.get("TOMTOM_PRIORITY_FRACTION", "0.8"))


def _is_weekend(dt: datetime) -> int:
    return 1 if dt.weekday() >= 5 else 0


def log_state(path, now: datetime) -> tuple[dict[str, int], set[str]]:
    """Read the observation log for depth-ordering + honest dedup.

    Returns (bucket_counts, already_done):
      * bucket_counts[segment_id] = DISTINCT prior days observed for this run's
        (hour, is_weekend) bucket — the real depth we already have for this
        hour-of-week (counted by distinct date, so redundant intra-day readings
        can never inflate it).
      * already_done = segments already logged on this exact (date, hour), so this
        run never adds a second reading to a bucket within the same day. That
        keeps a bucket's support == distinct observation days, so concentrating
        collection can't manufacture confidence — only genuine repeat visits
        across days deepen a road.
    """
    path = Path(path)
    if not path.exists():
        return {}, set()
    cur_wk, cur_date, cur_hour = _is_weekend(now), now.date().isoformat(), now.hour
    bucket_dates: dict[str, set] = defaultdict(set)
    already_done: set[str] = set()
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ts, sid = row.get("timestamp", ""), row.get("segment_id", "")
            if not ts or not sid:
                continue
            try:
                dt = datetime.fromisoformat(ts)
            except ValueError:
                continue
            if dt.hour == cur_hour and _is_weekend(dt) == cur_wk:
                bucket_dates[sid].add(dt.date())
            if dt.hour == cur_hour and dt.date().isoformat() == cur_date:
                already_done.add(sid)
    return {sid: len(dates) for sid, dates in bucket_dates.items()}, already_done


def select_segments(
    segments: list[dict],
    want: int,
    *,
    obs_counts: dict[str, int],
    already_done: set[str],
    priority_fraction: float = PRIORITY_FRACTION,
) -> list[dict]:
    """Pick up to `want` segments to collect this run.

    Spends `priority_fraction` of the budget deepening the THINNEST-covered
    priority corridors first (even, representative diurnal depth), then fills the
    remainder for breadth. Segments already collected this (date, hour) are
    excluded so support stays a count of distinct days.
    """
    if want <= 0:
        return []
    pool = [s for s in segments if s["segment_id"] not in already_done]

    def depth(s: dict) -> tuple[int, str]:
        return obs_counts.get(s["segment_id"], 0), s["segment_id"]

    majors = sorted((s for s in pool if s["road_class"] in PRIORITY_CLASSES), key=depth)
    others = sorted((s for s in pool if s["road_class"] not in PRIORITY_CLASSES), key=depth)

    n_priority = min(len(majors), round(want * priority_fraction))
    picked = majors[:n_priority]
    remainder = majors[n_priority:] + others
    picked += remainder[: max(0, want - len(picked))]
    return picked[:want]


def main() -> int:
    if not tomtom_available():
        print("[ERROR] TOMTOM_API_KEY not set. Add it to .env (see script docstring).")
        return 1

    segments = load_display_segments()
    if not segments:
        print("[ERROR] No segments. Run scripts/fetch_austin_network.py first.")
        return 1

    # Choose which segments to deepen BEFORE reserving, so budget is spent only on
    # segments we'll actually collect (dedup can drop some), and depth builds on
    # the thinnest-covered priority corridors first.
    now_dt = datetime.now()
    bucket_counts, already_done = log_state(OUT_PATH, now_dt)
    want = min(SAMPLE, len(segments))
    candidates = select_segments(
        segments, want, obs_counts=bucket_counts, already_done=already_done
    )
    if not candidates:
        print("[NOTE] Every candidate segment was already collected this hour; "
              "nothing new to add. Try a later hour to deepen other buckets.")
        return 0

    # Reserve from the hard daily budget — never exceed the free tier.
    granted = reserve(len(candidates))
    if granted <= 0:
        # Exit code 2 signals "budget spent, nothing collected" so the self-updater
        # can skip the redundant retrain (no new data) — but ONLY in this case.
        print(f"[STOP] Daily TomTom budget exhausted ({DAILY_LIMIT}/day). "
              f"Try again tomorrow.")
        return 2
    if granted < len(candidates):
        print(f"[NOTE] Capping this run to {granted} to stay under the daily budget.")

    sample = candidates[:granted]
    n_priority = sum(1 for s in sample if s["road_class"] in PRIORITY_CLASSES)
    print(f"Collecting {len(sample)} segments ({n_priority} priority corridors, "
          f"deepening thinnest {_is_weekend(now_dt) and 'weekend' or 'weekday'} "
          f"{now_dt.hour}:00 buckets first; {remaining_today()} left in today's budget)")

    now = now_dt.isoformat(timespec="minutes")
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
