"""Common observed-minus-predicted metrics, complete-period aggregation and plots."""
import numpy as np
import pandas as pd


def scores(frame):
    eligible = frame.quality.eq("valid") & frame.observed_energy_kWh.notna() & ~frame.split.isin(["excluded", "predict"])
    valid = eligible & frame.predicted_energy_kWh.notna()
    y, prediction = frame.loc[valid, "observed_energy_kWh"], frame.loc[valid, "predicted_energy_kWh"]
    residual = y-prediction
    n = len(y)
    mean = y.mean() if n else np.nan
    sst = ((y-mean)**2).sum()
    rmse = float(np.sqrt((residual**2).mean())) if n else np.nan
    power_error = residual/frame.loc[valid, "duration_h"]
    return dict(expected_observations=int(eligible.sum()), scored_observations=n,
                coverage_fraction=float(valid.sum()/eligible.sum()) if eligible.sum() else np.nan,
                observed_energy_kWh=float(y.sum()) if n else np.nan,
                predicted_energy_kWh=float(prediction.sum()) if n else np.nan,
                residual_energy_kWh=float(residual.sum()) if n else np.nan,
                RMSE_energy_kWh=rmse, MAE_energy_kWh=float(residual.abs().mean()) if n else np.nan,
                RMSE_average_power_kW=float(np.sqrt((power_error**2).mean())) if n else np.nan,
                CV_RMSE_pct=100*rmse/mean if n and mean > 1e-12 else np.nan,
                NMBE_pct=100*residual.mean()/mean if n and mean > 1e-12 else np.nan,
                R2=float(1-(residual**2).sum()/sst) if n and sst > 0 else np.nan,
                parameter_correction=0, residual_convention="observed_minus_predicted")


def aggregate_monthly(frame):
    """Only exact, complete calendar-month partitions; no partial-month totals."""
    records = []
    # Caller supplies local calendar identity, avoiding UTC month shifts.
    for _, group in frame.groupby("period_id"):
        if not group.month_complete.all() or group.split.nunique() != 1:
            continue
        record = group.iloc[0].to_dict()
        if len(group) > 1:
            record["observed_energy_kWh"] = group.observed_energy_kWh.sum() if group.observed_energy_kWh.notna().all() else np.nan
            record["predicted_energy_kWh"] = group.predicted_energy_kWh.sum() if group.predicted_energy_kWh.notna().all() else np.nan
            record["duration_h"] = group.duration_h.sum()
            record["temperature_C"] = float(np.average(group.temperature_C,weights=group.duration_h))
            record["residual_energy_kWh"] = record["observed_energy_kWh"]-record["predicted_energy_kWh"]
            record["native_uncertainty"] = np.nan  # no unproved independence assumption
            if pd.isna(record["predicted_energy_kWh"]):
                record["prediction_reason"] = "incomplete_month_prediction"
            record["quality"] = "valid" if group.quality.eq("valid").all() else "excluded"
            record["interval_end"] = group.interval_end.iloc[-1]
        records.append(record)
    return pd.DataFrame(records)


