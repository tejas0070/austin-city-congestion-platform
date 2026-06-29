#!/usr/bin/env python3
"""Before/after report for the seasonal autoregressive feature.

Trains the point + q10/q90 models twice on the SAME real data — once WITHOUT the
`seasonal_level` feature (baseline) and once WITH it (improved) — and compares
point accuracy, interval width, and confidence (under the deployed absolute
anchors). Both variants use the same anchors so the only thing that changes is
the feature, isolating its effect.

Run from the project root:
    python scripts/confidence_report.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402
from sklearn.metrics import mean_absolute_error, r2_score  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder  # noqa: E402

from backend.services.congestion_features import (  # noqa: E402
    NUMERIC_FEATURES, CATEGORICAL_FEATURES, TARGET_COLUMN,
)
from backend.etl.confidence import absolute_width_anchors, width_to_confidence  # noqa: E402

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "training" / "congestion_history.csv"
RANDOM_STATE = 42


def _pipe(numeric: list[str], loss=None, quantile=None) -> Pipeline:
    gb_kwargs = dict(max_iter=400, learning_rate=0.06, max_depth=6,
                     l2_regularization=1.0, random_state=RANDOM_STATE)
    if loss:
        gb_kwargs.update(loss=loss, quantile=quantile)
    return Pipeline(steps=[
        ("prep", ColumnTransformer(
            transformers=[("road_class", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES)],
            remainder="passthrough",
        )),
        ("gb", HistGradientBoostingRegressor(**gb_kwargs)),
    ])


def _evaluate(df: pd.DataFrame, numeric: list[str]) -> dict:
    cols = numeric + CATEGORICAL_FEATURES
    x, y = df[cols], df[TARGET_COLUMN]
    x_tr, x_te, y_tr, y_te = train_test_split(x, y, test_size=0.2, random_state=RANDOM_STATE)

    point = _pipe(numeric).fit(x_tr, y_tr)
    preds = point.predict(x_te)

    # Match the deployed confidence signal: the tight central 50% band (q25/q75).
    q25 = _pipe(numeric, loss="quantile", quantile=0.25).fit(x_tr, y_tr)
    q75 = _pipe(numeric, loss="quantile", quantile=0.75).fit(x_tr, y_tr)
    lo = np.minimum(q25.predict(x_te), q75.predict(x_te))
    hi = np.maximum(q25.predict(x_te), q75.predict(x_te))
    widths = np.clip(hi, 0, 100) - np.clip(lo, 0, 100)

    a_low, a_high = absolute_width_anchors()
    conf = np.array([width_to_confidence(float(w), a_low, a_high) for w in widths])
    return {
        "r2": r2_score(y_te, preds),
        "mae": mean_absolute_error(y_te, preds),
        "coverage": float(((y_te >= lo) & (y_te <= hi)).mean()),
        "median_width": float(np.median(widths)),
        "mean_conf": float(conf.mean()),
        "pct_high": float((conf >= 80).mean() * 100),
        "pct_low": float((conf < 50).mean() * 100),
    }


def main() -> int:
    if not DATA_PATH.exists():
        print(f"[ERROR] {DATA_PATH} not found. Run scripts/build_real_training_data.py first.")
        return 1
    df = pd.read_csv(DATA_PATH)
    print(f"Real data: {len(df):,} rows\n")

    baseline_numeric = [f for f in NUMERIC_FEATURES if f != "seasonal_level"]
    print("Training BASELINE (no seasonal_level) ...")
    base = _evaluate(df, baseline_numeric)
    print("Training IMPROVED (with seasonal_level) ...")
    impr = _evaluate(df, NUMERIC_FEATURES)

    a_low, a_high = absolute_width_anchors()
    rows = [
        ("Point R^2 (higher better)", f"{base['r2']:.3f}", f"{impr['r2']:.3f}"),
        ("Point MAE (lower better)", f"{base['mae']:.1f}", f"{impr['mae']:.1f}"),
        ("Interval coverage (~0.80)", f"{base['coverage']:.3f}", f"{impr['coverage']:.3f}"),
        ("Median interval width", f"{base['median_width']:.1f}", f"{impr['median_width']:.1f}"),
        ("Mean confidence", f"{base['mean_conf']:.1f}%", f"{impr['mean_conf']:.1f}%"),
        ("Segments >= 80% conf", f"{base['pct_high']:.0f}%", f"{impr['pct_high']:.0f}%"),
        ("Segments < 50% conf", f"{base['pct_low']:.0f}%", f"{impr['pct_low']:.0f}%"),
    ]
    print(f"\n=== Before / After (absolute anchors {a_low}/{a_high}) ===")
    print(f"{'Metric':30} {'Baseline':>12} {'Improved':>12}")
    print("-" * 56)
    for name, b, i in rows:
        print(f"{name:30} {b:>12} {i:>12}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
