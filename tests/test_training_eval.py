# tests/test_training_eval.py
"""Leak-free seasonal_level assignment + the point-accuracy regression gate."""
import pandas as pd
import pytest

from backend.etl.training_eval import (
    assign_leakfree_seasonal,
    accuracy_regressed,
    R2_REGRESSION_TOL,
)

TARGET = "congestion_pct"


def _frame(rows):
    return pd.DataFrame(rows)


def test_test_row_seasonal_is_train_group_mean_not_self():
    """A held-out row's seasonal_level = the TRAIN-fold group mean, independent of
    its own target (no leakage)."""
    df = _frame([
        # train rows for seg A, hour 8, weekday -> mean target = 20
        {"_segment_id": "A", "road_class": "primary", "hour": 8, "is_weekend": 0, TARGET: 10.0},
        {"_segment_id": "A", "road_class": "primary", "hour": 8, "is_weekend": 0, TARGET: 30.0},
        # the test row in the same group, with an extreme own-target
        {"_segment_id": "A", "road_class": "primary", "hour": 8, "is_weekend": 0, TARGET: 99.0},
    ])
    train_idx = df.index[:2]
    out = assign_leakfree_seasonal(df, train_idx, target_col=TARGET)
    # test row (index 2) gets the train mean (20), NOT influenced by its own 99
    assert out.loc[2] == pytest.approx(20.0)

    # flipping the test row's own target must not change its seasonal_level
    df2 = df.copy()
    df2.loc[2, TARGET] = 0.0
    out2 = assign_leakfree_seasonal(df2, train_idx, target_col=TARGET)
    assert out2.loc[2] == pytest.approx(20.0)


def test_train_row_seasonal_is_leave_one_out():
    """A training row's seasonal_level is the mean of the OTHER train rows in its
    group (leave-one-out), so the model never sees its own target."""
    df = _frame([
        {"_segment_id": "A", "road_class": "primary", "hour": 8, "is_weekend": 0, TARGET: 10.0},
        {"_segment_id": "A", "road_class": "primary", "hour": 8, "is_weekend": 0, TARGET: 30.0},
        {"_segment_id": "A", "road_class": "primary", "hour": 8, "is_weekend": 0, TARGET: 50.0},
    ])
    train_idx = df.index  # all train
    out = assign_leakfree_seasonal(df, train_idx, target_col=TARGET)
    # row 0 LOO = mean(30,50) = 40 ; row 1 = mean(10,50)=30 ; row 2 = mean(10,30)=20
    assert out.loc[0] == pytest.approx(40.0)
    assert out.loc[1] == pytest.approx(30.0)
    assert out.loc[2] == pytest.approx(20.0)


def test_unseen_segment_falls_back_to_road_class_then_global():
    """Tiered fallback mirrors the live predictor: segment -> road_class -> global."""
    df = _frame([
        # train: seg A primary hour 8 weekday mean 20
        {"_segment_id": "A", "road_class": "primary", "hour": 8, "is_weekend": 0, TARGET: 20.0},
        {"_segment_id": "A", "road_class": "primary", "hour": 8, "is_weekend": 0, TARGET: 20.0},
        # test: unseen segment B but same road_class+hour -> road_class mean (20)
        {"_segment_id": "B", "road_class": "primary", "hour": 8, "is_weekend": 0, TARGET: 5.0},
        # test: unseen road_class entirely -> global train mean (20)
        {"_segment_id": "C", "road_class": "motorway", "hour": 2, "is_weekend": 1, TARGET: 5.0},
    ])
    train_idx = df.index[:2]
    out = assign_leakfree_seasonal(df, train_idx, target_col=TARGET)
    assert out.loc[2] == pytest.approx(20.0)  # road_class fallback
    assert out.loc[3] == pytest.approx(20.0)  # global fallback


def test_output_aligned_to_full_index_no_nans():
    df = _frame([
        {"_segment_id": "A", "road_class": "primary", "hour": 8, "is_weekend": 0, TARGET: 10.0},
        {"_segment_id": "A", "road_class": "primary", "hour": 8, "is_weekend": 0, TARGET: 30.0},
        {"_segment_id": "B", "road_class": "trunk", "hour": 9, "is_weekend": 0, TARGET: 40.0},
    ])
    out = assign_leakfree_seasonal(df, df.index[:2], target_col=TARGET)
    assert list(out.index) == list(df.index)
    assert out.notna().all()


# --- regression gate --------------------------------------------------------

def test_gate_allows_when_no_prior_baseline():
    # first honest run: nothing to compare against -> ship
    assert accuracy_regressed(0.29, 9.0, prev_r2=None, prev_mae=None) is False


def test_gate_blocks_materially_worse_r2():
    assert accuracy_regressed(0.20, 9.0, prev_r2=0.29, prev_mae=9.0) is True


def test_gate_allows_within_tolerance():
    # a drop smaller than the tolerance is noise, not a regression
    assert accuracy_regressed(0.29 - R2_REGRESSION_TOL / 2, 9.0, prev_r2=0.29, prev_mae=9.0) is False


def test_gate_allows_improvement():
    assert accuracy_regressed(0.35, 8.0, prev_r2=0.29, prev_mae=9.0) is False


def test_gate_blocks_mae_spike_even_if_r2_ok():
    assert accuracy_regressed(0.30, 12.0, prev_r2=0.29, prev_mae=9.0) is True
