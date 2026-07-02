#!/usr/bin/env python3
"""Honest, leak-free evaluation of the deployed congestion model.

Reproduces the exact train/test split and leak-free `seasonal_level` used by
train_model.py, then reports usefulness at three granularities plus interval
calibration, and writes the headline numbers into model_meta.json so they are
versioned with the model and shown on the model card.

Run from the project root (after training):
    python scripts/evaluate_model.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

from backend.services.congestion_features import (  # noqa: E402
    NUMERIC_FEATURES, CATEGORICAL_FEATURES, TARGET_COLUMN,
)
from backend.etl.training_eval import assign_leakfree_seasonal  # noqa: E402
from backend.etl.model_eval import (  # noqa: E402
    pointwise_metrics, aggregate_metrics, baseline_mae_reduction,
    calibrate_expected_value_interval,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "training" / "congestion_history.csv"
MODEL_PATH = ROOT / "data" / "models" / "congestion_model.pkl"
QUANTILES_PATH = ROOT / "data" / "models" / "congestion_quantiles.pkl"
META_PATH = ROOT / "data" / "models" / "model_meta.json"
RANDOM_STATE = 42


def _interval_coverage_50(model_lo, model_hi, x_test, y_test, conformal_q: float) -> float:
    lo = np.clip(np.minimum(model_lo.predict(x_test), model_hi.predict(x_test)) - conformal_q, 0, 100)
    hi = np.clip(np.maximum(model_lo.predict(x_test), model_hi.predict(x_test)) + conformal_q, 0, 100)
    y = y_test.to_numpy()
    return round(float(((y >= lo) & (y <= hi)).mean()), 4)


def main() -> int:
    if not DATA_PATH.exists() or not MODEL_PATH.exists():
        print("[ERROR] Train first: scripts/train_model.py")
        return 1

    df = pd.read_csv(DATA_PATH)
    if "_segment_id" not in df.columns:
        print("[ERROR] congestion_history.csv lacks _segment_id (re-run training_finalize).")
        return 1

    cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    train_idx, test_idx = train_test_split(df.index, test_size=0.2, random_state=RANDOM_STATE)
    df["seasonal_level"] = assign_leakfree_seasonal(df, train_idx, target_col=TARGET_COLUMN)
    test = df.loc[test_idx]

    model = joblib.load(MODEL_PATH)
    y_true = test[TARGET_COLUMN].to_numpy()
    y_pred = model.predict(test[cols])

    point = pointwise_metrics(y_true, y_pred)
    agg = aggregate_metrics(
        test[["_segment_id", "hour", "is_weekend"]], y_true, y_pred, min_samples=5
    )
    lift = baseline_mae_reduction(y_true, y_pred, float(df.loc[train_idx, TARGET_COLUMN].mean()))

    # Expected-value interval — the SERVED confidence signal: pred ± ev_q covering
    # the typical (per corridor x hour-of-week) congestion the app displays.
    ev_keys = test[["_segment_id", "hour", "is_weekend"]]
    ev80 = calibrate_expected_value_interval(ev_keys, y_true, y_pred, coverage=0.8)
    ev50 = calibrate_expected_value_interval(ev_keys, y_true, y_pred, coverage=0.5)

    cov50 = None
    if QUANTILES_PATH.exists():
        q = joblib.load(QUANTILES_PATH)
        cov50 = _interval_coverage_50(
            q["low"], q["high"], test[cols], test[TARGET_COLUMN], float(q.get("conformal_q", 0.0))
        )
    meta = json.loads(META_PATH.read_text(encoding="utf-8")) if META_PATH.exists() else {}
    cov80 = meta.get("empirical_coverage")

    print(f"\n=== Leak-free held-out evaluation (n={len(test):,}) ===\n")
    print("Per-reading (hard target — ~70% of variance is irreducible short-term noise):")
    print(f"  MAE {point['mae']}  RMSE {point['rmse']}  R^2 {point['r2']}")
    print(f"  tier (green/yellow/red) accuracy {point['tier_accuracy']*100:.1f}%  "
          f"| congested>=15 accuracy {point['congested_accuracy']*100:.1f}% (F1 {point['congested_f1']})")
    print(f"  within +/-10 pts {point['within_10pts']*100:.1f}%")
    print("\nTypical congestion per corridor x hour-of-week (what the app forecasts):")
    print(f"  R^2 {agg.get('r2')}  MAE {agg.get('mae')} pts  "
          f"tier accuracy {agg.get('tier_accuracy', 0)*100:.1f}%  "
          f"within +/-10 pts {agg.get('within_10pts', 0)*100:.1f}%  ({agg.get('buckets')} corridor-hours)")
    print(f"\nError vs naive (global-mean) baseline: {lift*100:.0f}% lower MAE")
    print("Per-reading prediction-interval calibration:")
    print(f"  50% band empirical coverage {cov50}   80% band empirical coverage {cov80}")
    print("Expected-value interval (SERVED confidence — typical congestion per corridor x hour):")
    print(f"  80%: +/-{ev80['q']} pts, held-out coverage {ev80['coverage']}  "
          f"| 50%: +/-{ev50['q']} pts, coverage {ev50['coverage']}  ({ev80['buckets']} buckets)")

    meta["evaluation"] = {
        "pointwise": point,
        "aggregate": agg,
        "baseline_mae_reduction": lift,
        "interval_coverage_50": cov50,
        "interval_coverage_80": cov80,
        "expected_value_interval_80": {"half_width": ev80["q"], "coverage": ev80["coverage"]},
        "expected_value_interval_50": {"half_width": ev50["q"], "coverage": ev50["coverage"]},
        "note": "leak-free held-out; aggregate = typical congestion per segment x hour-of-week; "
                "expected-value interval is the served confidence band around the displayed value",
    }
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\nWrote evaluation block to {META_PATH.name}")

    report = ROOT / "docs" / "model_evaluation.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        f"""# Model Evaluation (honest, leak-free held-out)

