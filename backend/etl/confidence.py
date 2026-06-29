# backend/etl/confidence.py
"""Convert a prediction-interval width into a 0-100 confidence score.

A tight band (small q90-q10 spread) means the model is confident; a wide band
means it is not. Width is normalised between two ABSOLUTE, fixed anchors (in
congestion-percent points) and inverted.

The anchors are deliberately fixed (not data-driven percentiles) so the score is
interpretable and stable across retrains: "80% confidence" always means the same
interval width. It also means a genuinely better model (narrower intervals)
shows up as higher confidence, instead of being re-normalised away.
"""
from __future__ import annotations

HIGH_THRESHOLD = 75.0
MEDIUM_THRESHOLD = 50.0

# Absolute interval-width anchors (q90-q10 spread, in congestion-percent points).
# An interval at/under FULL maps to 100% confidence; at/over ZERO maps to 0%.
# Chosen from the real-data model's width distribution so a well-predicted road
# reads high and a volatile one reads low (see docs/model_card.md).
ABS_WIDTH_FULL_CONF = 8.0
ABS_WIDTH_ZERO_CONF = 45.0


def absolute_width_anchors() -> tuple[float, float]:
    """The fixed (full-confidence, zero-confidence) interval-width anchors."""
    return ABS_WIDTH_FULL_CONF, ABS_WIDTH_ZERO_CONF


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
