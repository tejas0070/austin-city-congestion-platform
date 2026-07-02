"""Leak-free `seasonal_level` assignment + a point-accuracy regression gate.

`seasonal_level` is a per-(segment, hour, weekend) target encoding — the model's
single strongest feature. Computing it over the WHOLE dataset before the
train/test split (the old `training_finalize._add_seasonal_level` path) leaks
held-out targets into the evaluation: a test row's feature becomes the mean of
its group, including sibling test rows. The inflation scales with per-group
density, so as the self-updater changes data composition the reported R^2 drifts
and appears to "regress" even when real skill is unchanged.

`assign_leakfree_seasonal` mirrors how the live predictor serves the feature
(`backend.services.ml_model._resolve_seasonal`): held-out rows get the
TRAIN-fold group mean (tiered segment -> road_class -> global) and training rows
get a leave-one-out mean within the train fold. The reported metrics then reflect
true generalization and are stable across retrains.

`accuracy_regressed` is the guard the trainer uses to refuse shipping a model
whose honest held-out accuracy is materially worse than the deployed one.
"""
from __future__ import annotations

import pandas as pd

# A new model may ship only if its honest held-out accuracy is within these
# tolerances of the currently deployed model. Drops larger than this are treated
# as a real regression and block the retrain (the API keeps the last good model).
R2_REGRESSION_TOL = 0.03   # R^2 may dip by at most this before it's a regression
MAE_REGRESSION_TOL = 0.5   # MAE (congestion-pts) may rise by at most this


def assign_leakfree_seasonal(
    df: pd.DataFrame,
    train_idx,
    *,
    target_col: str,
    seg_col: str = "_segment_id",
    road_class_col: str = "road_class",
    hour_col: str = "hour",
    weekend_col: str = "is_weekend",
) -> pd.Series:
    """Return a leak-free `seasonal_level` Series aligned to ``df.index``.

    Train rows: leave-one-out group mean within the train fold (so a row never
    sees its own target). Test rows: the train-fold group mean via a tiered
    lookup (segment -> road_class -> global), exactly as the predictor serves it.
    """
    train_idx = pd.Index(train_idx)
    test_idx = df.index.difference(train_idx)
    train = df.loc[train_idx]

    global_mean = float(train[target_col].mean())

    # --- train rows: leave-one-out within the train fold ---
    grp = train.groupby([seg_col, hour_col, weekend_col])[target_col]
    gsum = grp.transform("sum")
    gcount = grp.transform("count")
    loo = (gsum - train[target_col]) / (gcount - 1).where(gcount > 1)
    loo = loo.fillna(global_mean)

    out = pd.Series(index=df.index, dtype="float64")
    out.loc[train_idx] = loo  # index-aligned

    # --- test rows: tiered train-fold priors (segment -> road_class -> global) ---
    if len(test_idx):
        seg_prior = train.groupby([seg_col, hour_col, weekend_col])[target_col].mean()
        rc_prior = train.groupby([road_class_col, hour_col, weekend_col])[target_col].mean()
        test = df.loc[test_idx]

        seg_keys = list(zip(test[seg_col], test[hour_col], test[weekend_col]))
        rc_keys = list(zip(test[road_class_col], test[hour_col], test[weekend_col]))
        seg_vals = seg_prior.reindex(seg_keys).to_numpy()
        rc_vals = rc_prior.reindex(rc_keys).to_numpy()

        resolved = pd.Series(seg_vals, index=test_idx)
        rc_series = pd.Series(rc_vals, index=test_idx)
        resolved = resolved.fillna(rc_series).fillna(global_mean)
        out.loc[test_idx] = resolved

    return out.round(3)


def accuracy_regressed(
    new_r2: float,
    new_mae: float,
    prev_r2: float | None,
    prev_mae: float | None,
    r2_tol: float = R2_REGRESSION_TOL,
    mae_tol: float = MAE_REGRESSION_TOL,
) -> bool:
    """True if the new model is materially worse than the deployed one.

    Returns False when there is no prior baseline (first honest run establishes
    it) or when the change is within tolerance / an improvement.
    """
    if prev_r2 is None:
        return False
    if new_r2 < prev_r2 - r2_tol:
        return True
    if prev_mae is not None and new_mae > prev_mae + mae_tol:
        return True
    return False
