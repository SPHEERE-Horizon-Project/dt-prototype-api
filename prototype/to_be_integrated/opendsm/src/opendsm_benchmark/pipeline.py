"""
pipeline.py - The benchmark, end to end.

    INPUT            energy_insight interim datasets or one plain CSV per period (inputs.py, [inputs] source)
    PRE-PROCESSING   preprocess.py: model time (local standard time), °F, weather, model days -> OpenDSM frames
    PROCESSING       per period and variant (solar: temperature + irradiance; nonsolar: temperature),
                     with OpenDSM 1.2.7 (opendsm_runner.py): in-sample fit on all model days and
                     blocked K-fold cross-validation (out-of-sample predictions)
    TEMPERATURE      response.py: daily temperature response of the solar model per temporal cluster
    OUTPUT           results/period_<k>/
                         predictions_period_<k>.csv        every hour: measured value, in-sample and
                                                           out-of-sample predictions, fold of the day
                         folds_period_<k>.csv              fold of every model day (read by energy_insight)
                         temperature_response_period_<k>.csv   (read by energy_insight, figure)
                         models/opendsm_<variant>_model_period_<k>.json   (parameter count, read by energy_insight)
                     results/summary/benchmark_metrics.csv  hourly and daily accuracy of every variant
                     results/summary/benchmark_fits.csv      OpenDSM's qualification of every fit (overridden rules)

Usage (in this folder; with source = "energy_insight" after that pipeline has written its interim datasets):
    .venv\\Scripts\\python run_benchmark.py                 all periods
    .venv\\Scripts\\python run_benchmark.py --periods 3     selected periods
    .venv\\Scripts\\python run_benchmark.py --config other.toml     another configuration (paths relative to it)
"""
from __future__ import annotations

import argparse
import time

import pandas as pd

from . import inputs, metrics, opendsm_runner, preprocess, response
from .folds import assign_folds
from .settings import DEFAULT_CONFIG, ConfigError, Settings, load_settings

FLOAT_FORMAT = "%.6g"


def run_period(settings: Settings, data: preprocess.PeriodData) -> dict:
    """All variants of one period: in-sample and out-of-sample predictions, accuracy, temperature response."""
    period, frame = data.period, data.frame
    folds = assign_folds(data.model_days, settings.n_folds, settings.block_days)
    hour_dates = frame.index.tz_localize(None).normalize()
    pred = pd.DataFrame(index=frame.index)
    pred["local_timestamp"] = frame["local_timestamp"]
    pred["model_day"] = frame["model_day"]
    pred["fold"] = hour_dates.map(folds)
    pred["working_day"] = frame["working_day"]
    pred["observed"] = frame["observed"]
    pred["temperature_C"] = frame["temperature_C"]
    pred["ghi"] = frame["ghi"]
    fits, rows, qualification = {}, [], []
    for variant in settings.variants:
        fitted, p_is = opendsm_runner.in_sample(data, variant, settings)
        p_cv, _ = opendsm_runner.cross_validate(data, variant, folds, settings)
        fits[variant] = fitted
        qualification.append({"period": period, "variant": variant, "fit_seconds": round(fitted.seconds, 2),
                              "disqualification": "; ".join(fitted.disqualification),
                              "warnings": "; ".join(fitted.warnings),
                              "opendsm_cvrmse_adj": fitted.baseline_metrics.get("cvrmse_adj")})
        pred[f"in_sample_{variant}"] = p_is["predicted"].reindex(frame.index)
        pred[f"cv_{variant}"] = p_cv["predicted"].reindex(frame.index)
        pred[f"cv_{variant}_unc"] = p_cv["predicted_unc"].reindex(frame.index)
        for evaluation, col in (("in_sample", f"in_sample_{variant}"), ("cross_validation", f"cv_{variant}")):
            for resolution, sc in metrics.hourly_daily(pred["observed"], pred[col]).items():
                rows.append({"period": period, "variant": variant, "evaluation": evaluation,
                             "resolution": resolution, **sc})
    out = {"data": data, "folds": folds, "pred": pred, "fits": fits, "metrics": rows, "qualification": qualification}
    if "solar" in fits:
        out["response"] = response.temperature_response(fits["solar"], data, settings)
    return out


def write_period(settings: Settings, res: dict) -> None:
    period = res["data"].period
    out = settings.period_dir(period)
    (out / "models").mkdir(parents=True, exist_ok=True)
    res["pred"].to_csv(out / f"predictions_period_{period}.csv", index_label="timestamp", float_format=FLOAT_FORMAT)
    res["folds"].to_frame().to_csv(out / f"folds_period_{period}.csv", float_format=FLOAT_FORMAT)
    if "response" in res:
        res["response"].to_csv(out / f"temperature_response_period_{period}.csv", index=False,
                               float_format=FLOAT_FORMAT)
    for variant, fitted in res["fits"].items():
        (out / "models" / f"opendsm_{variant}_model_period_{period}.json").write_text(fitted.model_json, encoding="utf-8")


def write_summary(settings: Settings, rows: list[dict], qualification: list[dict]) -> None:
    """Accuracy of every variant (benchmark_metrics.csv) and OpenDSM's own qualification of each fit,
    with the disqualifications that were overridden (benchmark_fits.csv)."""
    settings.summary_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(settings.summary_dir / "benchmark_metrics.csv", index=False, float_format=FLOAT_FORMAT)
    pd.DataFrame(qualification).to_csv(settings.summary_dir / "benchmark_fits.csv", index=False)


def run(settings: Settings, periods: list[int] | None = None) -> dict:
    t0 = time.time()
    periods = list(periods or settings.periods)
    frames, days = inputs.load(settings, periods)            # energy, climate and model days, from either source
    datas = {}
    for p in periods:
        datas[p] = preprocess.build_period(settings, p, *frames[p], days)
        i = datas[p].info
        print(f"Period {p}: {i['model_days']} model days ({i['first_day']} -> {i['last_day']}), "
              f"{i['filled_hours']} hour(s) filled, {i['nonexistent_hours_dropped']} non-existent DST hour(s) dropped")

    results, rows, qualification = {}, [], []
    for p, data in datas.items():
        t = time.time()
        results[p] = run_period(settings, data)
        write_period(settings, results[p])
        rows += results[p]["metrics"]
        qualification += results[p]["qualification"]
        cvs = pd.DataFrame(results[p]["metrics"]).query("evaluation == 'cross_validation' and resolution == 'hourly'")
        print(f"Period {p}: out-of-sample hourly CV(RMSE) "
              + ", ".join(f"{v} {c:.1f} %" for v, c in cvs.set_index("variant")["cv_rmse_pct"].items())
              + f" ({time.time() - t:.0f} s)")
    write_summary(settings, rows, qualification)
    print(f"Done in {time.time() - t0:.0f} s. Results in {settings.results_dir}")
    return results


def main(argv=None) -> dict:
    parser = argparse.ArgumentParser(description="OpenDSM benchmark of the cleaned hourly dataset")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--periods", type=int, nargs="+", default=None)
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.config)
    except (ConfigError, FileNotFoundError) as err:
        raise SystemExit(f"Configuration problem: {err}") from None
    return run(settings, args.periods)
