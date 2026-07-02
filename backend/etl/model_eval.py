"""Honest, leak-free evaluation metrics for the congestion model.

Three complementary views, because R^2 on individual 15-minute readings (a target
that is ~70% irreducible short-term noise) badly understates real usefulness:

* pointwise  — accuracy on individual readings (the hard target).
* aggregate  — accuracy on TYPICAL congestion per (corridor, hour-of-week), which
               is what the app actually forecasts; noise averages out, so this is
               the number that reflects the product's usefulness.
* classification — how often the predicted GREEN/YELLOW/RED tier (what users see
               on the map) is correct.

All inputs are held-out predictions with leak-free `seasonal_level`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from backend.services.congestion_features import congestion_level
from backend.etl.confidence import compute_conformal_q


def tier_indices(values) -> np.ndarray:
    """Map congestion percentages to tier indices (0 green / 1 yellow / 2 red)."""
    return np.array([congestion_level(float(v))[1] for v in values])


def pointwise_metrics(y_true, y_pred) -> dict:
    """Per-reading accuracy on the raw (noisy) target."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    yt, pt = tier_indices(y_true), tier_indices(y_pred)
    yb, pb = (y_true >= 15).astype(int), (y_pred >= 15).astype(int)
    return {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 3),
        "rmse": round(float(np.sqrt(((y_true - y_pred) ** 2).mean())), 3),
        "r2": round(float(r2_score(y_true, y_pred)), 4),
        "tier_accuracy": round(float(accuracy_score(yt, pt)), 4),
        "congested_accuracy": round(float(accuracy_score(yb, pb)), 4),
        "congested_f1": round(float(f1_score(yb, pb, zero_division=0)), 4),
        "within_10pts": round(float((np.abs(y_true - y_pred) <= 10).mean()), 4),
    }


def aggregate_metrics(keys: pd.DataFrame, y_true, y_pred, min_samples: int = 5) -> dict:
    """Accuracy on TYPICAL congestion per group in `keys` (e.g. segment x hour x
    weekend). Groups with < `min_samples` held-out readings are dropped so each
    group's actual mean is a stable target."""
    g = keys.reset_index(drop=True).copy()
    g["_y"] = np.asarray(y_true, dtype=float)
    g["_p"] = np.asarray(y_pred, dtype=float)
    grouped = g.groupby(list(keys.columns)).agg(
        y=("_y", "mean"), p=("_p", "mean"), n=("_y", "size")
    ).reset_index()
    grouped = grouped[grouped["n"] >= min_samples]
    if len(grouped) == 0:
        return {}
    yt, pt = tier_indices(grouped["y"].to_numpy()), tier_indices(grouped["p"].to_numpy())
    return {
        "buckets": int(len(grouped)),
        "r2": round(float(r2_score(grouped["y"], grouped["p"])), 4),
        "mae": round(float(mean_absolute_error(grouped["y"], grouped["p"])), 3),
        "tier_accuracy": round(float(accuracy_score(yt, pt)), 4),
        "within_10pts": round(float((np.abs(grouped["y"] - grouped["p"]) <= 10).mean()), 4),
    }


def calibrate_expected_value_interval(
    keys: pd.DataFrame, y_true, y_pred, coverage: float = 0.8,
    min_samples: int = 5, seed: int = 42,
) -> dict:
    """Split-conformal calibrate a symmetric interval `pred ± q` for the TYPICAL
    (per-bucket-mean) value, and measure its held-out coverage of the true means.

    Buckets are the groups in `keys` (e.g. segment x hour x weekend) — what the
    app forecasts. For each bucket with >= `min_samples` held-out readings we take
    the mean true congestion and the mean prediction; `q` is the conformal
    `coverage`-quantile of |true_mean - pred_mean|, fit on half the buckets and
    its coverage reported on the disjoint other half (so the number is honest, not
    the fitted-set optimism). Returns {q, coverage, buckets}.
    """
    g = keys.reset_index(drop=True).copy()
    g["_y"] = np.asarray(y_true, dtype=float)
    g["_p"] = np.asarray(y_pred, dtype=float)
    grouped = g.groupby(list(keys.columns)).agg(
        y=("_y", "mean"), p=("_p", "mean"), n=("_y", "size")
    ).reset_index()
    grouped = grouped[grouped["n"] >= min_samples].reset_index(drop=True)
    if len(grouped) == 0:
        return {"q": 0.0, "coverage": 0.0, "buckets": 0}

    if len(grouped) >= 4:
        cal_idx, eval_idx = train_test_split(
            grouped.index, test_size=0.5, random_state=seed
        )
    else:
        cal_idx = eval_idx = grouped.index  # too few buckets to hold out
    cal, ev = grouped.loc[cal_idx], grouped.loc[eval_idx]

    q = compute_conformal_q(
        cal["p"].to_numpy(), cal["p"].to_numpy(), cal["y"].to_numpy(), coverage=coverage
    )
    lo, hi = ev["p"] - q, ev["p"] + q
    emp = float(((ev["y"] >= lo) & (ev["y"] <= hi)).mean())
    return {"q": round(float(q), 4), "coverage": round(emp, 4), "buckets": int(len(grouped))}


def baseline_mae_reduction(y_true, y_pred, baseline_value: float) -> float:
    """Fractional MAE reduction vs. always predicting `baseline_value` (e.g. the
    global mean). 0.24 => the model's error is 24% lower than the naive baseline."""
    y_true = np.asarray(y_true, dtype=float)
    base = mean_absolute_error(y_true, np.full_like(y_true, baseline_value))
    if base <= 0:
        return 0.0
    model = mean_absolute_error(y_true, np.asarray(y_pred, dtype=float))
    return round(float(1.0 - model / base), 4)
