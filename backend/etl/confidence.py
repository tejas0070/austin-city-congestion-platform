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


# --- Conformal interval calibration (lever 1) -------------------------------
# The raw q25/q75 quantile band is systematically too narrow (it covered ~44%
# instead of the nominal 50%), so its width understates real spread and inflates
# confidence everywhere. Split-conformal calibration finds a single additive
# adjustment `q` (computed on a held-out calibration fold at train time) such that
# the widened band [low-q, high+q] empirically covers the target fraction. `q` is
# saved with the quantile models and applied at serving before width->confidence.

def compute_conformal_q(low_preds, high_preds, y_true, coverage: float = 0.5) -> float:
    """Additive band adjustment so [low-q, high+q] covers ~`coverage` of truths.

    Positive widens (band too narrow), negative narrows (band too wide). Uses the
    finite-sample split-conformal quantile of the conformity scores.
    """
    import numpy as np

    lo = np.asarray(low_preds, dtype=float)
    hi = np.asarray(high_preds, dtype=float)
    y = np.asarray(y_true, dtype=float)
    if lo.size == 0:
        return 0.0
    lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)
    scores = np.maximum(lo - y, y - hi)  # > 0 when the truth falls outside [lo, hi]
    n = scores.size
    level = min(1.0, float(np.ceil((n + 1) * coverage)) / n)
    return float(np.quantile(scores, level, method="higher"))


def conformal_interval(low: float, high: float, q: float) -> tuple[float, float]:
    """Order (low, high) and apply the conformal adjustment `q` to both sides."""
    lo, hi = (low, high) if low <= high else (high, low)
    return lo - q, hi + q


# --- Expected-value interval (lever 3) --------------------------------------
# The map/tooltip shows the model's estimate of the TYPICAL congestion for a
# (corridor, hour-of-week) — a quantity the model predicts to MAE ~2.7, far
# tighter than an individual 15-min reading (MAE ~8.8). The per-reading q25/q75
# band answered the wrong question ("where will one reading land?") and so
# understated how well the DISPLAYED value is known. Instead we attach a
# symmetric interval `pred ± q` whose `q` is split-conformal calibrated (reuse
# `compute_conformal_q` with low==high==pred so the conformity score is
# |true_mean - pred|) to cover the true bucket mean at the nominal rate. Coverage
# is verified on held-out buckets at train time — the interval is only tighter
# because the typical value is genuinely known that well, not by fiat.
#
# Because the calibrated half-width is ~constant across corridors, per-corridor
# confidence differentiation comes from the density cap (real history backing the
# prediction), which still applies on top.

# Absolute width anchors on the EXPECTED-VALUE scale (much smaller than the
# per-reading anchors above). Anchored to TIER-BAND geometry, not tuned to a
# target: tiers are 15 pts wide (green<15, yellow 15-30, red>=30), so an interval
# spanning a full 30-pt band (+/-15) means the tier is a coin flip -> zero
# confidence; within +/-1.5 pts (width 3) the tier is certain -> full confidence.
# The deployed 80% expected-value interval (+/-~4.3 pts) lands around ~79, safely
# above the road-class cap (70) so genuinely-measured corridors read higher than
# fallbacks, and slightly under the measured ~85% bucket tier accuracy.
EV_WIDTH_FULL_CONF = 3.0
EV_WIDTH_ZERO_CONF = 30.0


def expected_value_anchors() -> tuple[float, float]:
    """The fixed (full-confidence, zero-confidence) width anchors for the
    expected-value interval."""
    return EV_WIDTH_FULL_CONF, EV_WIDTH_ZERO_CONF


def expected_value_interval(pred: float, q: float) -> tuple[float, float]:
    """Symmetric interval `pred ± q` for the typical (expected) value.

    Unordered/unclamped by design; callers clamp to [0, 100] after building it.
    """
    return pred - q, pred + q


# A single global `ev_q` makes every corridor read the SAME confidence — the
# score then carries no per-road information beyond the density tier. To restore
# a real signal we redistribute the calibrated average half-width across corridors
# by the model's OWN learned per-reading spread (the q25/q75 band width): where the
# model is genuinely less sure (volatile roads, rush hour) the band is wider, so
# the interval widens and confidence drops, and vice-versa. The scale is bounded so
# no single interval is re-derived far from the calibrated average — the mean
# half-width (hence the held-out coverage it was calibrated to) is preserved.
EV_SCALE_MIN = 0.5
EV_SCALE_MAX = 2.0


def modulated_half_width(
    ev_q: float, width: float | None, ref_width: float | None,
) -> float:
    """Scale the calibrated EV half-width `ev_q` by this row's relative uncertainty.

    `width` is the model's per-reading band width (q75-q25) for the row; `ref_width`
    is the population-average band width recorded at train time. The half-width is
    `ev_q * clamp(width / ref_width, EV_SCALE_MIN, EV_SCALE_MAX)`. Falls back to the
    unmodulated `ev_q` when either input is missing/degenerate (older artifacts),
    so serving never breaks.
    """
    if ref_width is None or ref_width <= 0 or width is None or width < 0:
        return float(ev_q)
    scale = max(EV_SCALE_MIN, min(EV_SCALE_MAX, float(width) / float(ref_width)))
    return float(ev_q) * scale


# --- Density-aware confidence cap (lever 2) ---------------------------------
# A prediction must be no more confident than the real history backing it.
# `seasonal_level` resolves per-(segment, hour-of-week) from a tiered prior:
#   "segment"    real history for this exact road+hour  (trust scales with count)
#   "road_class" only the road-class average is known   (capped)
#   "global"     only the city-wide mean is known       (capped lowest)
# This stops the model reading "most confident where it knows least" — fallback
# roads can no longer out-confidence well-measured corridors.

SUPPORT_FULL = 12           # per-segment hour-of-week readings earning full trust
ROAD_CLASS_CONF_CAP = 70.0  # ceiling when falling back to the road-class average
GLOBAL_CONF_CAP = 50.0      # ceiling when only the global mean is available


def density_confidence_cap(tier: str, count: int = 0) -> float:
    """The maximum confidence justified by the data tier backing a prediction."""
    if tier == "segment":
        weight = min(1.0, max(0, int(count)) / SUPPORT_FULL)
        return ROAD_CLASS_CONF_CAP + (100.0 - ROAD_CLASS_CONF_CAP) * weight
    if tier == "road_class":
        return ROAD_CLASS_CONF_CAP
    return GLOBAL_CONF_CAP  # "global" / unknown — least-supported


def apply_density_cap(confidence: float, tier: str, count: int = 0) -> float:
    """Cap `confidence` by data support; never raises an already-low value."""
    return round(min(float(confidence), density_confidence_cap(tier, count)), 1)
