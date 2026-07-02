# tests/test_model_eval.py
"""Honest evaluation metrics: pointwise, aggregate, classification, baseline lift."""
import numpy as np
import pandas as pd

from backend.etl.model_eval import (
    tier_indices,
    pointwise_metrics,
    aggregate_metrics,
    baseline_mae_reduction,
    calibrate_expected_value_interval,
)


def test_tier_indices_thresholds():
    # green <15, yellow 15-30, red >=30
    assert list(tier_indices([0, 14.9, 15, 29.9, 30, 90])) == [0, 0, 1, 1, 2, 2]


def test_pointwise_perfect_prediction():
    y = [0, 20, 40, 5, 60]
    m = pointwise_metrics(y, y)
    assert m["mae"] == 0.0
    assert m["r2"] == 1.0
    assert m["tier_accuracy"] == 1.0
    assert m["within_10pts"] == 1.0


def test_pointwise_tier_accuracy_counts_color_matches():
    # both green, both red, but one green predicted as yellow -> 2/3 tier accuracy
    y_true = [5, 40, 10]
    y_pred = [8, 45, 20]  # 10(green) predicted 20(yellow) -> miss
    m = pointwise_metrics(y_true, y_pred)
    assert m["tier_accuracy"] == round(2 / 3, 4)


def test_aggregate_averages_out_noise():
    # one bucket, true readings noisy around 20, predictions noisy around 20 ->
    # the bucket means match closely even though individual readings don't
    keys = pd.DataFrame({"seg": ["a"] * 6, "hour": [8] * 6, "wk": [0] * 6})
    y_true = [10, 30, 15, 25, 18, 22]   # mean 20
    y_pred = [22, 18, 21, 19, 20, 20]   # mean 20
    agg = aggregate_metrics(keys, y_true, y_pred, min_samples=5)
    assert agg["buckets"] == 1
    assert agg["mae"] < 1.0  # bucket means nearly identical


def test_aggregate_drops_small_buckets():
    keys = pd.DataFrame({"seg": ["a", "a", "b"], "hour": [8, 8, 9], "wk": [0, 0, 0]})
    agg = aggregate_metrics(keys, [10, 20, 99], [10, 20, 0], min_samples=3)
    assert agg == {}  # no bucket has >= 3 samples


def test_baseline_mae_reduction():
    y = [0, 10, 20, 30]  # mean 15 -> baseline MAE = mean(|y-15|) = 10
    # perfect model -> 100% reduction
    assert baseline_mae_reduction(y, y, 15.0) == 1.0
    # model equal to baseline -> 0% reduction
    assert baseline_mae_reduction(y, [15, 15, 15, 15], 15.0) == 0.0


# --- expected-value interval calibration ------------------------------------

def test_calibrate_ev_interval_covers_true_bucket_means():
    # 400 buckets, each 6 noisy readings whose MEAN sits a small distance from the
    # prediction. The calibrated 80% half-width should cover ~80% of the true
    # means on the held-out bucket half (enough buckets for a stable estimate).
    rng = np.random.default_rng(0)
    keys_rows, y, p = [], [], []
    for b in range(400):
        pred = 20.0 + (b % 60)  # bucket-level prediction
        offset = rng.normal(0, 5)  # bucket-mean error vs prediction
        for _ in range(6):
            keys_rows.append(b)
            y.append(pred + offset + rng.normal(0, 3))  # reading = mean + noise
            p.append(pred)
    keys = pd.DataFrame({"bucket": keys_rows})
    out = calibrate_expected_value_interval(keys, y, p, coverage=0.8, min_samples=5)
    assert out["buckets"] == 400
    assert out["q"] > 0
    # honest: measured held-out coverage lands near the 0.8 nominal target
    assert 0.7 <= out["coverage"] <= 0.9


def test_calibrate_ev_interval_perfect_prediction_zero_width():
    keys = pd.DataFrame({"bucket": [0, 0, 0, 0, 0]})
    out = calibrate_expected_value_interval(keys, [10, 10, 10, 10, 10],
                                            [10, 10, 10, 10, 10], coverage=0.8, min_samples=3)
    assert out["q"] == 0.0
    assert out["coverage"] == 1.0


def test_calibrate_ev_interval_drops_small_buckets():
    keys = pd.DataFrame({"bucket": [0, 0, 1]})
    out = calibrate_expected_value_interval(keys, [10, 20, 99], [10, 20, 0],
                                            coverage=0.8, min_samples=3)
    assert out["buckets"] == 0
    assert out["q"] == 0.0