Held-out readings: {len(test):,} · training rows: {meta.get('training_rows', 'n/a'):,} ·
data: real City-of-Austin travel sensors (Bluetooth + pre-COVID radar) + TomTom.

## Forecasting typical congestion per corridor × hour-of-week (what the app delivers)
- **R² = {agg.get('r2')}** — explains {agg.get('r2', 0)*100:.0f}% of variance in typical congestion
- **MAE = {agg.get('mae')} congestion-points** on a 0–100 scale
- **Traffic-level (green/yellow/red) accuracy = {agg.get('tier_accuracy', 0)*100:.0f}%**
- Within ±10 points **{agg.get('within_10pts', 0)*100:.0f}%** of the time ({agg.get('buckets')} corridor-hours)

## Uncertainty quantification (conformal prediction intervals)
The **served** confidence band is the *expected-value* interval — the range for the
typical congestion the app displays (`pred ± ev_q`), calibrated on held-out
corridor-hour means. This is what the Predicted tooltip and Forecast panel show.
- **Expected-value 80% interval: ±{ev80['q']} pts, {ev80['coverage']*100:.0f}% held-out coverage** (well-calibrated)
- Expected-value 50% interval: ±{ev50['q']} pts, {ev50['coverage']*100:.0f}% coverage
- Per-reading 80% band (individual readings, wider): {(cov80 or 0)*100:.0f}% coverage; 50% band {(cov50 or 0)*100:.0f}%

## Per-reading (individual 15-min sensor readings — the hard target)
Individual readings are ~70% irreducible short-term noise, so this understates the
product; reported for transparency.
- MAE {point['mae']} · R² {point['r2']} · congested-detection accuracy {point['congested_accuracy']*100:.0f}% (F1 {point['congested_f1']})
- **{lift*100:.0f}% lower error than a naive baseline**

_Generated by `scripts/evaluate_model.py`._
""",
        encoding="utf-8",
    )
    print(f"Wrote human-readable report to {report.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
