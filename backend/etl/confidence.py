# backend/etl/confidence.py
"""Convert a prediction-interval width into a 0-100 confidence score.

A tight band (small q90-q10 spread) means the model is confident; a wide band
means it is not. Width is normalised between two data-calibrated anchors
(5th/95th percentile interval widths from training) and inverted.
"""
from __future__ import annotations

HIGH_THRESHOLD = 75.0
MEDIUM_THRESHOLD = 50.0


def clamp_interval(q_low: float, q_high: float) -> tuple[float, float]:
    """Order a (possibly crossed) quantile pair and clamp both to [0, 100]."""
    low, high = (q_low, q_high) if q_low <= q_high else (q_high, q_low)
    low = max(0.0, min(100.0, float(low)))
    high = max(0.0, min(100.0, float(high)))
    return low, high


def width_to_confidence(width: float, low_anchor: float, high_anchor: float) -> float:
    """Map interval width to confidence in [0, 100]; tighter band -> higher."""
    span = high_anchor - low_anchor
    if span <= 0:
        return 100.0
    frac = (width - low_anchor) / span
    frac = max(0.0, min(1.0, frac))
    return round((1.0 - frac) * 100.0, 1)


def confidence_label(confidence_pct: float) -> str:
    if confidence_pct >= HIGH_THRESHOLD:
        return "High"
    if confidence_pct >= MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"
