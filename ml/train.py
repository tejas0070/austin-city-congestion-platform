"""
ML Training — Austin City Congestion Platform

Trains a RandomForestRegressor on data/processed/merged_features.csv
to predict congestion_index (0.0 = free-flowing, 1.0 = fully stopped).

Run offline after transform.py has produced the processed dataset.
Never call this from inside API routes — use ml/predict.py instead.

Usage:
    python ml/train.py
"""

import os
import sys

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

PROCESSED_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "processed", "merged_features.csv"
)
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODELS_DIR, "congestion_rf.joblib")
ENCODER_PATH = os.path.join(MODELS_DIR, "impact_encoder.joblib")

NUMERIC_FEATURES = [
    "current_speed_mph",
    "free_flow_speed_mph",
    "weather_temp_f",
    "weather_humidity_pct",
    "weather_wind_speed_mph",
    "weather_cloud_cover_pct",
    "weather_rain_1h_mm",
    "nearby_event_count",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
]

CATEGORICAL_FEATURES = [
    "weather_traffic_impact_level",  # Low / Moderate / High / Severe
]

TARGET = "congestion_index"


def load_features(path: str) -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(path, parse_dates=["timestamp"])

    # Drop rows where the target is missing
    df = df.dropna(subset=[TARGET])

    # Fill numeric NaNs with column median
    df[NUMERIC_FEATURES] = df[NUMERIC_FEATURES].apply(
        lambda col: col.fillna(col.median())
    )

    # Encode categorical feature
    le = LabelEncoder()
    df["weather_traffic_impact_level_enc"] = le.fit_transform(
        df["weather_traffic_impact_level"].fillna("Low")
    )

    feature_cols = NUMERIC_FEATURES + ["weather_traffic_impact_level_enc"]
    X = df[feature_cols]
    y = df[TARGET]
    return X, y, le


def train() -> None:
    print("=" * 60)
    print("  Austin Congestion ML — Training")
    print("=" * 60)

    if not os.path.exists(PROCESSED_FILE):
        print(f"[-] Processed file not found: {PROCESSED_FILE}")
        print("    Run etl/transform.py first.")
        sys.exit(1)

    print(f"\n[1/4] Loading features from: {PROCESSED_FILE}")
    X, y, le = load_features(PROCESSED_FILE)
    print(f"  Samples : {len(X)}")
    print(f"  Features: {list(X.columns)}")
    print(f"  Target  : {TARGET}  (mean={y.mean():.4f}, std={y.std():.4f})")

    print("\n[2/4] Splitting train/test (80/20)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"  Train: {len(X_train)}  |  Test: {len(X_test)}")

    print("\n[3/4] Training RandomForestRegressor...")
    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=10,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    print(f"  MAE : {mae:.4f}")
    print(f"  R²  : {r2:.4f}")

    print("\n[4/4] Saving model artifacts...")
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(le, ENCODER_PATH)
    print(f"  Model   : {MODEL_PATH}")
    print(f"  Encoder : {ENCODER_PATH}")

    print("\n[+] Training complete.")
    print("=" * 60)


if __name__ == "__main__":
    train()