def write_reports(predictions, directory):
    metrics, monthly = [], []
    for identity, group in predictions.groupby(["series_id", "model_id"], sort=True):
        for split, part in group.groupby("split"):
            metrics.append(dict(series_id=identity[0], model_id=identity[1], split=split, resolution="native", **scores(part)))
        month = aggregate_monthly(group)
        if not month.empty:
            monthly.append(month)
            for split, part in month.groupby("split"):
                metrics.append(dict(series_id=identity[0], model_id=identity[1], split=split, resolution="monthly", **scores(part)))
    metric_frame = pd.DataFrame(metrics)
    metric_frame.to_csv(directory / "metrics.csv", index=False)
    month_frame = pd.concat(monthly, ignore_index=True) if monthly else pd.DataFrame(columns=predictions.columns)
    month_frame.to_csv(directory / "monthly_predictions.csv", index=False)
    # Common-support monthly scores prevent unequal missingness flattering one backend.
    common = []
    for sid, series in month_frame.groupby("series_id"):
        model_ids = set(predictions.loc[predictions.series_id == sid, "model_id"])
        usable = series[series.quality.eq("valid") & series.observed_energy_kWh.notna() & series.predicted_energy_kWh.notna()]
        counts = usable.groupby(["period_id", "split"]).model_id.nunique()
        periods = set(counts[counts == len(model_ids)].index)
        selected = usable.loc[np.array([tuple(row) in periods for row in usable[["period_id", "split"]].to_numpy()], dtype=bool)]
        for (model, split), part in selected.groupby(["model_id", "split"]):
            common.append(dict(series_id=sid, model_id=model, split=split, resolution="monthly_common_support", **scores(part)))
    pd.DataFrame(common, columns=metric_frame.columns).to_csv(directory / "comparison_metrics.csv", index=False)
    if not month_frame.empty:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from dt_prototype.common.output_paths import output_component

        figures = directory / "figures"
        figures.mkdir()
        for sid, group in month_frame.groupby("series_id"):
            fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True, constrained_layout=True)
            for model, part in group.groupby("model_id"):
                part = part.sort_values("period_id")
                x = pd.to_datetime(part.period_id)
                axes[0].plot(x, part.predicted_energy_kWh, marker=".", label=model)
                axes[1].plot(x, part.observed_energy_kWh-part.predicted_energy_kWh, marker=".", label=model)
            observed = group.drop_duplicates("period_id").sort_values("period_id")
            axes[0].plot(pd.to_datetime(observed.period_id), observed.observed_energy_kWh, "k--", label="observed")
            axes[0].set_ylabel("Monthly energy [kWh]")
            axes[1].set_ylabel("Observed − predicted [kWh]")
            axes[0].set_title(sid, fontsize=9)
            axes[0].legend(fontsize=8)
            axes[1].axhline(0, color="grey", linewidth=0.5)
            fig.savefig(figures / (output_component(sid) + ".png"), dpi=130)
            plt.close(fig)
            fig, axis = plt.subplots(figsize=(8,5), constrained_layout=True)
            axis.scatter(observed.temperature_C,observed.observed_energy_kWh/observed.duration_h,
                         color="black",marker="x",label="observed monthly mean")
            for model, part in group.groupby("model_id"):
                axis.scatter(part.temperature_C,part.predicted_energy_kWh/part.duration_h,s=22,label=model)
            axis.set_xlabel("Monthly mean outdoor temperature [°C]")
            axis.set_ylabel("Monthly mean power [kW; energy / elapsed hours]")
            axis.set_title("Monthly energy signatures; model predictions at observed weather",fontsize=9)
            axis.legend(fontsize=7)
            fig.savefig(figures/(output_component(sid)+"_signature.png"),dpi=130)
            plt.close(fig)
    return metric_frame


def write_run_report(directory, manifest):
    """Expose actual run status, per-model failures and links beside the CSVs."""
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    lines = ["# Inverse-model results", "",
        f"Operation: **{manifest['operation']}**. Processing status: **{manifest['status']}**.",
        f"Successful models: **{manifest['successful_models']}**; failed models: **{manifest['failed_models']}**; "
        f"missing predictions in successful models: **{manifest['missing_predictions']}**.", "",
        "Processing, qualification and held-out coverage are separate. Fit success does not establish measured-building accuracy or M&V qualification.", "",
        "| Series | Model | Status | Qualification / issue |", "| --- | --- | --- | --- |"]
    for model in manifest["models"]:
        note = model.get("error", model.get("qualification", ""))
        if model.get("warnings"):
            note += "; " + ", ".join(model["warnings"])
        lines.append("| " + " | ".join(cell(v) for v in [model["series_id"], model.get("model_id", "unavailable"), model["status"], note]) + " |")
    lines += ["", "Full native diagnostics, tracebacks, input snapshots and source/environment provenance are in [manifest.json](manifest.json).", "",
        "Common scores use observed minus predicted and p=0. Monthly comparisons use complete periods and common prediction support across successful backends. "
        "Inspect model failures separately; failed models have no comparison score. Native-hourly scores and monthly scores have different resolutions.", "",
        "Training metrics describe fitting. Validation/test metrics require eligible observed energy; prediction-only rows have no accuracy score.", ""]
    for name in ["models.csv", "metrics.csv", "comparison_metrics.csv", "predictions.csv", "monthly_predictions.csv", "model_index.json"]:
        if (directory/name).exists():
            lines.append(f"- [{name}]({name})")
    figures = sorted((directory/"figures").glob("*.png"))
    if figures:
        lines += ["", "## Figures", "", "Monthly energy/residual plots and mean-power energy signatures at the supplied weather:", ""]
        lines += [f"- [{file.stem}](figures/{file.name})" for file in figures]
    (directory/"report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
