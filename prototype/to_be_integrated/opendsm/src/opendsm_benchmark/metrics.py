"""
metrics.py - Accuracy of the load predictions of the benchmark.

    scores(y, y_hat)               n, mean, RMSE, CV(RMSE) %, NMBE %, MAE, R²
    hourly_daily(y, y_hat)         scores of hourly values and of daily average power

Definitions (y measured, ŷ predicted, n values, ȳ mean of y):
    RMSE = sqrt(Σ(y−ŷ)²/n)    CV(RMSE) = 100·RMSE/ȳ    NMBE = 100·Σ(y−ŷ)/(n·ȳ)    MAE = Σ|y−ŷ|/n
    R² = 1 − Σ(y−ŷ)²/Σ(y−ȳ)²
No degrees-of-freedom correction: the number of effective parameters of OpenDSM's regularised
model is not defined in the same way as for least squares. energy_insight component 5 re-scores these
predictions together with its hourly model on identical hours, with ASHRAE Guideline 14 degrees of freedom.
Daily values are daily energy / 24 (average power, kW).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def scores(y, y_hat) -> dict:
    y, y_hat = np.asarray(y, float), np.asarray(y_hat, float)
    ok = np.isfinite(y) & np.isfinite(y_hat)
    y, y_hat = y[ok], y_hat[ok]
    if len(y) == 0:
        return {"n": 0, "mean_obs": np.nan, "rmse": np.nan, "cv_rmse_pct": np.nan, "nmbe_pct": np.nan,
                "mae": np.nan, "r2": np.nan}
    e = y - y_hat
    return {"n": int(len(y)), "mean_obs": float(y.mean()), "rmse": float(np.sqrt((e ** 2).mean())),
            "cv_rmse_pct": float(100 * np.sqrt((e ** 2).mean()) / y.mean()),
            "nmbe_pct": float(100 * e.sum() / (len(y) * y.mean())), "mae": float(np.abs(e).mean()),
            "r2": float(1 - (e ** 2).sum() / ((y - y.mean()) ** 2).sum())}


def hourly_daily(y: pd.Series, y_hat: pd.Series) -> dict[str, dict]:
    """Scores of hourly values and of daily average power (days with all 24 predictions)."""
    df = pd.DataFrame({"y": y, "y_hat": y_hat}).dropna()
    day = df.index.tz_localize(None).normalize() if df.index.tz is not None else df.index.normalize()
    g = df.groupby(day)
    full = g.size() == 24
    daily = g.sum()[full] / 24.0
    return {"hourly": scores(df["y"], df["y_hat"]), "daily": scores(daily["y"], daily["y_hat"])}
