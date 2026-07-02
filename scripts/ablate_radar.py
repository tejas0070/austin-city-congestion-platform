#!/usr/bin/env python3
"""Ablation study: does the dense-but-narrow Radar source help or hurt?

The combined training set is ~381k rows, but 300k of them (79%) come from just 13
radar detector intersections, while ~2,590 corridors are covered by a handful of
sparse TomTom readings each. This asks the honest question: does that volume make
the model a BETTER, more generalizable forecaster of the things the product is
meant to explain — weather impact, event impact, and typical flow by corridor x
hour — or does it just pull the learned relationships toward 13 highway spots?

For each data variant it runs the EXACT leak-free protocol the trainer uses
(split first, rebuild `seasonal_level` per fold via `assign_leakfree_seasonal`,
train the same HistGradientBoostingRegressor) and reports:

  * aggregate R^2 / tier-accuracy per (corridor x hour-of-week) bucket  <- decision
  * per-reading MAE / R^2 / tier-accuracy                               (transparency)
  * expected-value interval coverage (calibration sanity)
  * weather counterfactual: predicted congestion delta Clear -> Heavy Rain
  * event counterfactual: predicted congestion delta no-event -> 20k concert nearby
  * permutation importance of the weather + event features (does the model USE them?)
  * dense-corridor count (segments that can read "High" confidence)

Trains only in memory; never writes to data/models/. Writes docs/radar_ablation.md.

Run from the project root:
    python scripts/ablate_radar.py
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
from sklearn.metrics import mean_absolute_error  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder  # noqa: E402

from backend.services.congestion_features import (  # noqa: E402
    CATEGORICAL_FEATURES, FEATURE_ORDER, NUMERIC_FEATURES, TARGET_COLUMN,
    WEATHER_PROFILES,
)
from backend.etl.training_eval import assign_leakfree_seasonal  # noqa: E402
from backend.etl.model_eval import (  # noqa: E402
    aggregate_metrics, baseline_mae_reduction, calibrate_expected_value_interval,
    pointwise_metrics,
)
from backend.etl.confidence import SUPPORT_FULL  # noqa: E402

TRAINING_DIR = Path(__file__).resolve().parents[1] / "data" / "training"
OUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "radar_ablation.md"
RANDOM_STATE = 42

# Downsample radar to Bluetooth's per-segment density so 13 intersections stop
# dominating the row count (Bluetooth is ~76k rows / 12 segments ~= 6.3k/segment).
RADAR_CAP_PER_SEG = 6300

# Event counterfactual: a distance/time-weighted attendance signal of a large
# concert essentially on top of the corridor at showtime.
CONCERT_SIGNAL = 20000.0


def _load(name: str) -> pd.DataFrame:
    return pd.read_csv(TRAINING_DIR / f"_{name}_rows.csv")


def _cap_radar(radar: pd.DataFrame, cap_per_seg: int) -> pd.DataFrame:
    """Keep at most `cap_per_seg` rows per radar segment (deterministic sample)."""
    return (
        radar.groupby("_segment_id", group_keys=False)
        .apply(lambda g: g.sample(min(len(g), cap_per_seg), random_state=RANDOM_STATE))
        .reset_index(drop=True)
    )


def _make_model() -> Pipeline:
    """The deployed training pipeline, replicated exactly for a fair comparison."""
    return Pipeline(steps=[
        ("prep", ColumnTransformer(
            transformers=[("road_class", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES)],
            remainder="passthrough",
        )),
        ("gb", HistGradientBoostingRegressor(
            max_iter=400, learning_rate=0.06, max_depth=6,
            l2_regularization=1.0, random_state=RANDOM_STATE,
        )),
    ])


def _weather_row(x: pd.DataFrame, condition: str) -> pd.DataFrame:
    """Copy of `x` with the weather columns forced to `condition`'s profile."""
    code, temp, precip, _ = WEATHER_PROFILES[condition]
    out = x.copy()
    out["weather_code"] = code
    out["temperature_f"] = temp
    out["precipitation_in"] = precip
    return out


def _dense_corridor_count(df: pd.DataFrame) -> int:
    """Segments with >= SUPPORT_FULL readings in some hour-of-week group — i.e.
    those whose real history can justify a 'High' confidence reading."""
    g = df.groupby(["_segment_id", "hour", "is_weekend"]).size()
    dense_segs = g[g >= SUPPORT_FULL].index.get_level_values("_segment_id").unique()
    return int(len(dense_segs))


def _permutation_delta(model, x_test, y_test, cols: list[str]) -> float:
    """MAE increase when `cols` are jointly shuffled — how much the model relies
    on them. Bigger => the feature group matters more to the prediction."""
    rng = np.random.default_rng(RANDOM_STATE)
    base_mae = mean_absolute_error(y_test, model.predict(x_test))
    shuffled = x_test.copy()
    perm = rng.permutation(len(shuffled))
    for c in cols:
        shuffled[c] = shuffled[c].to_numpy()[perm]
    return float(mean_absolute_error(y_test, model.predict(shuffled)) - base_mae)


