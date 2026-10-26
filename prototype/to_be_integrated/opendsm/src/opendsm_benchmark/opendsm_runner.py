"""
opendsm_runner.py - Fitting and prediction with OpenDSM's hourly model (EEmeter), used unchanged.

    fit(data, variant, training_days, settings)        one OpenDSM HourlyModel
    predict(fitted, data, days, settings)              hourly predictions for the given days
    in_sample(data, variant, settings)                 fit and predict on all model days
    cross_validate(data, variant, folds, settings)     blocked K-fold out-of-sample predictions

Variants: "solar" = temperature + GHI (OpenDSM's solar hourly model), "nonsolar" = temperature.

How three properties of OpenDSM 1.2.7 are handled here (the library itself is not modified):
  * predict() replaces the fitted model's table of month x weekday clusters with the
    combinations of the data it is given. To predict several separate runs of days, a fresh copy
    of the fitted model is restored from its JSON serialisation (public API) before every call;
    the copy reproduces the original predictions exactly.
  * Reporting data are made contiguous by OpenDSM, and a day whose month x weekday combination
    was absent from the training data cannot be predicted. Predictions are therefore made run by
    run (consecutive days) and only for days whose combination was trained; other days are
    reported as not predictable.
  * Warnings are logged on the "eemeter" logger; they are kept off the console and stored with
    the results (disqualification and warning names of every fit).
"""
from __future__ import annotations

import logging
import time
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from opendsm import eemeter as em

from .preprocess import PeriodData
from .settings import Settings

FEATURES = {"solar": ["temperature", "ghi"], "nonsolar": ["temperature"]}


@dataclass
class Fit:
    variant: str
    model_json: str
    training_days: pd.DatetimeIndex
    combos: set
    disqualification: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    baseline_metrics: dict = field(default_factory=dict)
    seconds: float = 0.0


@contextmanager
def quiet():
    """Silence OpenDSM's logged warnings and Python warnings while it runs."""
    logger = logging.getLogger("eemeter")
    level = logger.level
    logger.setLevel(logging.ERROR)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            yield
    finally:
        logger.setLevel(level)


def _dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return index.tz_localize(None).normalize()


def _combos(days: pd.DatetimeIndex) -> set:
    return set(zip(days.month, days.dayofweek))


def _metrics_dict(metrics) -> dict:
    if metrics is None:
        return {}
    raw = metrics.model_dump() if hasattr(metrics, "model_dump") else dict(vars(metrics))
    return {k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in raw.items()
            if isinstance(v, (int, float, np.floating, str)) or v is None}


def fit(data: PeriodData, variant: str, training_days: pd.DatetimeIndex, settings: Settings) -> Fit:
    """Fit one OpenDSM hourly model on the hours of `training_days` (other hours are passed as
    flagged missing values, so OpenDSM neither trains on them nor imputes them)."""
    cols = ["observed", *FEATURES[variant], "interpolated_observed"]
    df = data.frame[cols].copy()
    train = _dates(df.index).isin(training_days)
    df.loc[~train, "observed"] = np.nan
    df["interpolated_observed"] = (~train).astype(int)
    model_settings = (em.HourlySolarSettings(seed=settings.seed) if variant == "solar"
                      else em.HourlyNonSolarSettings(seed=settings.seed))
    t0 = time.time()
    with quiet():
        baseline = em.HourlyBaselineData(df, is_electricity_data=settings.is_electricity_data)
        model = em.HourlyModel(settings=model_settings).fit(
            baseline, ignore_disqualification=settings.ignore_disqualification)
    return Fit(variant=variant, model_json=model.to_json(), training_days=pd.DatetimeIndex(training_days),
               combos=_combos(pd.DatetimeIndex(training_days)),
               disqualification=sorted({w.qualified_name for w in model.disqualification}),
               warnings=sorted({w.qualified_name for w in model.warnings}),
               baseline_metrics=_metrics_dict(model.baseline_metrics), seconds=time.time() - t0)


def predict(fitted: Fit, data: PeriodData, days, settings: Settings) -> tuple[pd.DataFrame, list]:
    """Hourly `predicted` and `predicted_unc` for `days` (those with a trained month x weekday).
    Returns (frame, skipped days)."""
    days = pd.DatetimeIndex(sorted(set(pd.DatetimeIndex(days))))
    ok = np.array([(d.month, d.dayofweek) in fitted.combos for d in days], dtype=bool)
    skipped, days = list(days[~ok]), days[ok]
    if len(days) == 0:
        return pd.DataFrame(columns=["predicted", "predicted_unc"]), skipped
    runs = (pd.Series(days).diff() != pd.Timedelta(days=1)).cumsum().to_numpy()
    hour_dates = _dates(data.frame.index)
    parts = []
    with quiet():
        for r in np.unique(runs):
            seg = data.frame.loc[hour_dates.isin(days[runs == r]), FEATURES[fitted.variant]]
            model = em.HourlyModel.from_json(fitted.model_json)     # fresh copy: predict() mutates state
            report = em.HourlyReportingData(seg, is_electricity_data=settings.is_electricity_data)
            out = model.predict(report, ignore_disqualification=True)
            parts.append(out[["predicted", "predicted_unc"]])
    return pd.concat(parts).sort_index(), skipped


def in_sample(data: PeriodData, variant: str, settings: Settings) -> tuple[Fit, pd.DataFrame]:
    """Fit on all model days and predict them (goodness of fit)."""
    fitted = fit(data, variant, data.model_days, settings)
    pred, _ = predict(fitted, data, data.model_days, settings)
    return fitted, pred


def cross_validate(data: PeriodData, variant: str, folds: pd.Series, settings: Settings) -> tuple[pd.DataFrame, list[dict]]:
    """Out-of-sample prediction of every model day by the model fitted on the other folds.
    Returns hourly predictions (with the fold) and one record per fold."""
    parts, records = [], []
    for k in sorted(folds.unique()):
        test = folds.index[folds == k]
        train = folds.index[folds != k]
        fitted = fit(data, variant, train, settings)
        pred, skipped = predict(fitted, data, test, settings)
        parts.append(pred.assign(fold=int(k)))
        records.append({"variant": variant, "fold": int(k), "train_days": len(train), "test_days": len(test),
                        "not_predictable_days": len(skipped),
                        "not_predictable": ", ".join(f"{d:%Y-%m-%d}" for d in skipped),
                        "fit_seconds": round(fitted.seconds, 2)})
    return pd.concat(parts).sort_index(), records
