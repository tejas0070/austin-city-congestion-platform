# backend/etl/congestion.py
"""Derive congestion percentage from observed vs free-flow speed."""
from __future__ import annotations

FREE_FLOW_PERCENTILE = 0.85


def free_flow_speed(speeds: list[float]) -> float | None:
    """Free-flow reference = 85th-percentile observed speed for a sensor."""
    clean = [float(s) for s in speeds if s is not None and float(s) > 0]
    if not clean:
        return None
    clean.sort()
    # nearest-rank percentile
    idx = min(len(clean) - 1, int(round(FREE_FLOW_PERCENTILE * (len(clean) - 1))))
    return clean[idx]


def congestion_pct_from_speed(speed: float, free_flow: float) -> float:
    """congestion = 100 * (1 - speed/free_flow), clamped to [0, 100]."""
    if not free_flow or free_flow <= 0:
        return 0.0
    pct = 100.0 * (1.0 - float(speed) / float(free_flow))
    return round(max(0.0, min(100.0, pct)), 1)