def evaluate(name: str, df: pd.DataFrame) -> dict:
    df = df[FEATURE_ORDER[:-1] + CATEGORICAL_FEATURES + [TARGET_COLUMN, "_segment_id"]].copy()
    # Drop the disk `seasonal_level`; rebuild it leak-free per fold below.
    train_idx, test_idx = train_test_split(df.index, test_size=0.2, random_state=RANDOM_STATE)
    df["seasonal_level"] = assign_leakfree_seasonal(df, train_idx, target_col=TARGET_COLUMN)

    x, y = df[FEATURE_ORDER], df[TARGET_COLUMN]
    x_train, x_test = x.loc[train_idx], x.loc[test_idx]
    y_train, y_test = y.loc[train_idx], y.loc[test_idx]

    model = _make_model().fit(x_train, y_train)
    preds = model.predict(x_test)

    point = pointwise_metrics(y_test, preds)
    keys = df.loc[test_idx, ["_segment_id", "hour", "is_weekend"]]
    agg = aggregate_metrics(keys, y_test, preds)
    ev80 = calibrate_expected_value_interval(keys, y_test.to_numpy(), preds, coverage=0.8)

    # Counterfactuals on the held-out rows: hold location+time fixed, move one lever.
    def _clip(p):
        return np.clip(p, 0, 100)
    clear = _clip(model.predict(_weather_row(x_test, "Clear")))
    rain = _clip(model.predict(_weather_row(x_test, "Heavy Rain")))
    storm = _clip(model.predict(_weather_row(x_test, "Storm")))
    no_event = x_test.copy(); no_event["nearby_event_attendance"] = 0.0
    concert = x_test.copy(); concert["nearby_event_attendance"] = CONCERT_SIGNAL
    ev_base = _clip(model.predict(no_event))
    ev_big = _clip(model.predict(concert))

    return {
        "name": name,
        "rows": int(len(df)),
        "segments": int(df["_segment_id"].nunique()),
        "dense_corridors": _dense_corridor_count(df),
        "point_mae": point["mae"],
        "point_r2": point["r2"],
        "point_tier_acc": point["tier_accuracy"],
        "agg_r2": agg.get("r2"),
        "agg_mae": agg.get("mae"),
        "agg_tier_acc": agg.get("tier_accuracy"),
        "agg_buckets": agg.get("buckets"),
        "ev_q80": ev80["q"],
        "ev_cov80": ev80["coverage"],
        "baseline_reduction": baseline_mae_reduction(y_test, preds, float(y_train.mean())),
        "weather_rain_delta": round(float(np.mean(rain - clear)), 2),
        "weather_storm_delta": round(float(np.mean(storm - clear)), 2),
        "event_delta": round(float(np.mean(ev_big - ev_base)), 2),
        "imp_weather": round(_permutation_delta(model, x_test, y_test,
                             ["weather_code", "temperature_f", "precipitation_in"]), 3),
        "imp_event": round(_permutation_delta(model, x_test, y_test,
                             ["nearby_event_attendance"]), 3),
    }


def _fmt(v, nd=3):
    return "n/a" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def write_report(results: list[dict]) -> None:
    lines = ["# Radar data ablation", ""]
    lines.append("Leak-free held-out comparison of data-source variants, plus the "
                 "learned weather/event responses the product is meant to explain. "
                 "All variants use the identical split + per-fold `seasonal_level` "
                 "rebuild + model as the deployed trainer.")
    lines.append("")
    rows_tbl = [
        ("Rows", "rows", 0), ("Segments", "segments", 0),
        ("Dense corridors (>= %d)" % SUPPORT_FULL, "dense_corridors", 0),
        ("**Aggregate R2**", "agg_r2", 3), ("Aggregate MAE", "agg_mae", 2),
        ("Aggregate tier-acc", "agg_tier_acc", 3), ("Aggregate buckets", "agg_buckets", 0),
        ("Per-reading MAE", "point_mae", 2), ("Per-reading R2", "point_r2", 3),
        ("Per-reading tier-acc", "point_tier_acc", 3),
        ("EV interval q (80%)", "ev_q80", 2), ("EV coverage (80%)", "ev_cov80", 3),
        ("MAE reduction vs naive", "baseline_reduction", 3),
        ("**Rain delta (Clear->Heavy)**", "weather_rain_delta", 2),
        ("Storm delta (Clear->Storm)", "weather_storm_delta", 2),
        ("**Event delta (0->20k)**", "event_delta", 2),
        ("Weather importance (MAE+)", "imp_weather", 3),
        ("Event importance (MAE+)", "imp_event", 3),
    ]
    header = "| Metric | " + " | ".join(r["name"] for r in results) + " |"
    sep = "| --- | " + " | ".join("---" for _ in results) + " |"
    lines += [header, sep]
    for label, key, nd in rows_tbl:
        cells = " | ".join(_fmt(r[key], nd) for r in results)
        lines.append(f"| {label} | {cells} |")
    lines.append("")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {OUT_PATH}")


def main() -> int:
    bt, radar, tt = _load("bluetooth"), _load("radar"), _load("tomtom")
    print(f"Loaded bluetooth={len(bt):,} radar={len(radar):,} tomtom={len(tt):,}")
    radar_capped = _cap_radar(radar, RADAR_CAP_PER_SEG)
    print(f"Radar capped to <= {RADAR_CAP_PER_SEG}/segment: {len(radar_capped):,} rows")

    variants = {
        "Baseline (BT+Radar+TT)": pd.concat([bt, radar, tt], ignore_index=True),
        "No radar (BT+TT)": pd.concat([bt, tt], ignore_index=True),
        "Radar capped (BT+Radar*+TT)": pd.concat([bt, radar_capped, tt], ignore_index=True),
    }
    results = []
    for name, df in variants.items():
        print(f"\n=== {name}: {len(df):,} rows ===")
        results.append(evaluate(name, df))
        r = results[-1]
        print(f"  agg R2={_fmt(r['agg_r2'])} tier={_fmt(r['agg_tier_acc'])}  "
              f"rain +{r['weather_rain_delta']}  event +{r['event_delta']}  "
              f"dense={r['dense_corridors']}")
    write_report(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
