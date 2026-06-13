#!/usr/bin/env python3
"""Train the corridor-congestion prediction model.

Reads data/training/congestion_history.csv, trains a gradient-boosting
regressor on the engineered features, reports held-out metrics, and saves the
fitted model to data/models/congestion_model.pkl.

Run from the project root after generating training data:
    python scripts/generate_training_data.py
    python scripts/train_model.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import joblib  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402
from sklearn.metrics import mean_absolute_error, r2_score  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder  # noqa: E402

from backend.services.congestion_features import (  # noqa: E402
    NUMERIC_FEATURES,
    CATEGORICAL_FEATURES,
    TARGET_COLUMN,
)

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "training" / "congestion_history.csv"
MODEL_PATH = Path(__file__).resolve().parents[1] / "data" / "models" / "congestion_model.pkl"
META_PATH = Path(__file__).resolve().parents[1] / "data" / "models" / "model_meta.json"

RANDOM_STATE = 42


def main() -> int:
    if not DATA_PATH.exists():
        print(f"[ERROR] Training data not found at {DATA_PATH}")
        print("  Run: python scripts/generate_training_data.py")
        return 1

    print(f"Loading training data from {DATA_PATH} ...")
    df = pd.read_csv(DATA_PATH)
    print(f"  {len(df):,} rows, {len(df.columns)} columns")

    feature_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    x = df[feature_cols]
    y = df[TARGET_COLUMN]

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=RANDOM_STATE
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("road_class", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ],
        remainder="passthrough",
    )
    model = Pipeline(steps=[
        ("prep", preprocessor),
        ("gb", HistGradientBoostingRegressor(
            max_iter=400,
            learning_rate=0.06,
            max_depth=6,
            l2_regularization=1.0,
            random_state=RANDOM_STATE,
        )),
    ])

    print("Training HistGradientBoostingRegressor ...")
    model.fit(x_train, y_train)

    preds = model.predict(x_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)
    print("\n=== Held-out performance ===")
    print(f"  MAE: {mae:.2f} congestion-percent points")
    print(f"  R^2: {r2:.4f}")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    META_PATH.write_text(json.dumps({
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "feature_order": feature_cols,
        "target": TARGET_COLUMN,
        "model_type": "HistGradientBoostingRegressor",
        "test_mae": round(float(mae), 3),
        "test_r2": round(float(r2), 4),
        "training_rows": int(len(df)),
    }, indent=2), encoding="utf-8")

    print(f"\nSaved model to {MODEL_PATH}")
    print(f"Saved metadata to {META_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
