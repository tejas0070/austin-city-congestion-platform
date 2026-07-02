# tests/test_tomtom_sampling.py
"""Depth-building, honesty-preserving TomTom segment selection.

The collector deepens real per-segment diurnal history on priority corridors
(so they can honestly leave the confidence fallback cap) while:
  * excluding segments already collected this (date, hour) — so support counts
    reflect DISTINCT observation days, never redundant intra-window samples;
  * deepening the thinnest-covered buckets first, for even, representative depth.
"""
from datetime import datetime

import pandas as pd

from scripts.collect_tomtom_observations import (
    select_segments,
    log_state,
    PRIORITY_CLASSES,
)
from scripts.build_tomtom_training_data import dedup_observations


def _seg(i, road_class):
    return {"segment_id": f"seg_{i:03d}", "road_class": road_class,
            "centroid_lat": 30.0, "centroid_lng": -97.0}


def test_prioritizes_least_observed_majors_first():
    segs = [_seg(1, "motorway"), _seg(2, "primary"), _seg(3, "primary")]
    # seg_002 already deep at this hour; seg_001/003 thin -> they come first
    obs = {"seg_002": 20, "seg_001": 0, "seg_003": 1}
    picked = select_segments(segs, want=2, obs_counts=obs, already_done=set(),
                             priority_fraction=1.0)
    ids = [s["segment_id"] for s in picked]
    assert ids == ["seg_001", "seg_003"]  # thinnest majors, deepest excluded


def test_excludes_already_collected_this_bucket():
    segs = [_seg(1, "motorway"), _seg(2, "primary")]
    picked = select_segments(segs, want=2, obs_counts={}, already_done={"seg_001"},
                             priority_fraction=1.0)
    ids = [s["segment_id"] for s in picked]
    assert "seg_001" not in ids
    assert ids == ["seg_002"]


def test_respects_want_limit():
    segs = [_seg(i, "primary") for i in range(10)]
    picked = select_segments(segs, want=3, obs_counts={}, already_done=set(),
                             priority_fraction=1.0)
    assert len(picked) == 3


def test_priority_fraction_reserves_budget_for_majors():
    majors = [_seg(i, "motorway") for i in range(5)]
    minors = [_seg(i, "residential") for i in range(100, 105)]
    picked = select_segments(majors + minors, want=10, obs_counts={},
                             already_done=set(), priority_fraction=0.8)
    classes = [s["road_class"] for s in picked]
    # 80% of 10 -> at least 4 majors chosen (all 5 majors fit; rest are minors)
    assert sum(1 for c in classes if c in PRIORITY_CLASSES) >= 4


def test_fills_remainder_with_minors_when_majors_exhausted():
    segs = [_seg(1, "motorway")] + [_seg(i, "residential") for i in range(100, 104)]
    picked = select_segments(segs, want=3, obs_counts={}, already_done=set(),
                             priority_fraction=0.8)
    assert len(picked) == 3  # 1 major + 2 minors to fill


def test_log_state_dedupes_and_counts_current_bucket(tmp_path):
    """log_state returns (bucket_counts, already_done) for the run's (hour, weekend)
    and (date, hour) — the basis for honest, distinct-day support."""
    csv = tmp_path / "obs.csv"
    csv.write_text(
        "timestamp,segment_id,road_class,lat,lng,congestion_pct,confidence\n"
        # two DISTINCT weekdays at 17:00 for seg_001 -> counts as depth 2
        "2026-06-22T17:00,seg_001,primary,30,-97,10,1\n"
        "2026-06-23T17:00,seg_001,primary,30,-97,12,1\n"
        # a different hour for seg_001 -> not in the 17:00 bucket
        "2026-06-23T08:00,seg_001,primary,30,-97,5,1\n"
        # seg_002 already collected TODAY at 17:00 -> must be in already_done
        "2026-06-24T17:00,seg_002,primary,30,-97,8,1\n",
        encoding="utf-8",
    )
    now = datetime(2026, 6, 24, 17, 30)  # Wed 17:xx (weekday), same date+hour as seg_002
    bucket_counts, already_done = log_state(csv, now)
    # seg_001 has two weekday-17:00 observations -> depth 2 in this bucket
    assert bucket_counts.get("seg_001") == 2
    # seg_002 already collected this date+hour -> excluded from this run (dedup)
    assert "seg_002" in already_done
    assert "seg_001" not in already_done  # its 17:00 obs were on other dates


def test_build_dedup_collapses_same_day_hour_to_distinct_days():
    """The reporting-honesty guard: two readings of the same segment in the same
    (date, hour) collapse to one, so support counts distinct days — but two
    DIFFERENT days at the same hour are both kept (genuine depth)."""
    obs = pd.DataFrame([
        {"timestamp": "2026-06-22T17:05", "segment_id": "seg_001", "congestion_pct": 10},
        {"timestamp": "2026-06-22T17:40", "segment_id": "seg_001", "congestion_pct": 14},  # dup day+hour
        {"timestamp": "2026-06-23T17:10", "segment_id": "seg_001", "congestion_pct": 12},  # new day -> kept
        {"timestamp": "bad-timestamp",    "segment_id": "seg_001", "congestion_pct": 99},  # dropped
    ])
    out = dedup_observations(obs)
    assert len(out) == 2  # one per distinct (date, hour); bad row dropped
    assert set(out["congestion_pct"]) == {10, 12}  # keeps first of the dup pair
