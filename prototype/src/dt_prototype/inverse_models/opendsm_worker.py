"""File-protocol worker for pinned OpenDSM 1.2.7 / pandas 2, never imported by the main runtime.

Uses public model APIs with a recorded, version-guarded hourly metrics fix.
Fitting coefficients and the supplied benchmark remain unchanged. Billing
holdouts are entire bills outside a contiguous training block.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import importlib.metadata
import json
import traceback
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from opendsm import eemeter as em

# This file runs directly in the isolated environment, without installing the
# main package (whose pandas version is intentionally different).
from opendsm_compat import hourly_metrics_compatibility


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def read_frame(path, clock, columns):
    data = pd.read_csv(path, keep_default_na=False)
    for column in columns:
        data[column] = pd.to_datetime(data[column], utc=True).dt.tz_convert(clock)
    if "energy_kWh" in data:
        data["energy_kWh"] = pd.to_numeric(data.energy_kWh.replace("", np.nan))
    for column in ["temperature_C", "ghi_Wm2"]:
        if column in data:
            data[column] = pd.to_numeric(data[column].replace("", np.nan), errors="raise")
    return data


def diagnostics(model):
    return {name: [{"code": w.qualified_name, "description": w.description} for w in getattr(model, name, [])]
            for name in ["warnings", "disqualification"]}


def hourly(obs, weather, task, saved):
    options = task["options"]
    if saved:
        model_zone = saved["model_timezone"]
    else:
        zone = obs.interval_start.dt.tz
        year = obs.interval_start.iloc[0].year
        offset = min(datetime(year, m, 1, tzinfo=zone).utcoffset() for m in range(1, 13))
        hours = offset.total_seconds()/3600
        if hours != int(hours):
            raise ValueError("hourly backend currently requires a whole-hour standard offset")
        model_zone = "UTC" if hours == 0 else f"Etc/GMT{int(-hours):+d}"
    obs = obs.copy()
    for name in ["interval_start", "interval_end"]:
        obs[name] = obs[name].dt.tz_convert(model_zone)
    if not (obs.duration_h == 1).all():
        raise ValueError("OpenDSM hourly needs genuine one-hour energy observations")
    wx = weather.set_index("time").tz_convert(model_zone)
    first, end = obs.interval_start.min().floor("D"), obs.interval_end.max().ceil("D")
    idx = pd.date_range(first, end, inclusive="left", freq="h", tz=model_zone)
    wx = wx.reindex(idx)
    required = ["temperature_C"] + (["ghi_Wm2"] if options.get("variant", "nonsolar") == "solar" else [])
    # Partial standard-time boundary days are not fabricated from civil input.
    complete_weather = wx[required].notna().all(axis=1)
    frame = pd.DataFrame({"temperature": wx.temperature_C*9/5+32, "ghi": wx.ghi_Wm2}, index=idx)
    feature_columns = ["temperature", "ghi"] if options.get("variant", "nonsolar") == "solar" else ["temperature"]
    if saved:
        native = saved["native_json"]
        combos = {tuple(v) for v in saved["supported_combinations"]}
        detail = saved["diagnostics"]
        training_days = saved["training_days"]
        compatibility = saved.get("compatibility", {"patch_id": None})
    else:
        train = obs[obs.split.eq("train") & obs.quality.eq("valid") & obs.energy_kWh.notna()]
        frame["observed"] = train.set_index("interval_start").energy_kWh.reindex(idx)
        dates = idx.tz_localize(None).normalize()
        usable = (frame.observed.notna() & complete_weather).groupby(dates).transform("all")
        counts = pd.Series(1, index=idx).groupby(dates).transform("sum")
        usable &= counts.eq(24)
        train_idx = frame.index[usable]
        if not len(train_idx):
            raise ValueError("no complete 24-hour training days")
        baseline_frame = frame.loc[train_idx.min().floor("D"):train_idx.max().ceil("D")-pd.Timedelta(hours=1)].copy()
        baseline_frame.loc[~usable.reindex(baseline_frame.index), "observed"] = np.nan
        baseline_frame["interpolated_observed"] = baseline_frame.observed.isna().astype(int)
        baseline = em.HourlyBaselineData(baseline_frame[["observed", *feature_columns, "interpolated_observed"]], is_electricity_data=False)
        settings = em.HourlySolarSettings(seed=options.get("seed", 42)) if len(feature_columns) == 2 else em.HourlyNonSolarSettings(seed=options.get("seed", 42))
        with hourly_metrics_compatibility() as compatibility:
            model = em.HourlyModel(settings=settings).fit(baseline, ignore_disqualification=options.get("allow_disqualified", False))
        native, detail = model.to_json(), diagnostics(model)
        days = pd.DatetimeIndex(train_idx.tz_localize(None).normalize().unique())
        combos = set(zip(days.month, days.dayofweek))
        training_days = len(days)
    date = idx.tz_localize(None).normalize()
    weather_days = complete_weather.groupby(date).transform("all")
    eligible = np.array([(t.month, t.dayofweek) in combos for t in idx]) & weather_days.to_numpy()
    days = pd.DatetimeIndex(date[eligible].unique()).sort_values()
    parts = []
    report_diagnostics = []
    if len(days):
        runs = (pd.Series(days).diff() != pd.Timedelta(days=1)).cumsum().to_numpy()
        for run in np.unique(runs):
            selection = date.isin(days[runs == run])
            # OpenDSM 1.2.7 mutates temporal cluster state on prediction.
            model = em.HourlyModel.from_json(native)
            reporting = em.HourlyReportingData(frame.loc[selection, feature_columns], is_electricity_data=False)
            report_diagnostics.append(diagnostics(reporting))
            part = model.predict(reporting, ignore_disqualification=options.get("allow_disqualified", False))
            parts.append(part[["predicted", "predicted_unc"]])
    predicted = pd.concat(parts) if parts else pd.DataFrame(columns=["predicted", "predicted_unc"])
    result = pd.DataFrame(index=pd.DatetimeIndex(obs.interval_start))
    result["predicted_energy_kWh"] = predicted.predicted.reindex(result.index)
    result["native_uncertainty"] = predicted.predicted_unc.reindex(result.index)
    result["prediction_reason"] = np.where(result.predicted_energy_kWh.notna(), "ok", "unsupported_calendar_or_incomplete_standard_day")
    payload = dict(native_json=native, model_timezone=model_zone, supported_combinations=sorted(combos),
                   training_days=training_days, diagnostics=detail, reporting_diagnostics=report_diagnostics,
                   compatibility=compatibility)
    return result.reset_index(drop=True), payload


def billing(obs, weather, task, saved):
    options = task["options"]
    if any(t != t.normalize() for t in list(obs.interval_start) + list(obs.interval_end)):
        raise ValueError("billing boundaries must be local midnight")
    temperature = weather.set_index("time").temperature_C*9/5+32
    if saved:
        native, detail = saved["native_json"], saved["diagnostics"]
        training = saved["training"]
    else:
        train = obs[obs.split.eq("train") & obs.quality.eq("valid") & obs.energy_kWh.notna()].copy()
        if len(train) < 6:
            raise ValueError("billing requires at least six actual training bills")
        if any(a != b for a, b in zip(train.interval_start.iloc[1:], train.interval_end.iloc[:-1])):
            raise ValueError("billing training bills must form one contiguous block; interleaved held-out bills would be bridged by OpenDSM 1.2.7 preprocessing")
        meter = pd.Series(train.energy_kWh.to_numpy(), index=pd.DatetimeIndex(train.interval_start))
        terminal = train.interval_end.iloc[-1]
        temperatures = temperature[(temperature.index >= train.interval_start.iloc[0]) & (temperature.index < terminal)]
        # The 1.2.7 from_series convenience path can trim the final bill when
        # hourly weather ends before its exclusive terminal marker. The public
        # dataframe constructor uses our exact complete-hour coverage instead.
        baseline = em.BillingBaselineData(pd.DataFrame({"observed":meter.reindex(temperatures.index),
                                                        "temperature":temperatures}), is_electricity_data=False)
        used = baseline.df.observed.sum()
        expected = train.energy_kWh.sum()
        if abs(used-expected) > 1e-6+1e-9*abs(expected):
            raise ValueError(f"billing preprocessing changed training energy: {used} vs {expected}; inspect bill lengths/coverage")
        model = em.BillingModel().fit(baseline, ignore_disqualification=options.get("allow_disqualified", False))
        native, detail = model.to_json(), diagnostics(model)
        training = {"bills": len(train), "input_energy_kWh": float(expected), "processed_energy_kWh": float(used),
                    "first": str(train.interval_start.iloc[0]), "end_exclusive": str(terminal)}
    # Prediction uses weather only, so held-out bill totals cannot enter fitting
    # or affect prediction. Summation below preserves the caller's actual bills.
    model = em.BillingModel.from_json(native)
    reporting = em.BillingReportingData.from_series(None, temperature, is_electricity_data=False, tzinfo=temperature.index.tz)
    daily = model.predict(reporting, ignore_disqualification=options.get("allow_disqualified", False))
    records = []
    for row in obs.itertuples():
        dates = pd.date_range(row.interval_start, row.interval_end, inclusive="left", freq="D")
        predicted = daily.predicted.reindex(dates)
        complete = predicted.notna().all() and len(predicted) == len(dates)
        records.append(dict(predicted_energy_kWh=float(predicted.sum()) if complete else np.nan,
                            native_uncertainty=np.nan, prediction_reason="ok" if complete else "incomplete_daily_prediction"))
    return pd.DataFrame(records), dict(native_json=native, diagnostics=detail, training=training,
                                      reporting_diagnostics=[diagnostics(reporting)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    if importlib.metadata.version("opendsm") != "1.2.7" or int(pd.__version__.split(".")[0]) != 2:
        raise RuntimeError("worker requires OpenDSM 1.2.7 and pandas 2.x")
    results = []
    for task in request["tasks"]:
        try:
            obs = read_frame(task["observations"], task["clock"]["timezone"], ["interval_start", "interval_end"])
            weather = read_frame(task["weather"], task["clock"]["timezone"], ["time"])
            saved = json.loads(Path(task["saved_payload"]).read_text()) if task.get("saved_payload") else None
            np.random.seed(task["options"].get("seed", 42))
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                result, payload = (hourly if task["backend"] == "opendsm_hourly" else billing)(obs, weather, task, saved)
            result.to_csv(task["prediction_output"], index=False)
            payload["runtime_warnings"] = sorted({str(w.message) for w in captured})
            Path(task["payload_output"]).write_text(json.dumps(clean(payload), allow_nan=False), encoding="utf-8")
            results.append({"task_id": task["task_id"], "status": "complete"})
        except Exception as error:
            results.append({"task_id": task["task_id"], "status": "failed", "error": f"{type(error).__name__}: {error}", "traceback": traceback.format_exc()})
        print(f"{task['task_id']}: {results[-1]['status']}", flush=True)
    versions = {name: importlib.metadata.version(name) for name in ["opendsm", "pandas", "numpy", "scipy", "scikit-learn", "multimethod"]}
    Path(request["response"]).write_text(json.dumps({"tasks": results, "versions": versions}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
