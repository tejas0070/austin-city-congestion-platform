"""Finalize the combined training set from cached per-source row files.

Each real source (Bluetooth, radar, TomTom) writes a raw rows file
`data/training/_<source>_rows.csv` with the model's feature columns plus the
target and a `_segment_id`. This module concatenates them, computes the
leave-one-out `seasonal_level` feature + the serving seasonal prior, and writes
`data/training/congestion_history.csv`.

Splitting this out lets retrains run WITHOUT re-pulling the static Bluetooth
history, so the self-updater stays fast.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.services.congestion_features import FEATURE_ORDER, TARGET_COLUMN

TRAINING_DIR = Path(__file__).resolve().parents[2] / "data" / "training"
OUT_PATH = TRAINING_DIR / "congestion_history.csv"
PRIOR_PATH = Path(__file__).resolve().parents[2] / "data" / "models" / "seasonal_prior.json"


def _howk_key(hour: int, is_weekend: int) -> str:
    """Hour-of-week bucket key: hour (0-23) x weekday/weekend."""
    return f"{int(hour)}_{int(is_weekend)}"


def _add_seasonal_level(df: pd.DataFrame) -> None:
    """Fill `seasonal_level` with a leave-one-out per-segment hour-of-week mean."""
    grp = df.groupby(["_segment_id", "hour", "is_weekend"])[TARGET_COLUMN]
    gsum = grp.transform("sum")
    gcount = grp.transform("count")
    global_mean = float(df[TARGET_COLUMN].mean())
    loo = (gsum - df[TARGET_COLUMN]) / (gcount - 1).where(gcount > 1)
    df["seasonal_level"] = loo.fillna(global_mean).round(3)


def _write_seasonal_prior(df: pd.DataFrame) -> None:
    """Persist full-group seasonal means for serving (per segment, per road class)."""
    def _means(group_cols: list[str]) -> dict:
        means = df.groupby(group_cols + ["hour", "is_weekend"])[TARGET_COLUMN].mean().round(2)
        out: dict[str, dict[str, float]] = {}
        for idx, value in means.items():
            key, hour, weekend = idx[0], idx[-2], idx[-1]
            out.setdefault(str(key), {})[_howk_key(hour, weekend)] = float(value)
        return out

    artifact = {
        "by_segment": _means(["_segment_id"]),
        "by_road_class": _means(["road_class"]),
        "global": round(float(df[TARGET_COLUMN].mean()), 2),
    }
    PRIOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRIOR_PATH.write_text(json.dumps(artifact), encoding="utf-8")


def finalize() -> int:
    """Combine all `_*_rows.csv`, compute seasonal_level + prior, write the CSV.

    Returns the number of rows written, or 0 when no source files are present.
    """
    parts = []
    for path in sorted(TRAINING_DIR.glob("_*_rows.csv")):
        part = pd.read_csv(path)
        parts.append(part)
        print(f"  + {len(part):,} rows from {path.name}")
    if not parts:
        print("[ERROR] No _*_rows.csv source files found.")
        return 0

    df = pd.concat(parts, ignore_index=True)
    _add_seasonal_level(df)
    _write_seasonal_prior(df)
    df = df[FEATURE_ORDER + [TARGET_COLUMN]]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Finalized {len(df):,} rows ({df.shape}) -> {OUT_PATH.name}")
    return len(df)


if __name__ == "__main__":
    import sys
    sys.exit(0 if finalize() else 1)
