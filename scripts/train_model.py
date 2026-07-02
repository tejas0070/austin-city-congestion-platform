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
from datetime import datetime
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
from backend.etl.training_eval import (  # noqa: E402
    assign_leakfree_seasonal,
    accuracy_regressed,
    R2_REGRESSION_TOL,
    MAE_REGRESSION_TOL,
)

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "training" / "congestion_history.csv"
MODEL_PATH = Path(__file__).resolve().parents[1] / "data" / "models" / "congestion_model.pkl"
META_PATH = Path(__file__).resolve().parents[1] / "data" / "models" / "model_meta.json"

RANDOM_STATE = 42
# Set ALLOW_ACCURACY_REGRESSION=1 to bypass the gate (e.g. an intentional
# feature change that legitimately shifts the metric baseline).
ALLOW_REGRESSION_ENV = "ALLOW_ACCURACY_REGRESSION"


def _prev_honest_metrics() -> tuple[float | None, float | None]:
    """The deployed model's honest held-out (R^2, MAE), or (None, None)."""
    if not META_PATH.exists():
        return None, None
    try:
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None, None
    return meta.get("point_holdout_r2"), meta.get("point_holdout_mae")


def main() -> int:
    if not DATA_PATH.exists():
        print(f"[ERROR] Training data not found at {DATA_PATH}")
        print("  Run: python scripts/generate_training_data.py")
        return 1

    print(f"Loading training data from {DATA_PATH} ...")
    df = pd.read_csv(DATA_PATH)
    print(f"  {len(df):,} rows, {len(df.columns)} columns")

    feature_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES

    # Leak-free evaluation: split first, then derive `seasonal_level` per fold so
    # held-out rows never borrow their own group's test targets. This mirrors how
    # the live predictor serves the feature, making the reported R^2 a true
    # generalization estimate that is stable across retrains (it is NOT inflated
    # by per-group leakage density, which changes every self-update). Requires
    # `_segment_id` (kept by training_finalize); the synthetic fallback CSV omits
    # it, so we degrade to the old non-fold-aware split there.
    if "_segment_id" in df.columns:
        train_idx, test_idx = train_test_split(
            df.index, test_size=0.2, random_state=RANDOM_STATE
        )
        df = df.copy()
        df["seasonal_level"] = assign_leakfree_seasonal(
            df, train_idx, target_col=TARGET_COLUMN
        )
        x = df[feature_cols]
        y = df[TARGET_COLUMN]
        x_train, x_test = x.loc[train_idx], x.loc[test_idx]
        y_train, y_test = y.loc[train_idx], y.loc[test_idx]
        leakfree = True
    else:
        print("[warn] no _segment_id column — using non-fold-aware seasonal_level "
              "(leak-free evaluation disabled).")
        x = df[feature_cols]
        y = df[TARGET_COLUMN]
        x_train, x_test, y_train, y_test = train_test_split(
            x, y, test_size=0.2, random_state=RANDOM_STATE
        )
        leakfree = False

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
    print(f"  R^2: {r2:.4f}  ({'leak-free' if leakfree else 'non-fold-aware'})")

    # Regression gate: refuse to ship a model that is materially worse than the
    # one currently deployed. Comparison is honest-to-honest (both leak-free), so
    # it never blocks on the legacy inflated baseline. Bail BEFORE writing any
    # artifacts so the running API keeps serving the last good model. The
    # self-updater (auto_update.py) propagates this non-zero exit.
    prev_r2, prev_mae = _prev_honest_metrics()
    if leakfree and accuracy_regressed(r2, mae, prev_r2, prev_mae):
        allow = os.environ.get(ALLOW_REGRESSION_ENV) == "1"
        msg = (f"[BLOCKED] New model regresses point accuracy: "
               f"R^2 {r2:.4f} vs deployed {prev_r2:.4f} "
               f"(tol {R2_REGRESSION_TOL}), MAE {mae:.2f} vs {prev_mae} "
               f"(tol {MAE_REGRESSION_TOL}).")
        if not allow:
            print(msg)
            print("  Keeping the deployed model. Set "
                  f"{ALLOW_REGRESSION_ENV}=1 to override intentionally.")
            return 2
        print(msg + f"\n  {ALLOW_REGRESSION_ENV}=1 set — shipping anyway.")

    # --- Quantile models for an 80% prediction interval -------------------
    QUANTILES_PATH = Path(__file__).resolve().parents[1] / "data" / "models" / "congestion_quantiles.pkl"
    CARD_PATH = Path(__file__).resolve().parents[1] / "docs" / "model_card.md"

    def _make_quantile_model(q: float) -> Pipeline:
        return Pipeline(steps=[
            ("prep", ColumnTransformer(
                transformers=[("road_class", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES)],
                remainder="passthrough",
            )),
            ("gb", HistGradientBoostingRegressor(
                loss="quantile", quantile=q,
                max_iter=400, learning_rate=0.06, max_depth=6,
                l2_regularization=1.0, random_state=RANDOM_STATE,
            )),
        ])

    import numpy as np

    # Wide 80% interval (q10/q90): used ONLY to report the accuracy badge — how
    # often the model's prediction range actually contains the real value.
    print("Training 80% interval models (q10, q90) for the accuracy badge ...")
    q10_model = _make_quantile_model(0.10).fit(x_train, y_train)
    q90_model = _make_quantile_model(0.90).fit(x_train, y_train)
    lo80 = np.minimum(q10_model.predict(x_test), q90_model.predict(x_test))
    hi80 = np.maximum(q10_model.predict(x_test), q90_model.predict(x_test))
    coverage = float(((y_test >= lo80) & (y_test <= hi80)).mean())
    print(f"  80% interval coverage (accuracy badge): {coverage:.3f}")

    # Tight central 50% interval (q25/q75): this is what is SERVED for the
    # per-road confidence signal. A good model's central band is narrow, so this
    # reads as high confidence where the model predicts well, and low where it
    # genuinely cannot — without overstating an 80% band.
    #
    # The raw quantile band is systematically too narrow (covers ~44% not 50%), so
    # we split-conformal calibrate it: a single additive adjustment `conformal_q`
    # so the widened band hits nominal 50% coverage. CRITICAL: calibrate on
    # SERVING-STYLE features. Training rows carry a leave-one-out `seasonal_level`
    # while production (and the test fold) use the prior-lookup value — a different
    # distribution — so a q fit on training rows does NOT transfer (it comes out
    # ~0 and calibrates nothing). We therefore calibrate on a slice of the test
    # fold (prior-lookup features, exactly like serving) and report coverage on the
    # disjoint remainder.
    from backend.etl.confidence import compute_conformal_q  # noqa: E402
    print("Training 50% interval models (q25, q75) + conformal calibration ...")
    q25_model = _make_quantile_model(0.25).fit(x_train, y_train)
    q75_model = _make_quantile_model(0.75).fit(x_train, y_train)

    if leakfree and len(x_test) > 200:
        cal_idx, eval_idx = train_test_split(
            x_test.index, test_size=0.5, random_state=RANDOM_STATE
        )
    else:
        cal_idx = eval_idx = x_test.index  # fallback: single fold (mildly optimistic)

    lo_cal = np.minimum(q25_model.predict(x_test.loc[cal_idx]), q75_model.predict(x_test.loc[cal_idx]))
    hi_cal = np.maximum(q25_model.predict(x_test.loc[cal_idx]), q75_model.predict(x_test.loc[cal_idx]))
    conformal_q = compute_conformal_q(lo_cal, hi_cal, y_test.loc[cal_idx].to_numpy(), coverage=0.5)

    # Report on the disjoint evaluation slice.
    x_eval, yte = x_test.loc[eval_idx], y_test.loc[eval_idx].to_numpy()
    raw_lo = np.clip(np.minimum(q25_model.predict(x_eval), q75_model.predict(x_eval)), 0, 100)
    raw_hi = np.clip(np.maximum(q25_model.predict(x_eval), q75_model.predict(x_eval)), 0, 100)
    lo = np.clip(raw_lo - conformal_q, 0, 100)
    hi = np.clip(raw_hi + conformal_q, 0, 100)
    widths = hi - lo
    raw_cov = float(((yte >= raw_lo) & (yte <= raw_hi)).mean())
    coverage50 = float(((yte >= lo) & (yte <= hi)).mean())
    w_low = float(np.percentile(widths, 5))
    w_high = float(np.percentile(widths, 95))
    print(f"  conformal_q: {conformal_q:+.2f}  (50% coverage  raw {raw_cov:.3f} -> calibrated {coverage50:.3f})")
    print(f"  Calibrated width percentiles (p5/p50/p95): {w_low:.1f} / {np.percentile(widths,50):.1f} / {w_high:.1f}")

    # Confidence under the deployed ABSOLUTE anchors (what the UI actually shows).
    from backend.etl.confidence import absolute_width_anchors, width_to_confidence
    a_low, a_high = absolute_width_anchors()
    conf = np.array([width_to_confidence(float(w), a_low, a_high) for w in widths])
    mean_conf = float(conf.mean())
    pct_high = float((conf >= 80).mean() * 100)
    print(f"  Confidence (absolute anchors {a_low}/{a_high}): mean {mean_conf:.1f}%, "
          f"{pct_high:.0f}% of segments >= 80%")

    # --- Expected-value interval (lever 3) --------------------------------
    # The served confidence signal is the interval for the TYPICAL congestion the
    # app displays (per corridor x hour-of-week), not for a single 15-min reading.
    # We calibrate a symmetric half-width `ev_q` on held-out (segment,hour,weekend)
    # bucket means so `pred ± ev_q` covers the true typical value at the nominal
    # rate, and record the honestly-measured held-out coverage. This is far tighter
    # than the per-reading band because the typical value is genuinely known that
    # well (bucket MAE ~2.7 vs per-reading ~8.8) — verified, not asserted.
    from backend.etl.model_eval import calibrate_expected_value_interval  # noqa: E402
    from backend.etl.confidence import (  # noqa: E402
        HIGH_THRESHOLD, expected_value_anchors, modulated_half_width,
        width_to_confidence as _w2c,
    )
    ev80 = ev50 = {"q": 0.0, "coverage": 0.0, "buckets": 0}
    # Reference per-reading band width the serving path normalises against, so the
    # calibrated average half-width can be redistributed across corridors by each
    # one's relative uncertainty without shifting the mean (E[width/ref] ~= 1).
    # `widths` are the eval-fold per-reading band widths (serving-style features).
    ev_ref_width = float(np.mean(widths)) if len(widths) else 0.0
    ev_conf_mean = 0.0
    ev_conf_pct_high = 0.0
    if leakfree:
        ev_keys = df.loc[test_idx, ["_segment_id", "hour", "is_weekend"]]
        yte_all = y_test.to_numpy()
        ev80 = calibrate_expected_value_interval(ev_keys, yte_all, preds, coverage=0.8)
        ev50 = calibrate_expected_value_interval(ev_keys, yte_all, preds, coverage=0.5)
        ev_full, ev_zero = expected_value_anchors()
        ev_base_conf = _w2c(2 * ev80["q"], ev_full, ev_zero)
        # SERVED confidence (pre density-cap) over the eval fold: exactly what the
        # UI shows — the calibrated ev_q modulated by each row's learned spread.
        # This replaces the old per-reading `confidence_mean`, which described a
        # signal the app no longer serves and read a misleadingly high ~86%.
        served_conf = np.array([
            _w2c(2 * modulated_half_width(ev80["q"], float(w), ev_ref_width), ev_full, ev_zero)
            for w in widths
        ])
        ev_conf_mean = float(served_conf.mean()) if served_conf.size else 0.0
        ev_conf_pct_high = float((served_conf >= HIGH_THRESHOLD).mean() * 100) if served_conf.size else 0.0
        print(f"  expected-value interval (typical congestion per corridor x hour):")
        print(f"    80%: ev_q +/-{ev80['q']:.2f}  held-out coverage {ev80['coverage']:.3f}  "
              f"({ev80['buckets']} buckets) -> base confidence {ev_base_conf:.1f}")
        print(f"    50%: ev_q +/-{ev50['q']:.2f}  held-out coverage {ev50['coverage']:.3f}")
        print(f"    ref width {ev_ref_width:.2f}; served confidence (pre-cap): "
              f"mean {ev_conf_mean:.1f}%, {ev_conf_pct_high:.0f}% >= High")

    # Serve the 50% band for per-road confidence. Keys stay low/high so the
    # predictor is agnostic to which quantiles back the band; `conformal_q` is the
    # additive calibration the serving path applies before width->confidence.
    # `ev_q_80`/`ev_q_50` are the expected-value half-widths the serving path now
    # prefers (falling back to the per-reading band on older artifacts).
    joblib.dump({
        "low": q25_model, "high": q75_model, "conformal_q": conformal_q,
        "ev_q_80": float(ev80["q"]), "ev_q_50": float(ev50["q"]),
        # Population-average per-reading band width; the serving path redistributes
        # the calibrated ev_q across corridors relative to this (modulated_half_width).
        "ev_ref_width": float(ev_ref_width),
    }, QUANTILES_PATH)
    print(f"Saved confidence (50% interval) models to {QUANTILES_PATH}")

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
        # Honest, leak-free held-out metrics — the regression gate compares
        # against these on the next retrain. `leakfree_eval` records whether the
        # fold-aware path ran (false only for the synthetic-data fallback).
        "point_holdout_r2": round(float(r2), 4),
        "point_holdout_mae": round(float(mae), 3),
        "leakfree_eval": bool(leakfree),
        "training_rows": int(len(df)),
        # Accuracy badge: the wide 80% interval's empirical coverage.
        "interval": {"lower_quantile": 0.10, "upper_quantile": 0.90, "nominal_coverage": 0.80},
        "empirical_coverage": round(coverage, 4),
        # Confidence signal: the tight central 50% interval mapped via fixed anchors.
        "confidence_interval": {"lower_quantile": 0.25, "upper_quantile": 0.75},
        # Split-conformal calibration of that 50% band (lever 1): the additive
        # adjustment + the before/after empirical coverage on the held-out fold.
        "conformal_q": round(float(conformal_q), 3),
        "confidence_interval_coverage_raw": round(raw_cov, 4),
        "confidence_interval_coverage": round(coverage50, 4),
        # Expected-value interval (lever 3): the SERVED confidence signal — the
        # interval for the typical congestion the app displays. `coverage` is the
        # honestly-measured held-out coverage of the true bucket means.
        "expected_value_interval": {
            "ev_q_80": round(float(ev80["q"]), 3),
            "ev_q_50": round(float(ev50["q"]), 3),
            "coverage_80": round(float(ev80["coverage"]), 4),
            "coverage_50": round(float(ev50["coverage"]), 4),
            "buckets": int(ev80["buckets"]),
            "ev_ref_width": round(float(ev_ref_width), 3),
            "note": "pred +/- ev_q (modulated per-corridor) covers the typical value",
        },
        "width_anchors": {"p5": round(w_low, 3), "p95": round(w_high, 3)},
        # Anchors used by the legacy per-reading fallback path only.
        "confidence_anchors": {"full": a_low, "zero": a_high},
        # SERVED confidence over the held-out fold (expected-value path, pre
        # density-cap) — the figure that matches what users see on the map. The
        # legacy per-reading mean (~86%) described a signal the app no longer serves.
        "confidence_mean": round(ev_conf_mean, 1),
        "confidence_pct_high": round(ev_conf_pct_high, 1),
        "confidence_mean_per_reading_legacy": round(mean_conf, 1),
        "data_source": "City of Austin Bluetooth travel sensors (real)",
    }, indent=2), encoding="utf-8")

    CARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    CARD_PATH.write_text(
        f"""# Congestion Model Card

- **Model:** HistGradientBoostingRegressor (point) + q10/q90 quantile models (80% interval)
- **Training rows:** {len(df):,}
- **Data source:** City of Austin Bluetooth travel sensors (real speed history)
- **Point accuracy:** MAE {mae:.2f} congestion-pts, R squared {r2:.4f} ({'leak-free held-out' if leakfree else 'non-fold-aware'})
- **Interval calibration:** empirical coverage {coverage:.3f} (nominal 0.80)
- **Confidence:** interval width mapped to 0-100 via p5/p95 width anchors ({w_low:.1f} / {w_high:.1f})
- **Generated:** {datetime.now().isoformat(timespec='minutes')}
""",
        encoding="utf-8",
    )
    print(f"Saved model card to {CARD_PATH}")

    print(f"\nSaved model to {MODEL_PATH}")
    print(f"Saved metadata to {META_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
