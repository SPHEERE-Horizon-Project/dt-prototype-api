"""
folds.py - Blocked cross-validation folds for out-of-sample load prediction.

The model days of a period are cut into blocks of `block_days` consecutive calendar days
(counted from the first model day); block b goes to fold b mod n_folds. Each fold is predicted
by a model fitted on the other folds, so every model day gets one out-of-sample prediction.

Whole blocks (not single days) are held out so that the test days are not surrounded by
training days of the same week, which would flatter the scores through autocorrelation; the
round-robin assignment keeps every month and weekday represented in each training set.
The fold of every day is exported (folds.csv) so later models can be compared on the same split.
"""
from __future__ import annotations

import pandas as pd


def assign_folds(model_days: pd.DatetimeIndex, n_folds: int, block_days: int) -> pd.Series:
    """Fold number (0 ... n_folds-1) of every model day."""
    days = pd.DatetimeIndex(model_days).sort_values()
    block = ((days - days[0]).days // block_days).to_numpy()
    return pd.Series(block % n_folds, index=pd.DatetimeIndex(days, name="date"), name="fold")
