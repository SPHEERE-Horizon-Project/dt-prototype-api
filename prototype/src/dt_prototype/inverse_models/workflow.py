"""Immutable fit/predict/evaluate orchestration for independent energy series."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from dt_prototype.common.output_paths import output_component
from . import __version__
from .adapters import load_dataset
from .backends import call_worker, fivep
from .data import BACKENDS, keys, load_json, sha
from .reporting import write_reports, write_run_report


def dump(path, value):
    def clean(item):
        if isinstance(item, dict):
            return {k: clean(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [clean(v) for v in item]
        if isinstance(item, (float, np.floating)) and not np.isfinite(item):
            return None
        if isinstance(item, np.generic):
            return item.item()
        return item
    Path(path).write_text(json.dumps(clean(value), indent=2, allow_nan=False)+"\n", encoding="utf-8")


def model_settings(models):
    if not isinstance(models, list) or not models:
        raise ValueError("models must be a nonempty list")
    result = []
    for value in models:
        model = {"backend": value} if isinstance(value, str) else dict(value)
        keys(model, {"backend", "options"}, "model")
        backend = model.get("backend")
        if not isinstance(backend, str) or backend not in BACKENDS:
            raise ValueError(f"unknown backend {backend}")
        options = model.get("options", {})
        keys(options, {"fit"} if backend == "5p_monthly" else {"variant", "seed", "allow_disqualified"}, "backend options")
        if backend != "5p_monthly":
            if type(options.get("allow_disqualified", False)) is not bool or type(options.get("seed", 42)) is not int:
                raise ValueError("allow_disqualified must be boolean and seed integer")
            if options.get("variant", "nonsolar") not in {"solar", "nonsolar"}:
                raise ValueError("hourly variant must be solar or nonsolar")
            if backend == "opendsm_billing" and "variant" in options:
                raise ValueError("billing does not use hourly solar/nonsolar variants")
        mid = backend + ("_" + options.get("variant", "nonsolar") if backend == "opendsm_hourly" else "")
        if mid in {r["model_id"] for r in result}:
            raise ValueError("duplicate model selection")
        result.append(dict(backend=backend, model_id=mid, options=options))
    return result


def _calendar_columns(data, clock):
    data = data.copy()
    starts = pd.DatetimeIndex(data.interval_start)
    data["period_id"] = starts.tz_localize(None).to_period("M").astype(str)
    data["month_complete"] = False
    for period, group in data.groupby("period_id"):
        start = pd.Timestamp(period).tz_localize(clock["timezone"])
        end = start + pd.offsets.MonthBegin(1)
        complete = (group.interval_start.iloc[0] == start and group.interval_end.iloc[-1] == end and
                    all(a == b for a, b in zip(group.interval_start.iloc[1:], group.interval_end.iloc[:-1])))
        data.loc[group.index, "month_complete"] = complete
    return data


def run_inverse(configuration, output, *, simulation_results=None):
    """Run data models without requiring a geometry or invoking physical solvers."""
    source, out = Path(configuration).resolve(), Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    manifest = dict(schema_version="1.0", component_version=__version__, mode="inverse", status="running",
                    started_utc=datetime.now(timezone.utc).isoformat(), models=[], python=sys.version,
                    code_hashes={p.name: sha(p) for p in Path(__file__).parent.glob("*.py")})
    dump(out / "manifest.json", manifest)
    try:
        settings = load_json(source)
        keys(settings, {"schema_version", "description", "operation", "source", "clock", "models", "model_dir", "opendsm_python", "worker_timeout_s"}, "inverse configuration")
        if settings.get("schema_version") != "1.0" or settings.get("operation", "fit") not in {"fit", "predict", "evaluate"}:
            raise ValueError("expected schema_version 1.0 and operation fit, predict or evaluate")
        operation = settings.get("operation", "fit")
        dataset = load_dataset(settings, source.parent, simulation_results)
        manifest.update(configuration_path=str(source), configuration_sha256=sha(source), operation=operation,
                        input_provenance=dataset.provenance, clock=dataset.clock, series=dataset.series,
                        target_units="kWh per explicit interval", residual_convention="observed_minus_predicted")
        inputs = out / "inputs"
        inputs.mkdir()
        dataset.observations.to_csv(inputs / "observations.csv", index=False)
        dataset.weather.to_csv(inputs / "weather.csv", index=False)
        dump(inputs / "series.json", dataset.series)
        manifest["snapshot_hashes"] = {p.name: sha(p) for p in inputs.iterdir()}
        saved_models = {}
        if operation != "fit":
            model_dir = (source.parent / settings["model_dir"]).resolve()
            index = load_json(model_dir / "model_index.json")
            if index.get("schema_version") != "1.0":
                raise ValueError("unsupported model index")
            for entry in index["models"]:
                path = (model_dir / entry["artifact"]).resolve()
                if not path.is_relative_to(model_dir) or sha(path) != entry["sha256"]:
                    raise ValueError("model artifact path/hash mismatch")
                artifact = load_json(path)
                if artifact["series_id"] in dataset.series:
                    saved_models[(artifact["series_id"], artifact["model_id"])] = artifact
            manifest["model_index_sha256"] = sha(model_dir / "model_index.json")
            models = model_settings(settings["models"]) if "models" in settings else list({a["model_id"]: {k:a[k] for k in ["backend", "model_id", "options"]} for a in saved_models.values()}.values())
            if not models:
                raise ValueError("no saved models match the requested series")
        else:
            models = model_settings(settings.get("models", ["5p_monthly"]))
        results, artifacts, worker_tasks, pending, details = [], [], [], {}, []
        worker_dir = out / "worker"
        for sid in dataset.series:
            # A partial training run need not have the same saved backends for
            # every building. Omitted selection means available artifacts only.
            selected = models
            if operation != "fit" and "models" not in settings:
                selected = [{k:a[k] for k in ["backend", "model_id", "options"]}
                            for (series_id, _), a in saved_models.items() if series_id == sid]
                if not selected:
                    details.append(dict(series_id=sid, status="failed", error="no saved models for requested series"))
            for model in selected:
                identity = dict(series_id=sid, **model)
                try:
                    if operation == "evaluate":
                        observations = dataset.observations[dataset.observations.series_id == sid]
                        eligible = (observations.quality.eq("valid") & observations.energy_kWh.notna()
                                    & ~observations.split.isin(["predict", "excluded"]))
                        if not eligible.any():
                            raise ValueError("evaluate requires eligible observed energy; use predict for targets-free inputs")
                    saved = saved_models.get((sid, model["model_id"]))
                    if operation != "fit" and saved is None:
                        raise ValueError("saved model missing for requested series/model")
                    if saved:
                        if saved.get("schema_version") != "1.0" or saved["clock"] != dataset.clock:
                            raise ValueError("saved model schema/clock mismatch; express new inputs in the training clock")
                        for key in ["building_id", "zone_id", "carrier", "meter_boundary_id", "scenario_id", "representation"]:
                            if saved["series"].get(key) != dataset.series[sid].get(key):
                                raise ValueError(f"saved model physical identity mismatch: {key}")
                        identity["options"] = saved["options"]
                    if model["backend"] == "5p_monthly":
                        data, payload = fivep(dataset, sid, identity["options"], saved["payload"] if saved else None)
                        results.append((identity, data, payload))
                    else:
                        packet = worker_dir / str(len(worker_tasks))
                        packet.mkdir(parents=True)
                        data = dataset.observations[dataset.observations.series_id == sid].reset_index(drop=True)
                        if model["backend"] == "opendsm_billing" and data.duration_h.eq(1).all():
                            from .data import monthly
                            data = monthly(dataset, sid)
                        data.to_csv(packet / "observations.csv", index=False)
                        dataset.weather_for(sid).to_csv(packet / "weather.csv", index=False)
                        if saved:
                            dump(packet / "saved_payload.json", saved["payload"])
                        task_id = str(len(worker_tasks))
                        worker_tasks.append(dict(task_id=task_id, backend=model["backend"], options=identity["options"], clock=dataset.clock,
                            observations=str(packet / "observations.csv"), weather=str(packet / "weather.csv"),
                            saved_payload=str(packet / "saved_payload.json") if saved else None,
                            prediction_output=str(packet / "predictions.csv"), payload_output=str(packet / "payload.json")))
                        pending[task_id] = (identity, data, packet)
                except Exception as error:
                    details.append({**identity, "status": "failed", "error": f"{type(error).__name__}: {error}"})
        if worker_tasks:
            timeout = settings.get("worker_timeout_s", 1800)
            if type(timeout) is not int or timeout <= 0:
                raise ValueError("worker_timeout_s must be a positive integer")
            executable = (source.parent / settings["opendsm_python"]).resolve() if settings.get("opendsm_python") else None
            try:
                response = call_worker(worker_tasks, executable, worker_dir, timeout)
            except Exception as error:
                response = {"tasks":[{"task_id":t["task_id"],"status":"failed","error":f"{type(error).__name__}: {error}"} for t in worker_tasks],"versions":{}}
            manifest["worker_versions"] = response["versions"]
            for item in response["tasks"]:
                identity, data, packet = pending[item["task_id"]]
                if item["status"] == "failed":
                    details.append({**identity, **item})
                else:
                    predicted = pd.read_csv(packet / "predictions.csv")
                    if len(predicted) != len(data):
                        raise RuntimeError("worker prediction alignment mismatch")
                    data = data.copy()
                    for column in predicted:
                        data[column] = predicted[column].to_numpy()
                    results.append((identity, data, load_json(packet / "payload.json")))
        for identity, data, payload in results:
            sid, mid = identity["series_id"], identity["model_id"]
            negative = data.predicted_energy_kWh.lt(0)
            data.loc[negative, "prediction_reason"] = "native_negative_prediction"
            artifact = dict(schema_version="1.0", **identity, series=dataset.series[sid], clock=dataset.clock, payload=payload)
            path = out / "models" / output_component(sid) / output_component(mid) / "artifact.json"
            path.parent.mkdir(parents=True)
            dump(path, artifact)
            artifacts.append(dict(series_id=sid, model_id=mid, artifact=path.relative_to(out).as_posix(), sha256=sha(path)))
            native = payload.get("diagnostics", {})
            warning = list(payload.get("parameters", {}).get("warning_codes", []))
            compatibility = payload.get("compatibility", {})
            if compatibility.get("zero_parameter_metric_calls", 0):
                warning.append("HOURLY_ZERO_COEFFICIENT_METRICS_COMPATIBILITY")
            holdout = data.split.isin(["validation", "test"]) & data.quality.eq("valid") & data.energy_kWh.notna()
            if operation == "fit" and not holdout.any():
                warning.append("NO_HELD_OUT_OBSERVATIONS")
            if negative.any():
                warning.append("NATIVE_NEGATIVE_PREDICTIONS_RETAINED")
            reporting = payload.get("reporting_diagnostics", [])
            model_status = "review" if warning or native.get("disqualification") or native.get("warnings") or any(r.get("disqualification") or r.get("warnings") for r in reporting) else "no_native_disqualification"
            details.append({**identity, "status": "complete", "qualification": model_status,
                            "warnings": warning, "diagnostics": native, "reporting_diagnostics":reporting,
                            "runtime_warnings":payload.get("runtime_warnings",[]),
                            "compatibility": compatibility})
        columns = []
        for identity, data, payload in results:
            if "temperature_C" not in data:
                wx = dataset.weather_for(identity["series_id"]).set_index("time").temperature_C
                start = ((data.interval_start-wx.index[0]).dt.total_seconds()/3600).to_numpy(dtype=int)
                stop = start+data.duration_h.to_numpy(dtype=int)
                cumulative = np.r_[0, wx.to_numpy().cumsum()]
                data["temperature_C"] = (cumulative[stop]-cumulative[start])/data.duration_h.to_numpy()
            data = _calendar_columns(data, dataset.clock).rename(columns={"energy_kWh":"observed_energy_kWh"})
            data["model_id"] = identity["model_id"]
            data["backend"] = identity["backend"]
            for key, value in dataset.series[identity["series_id"]].items():
                data[key] = value
            data["residual_energy_kWh"] = data.observed_energy_kWh-data.predicted_energy_kWh
            columns.append(data)
        manifest["models"] = details
        dump(out / "model_index.json", {"schema_version":"1.0", "models":artifacts})
        pd.DataFrame([{k:v for k,v in r.items() if k not in {"options","diagnostics","traceback"}} for r in details]).to_csv(out / "models.csv", index=False)
        if columns:
            predictions = pd.concat(columns, ignore_index=True)
            predictions.to_csv(out / "predictions.csv", index=False)
            metrics = write_reports(predictions, out)
            missing_predictions = int((predictions.predicted_energy_kWh.isna() & ~predictions.split.eq("excluded")).sum())
        else:
            missing_predictions = 0
            pd.DataFrame(columns=["series_id", "model_id", "interval_start", "interval_end", "predicted_energy_kWh"]).to_csv(out / "predictions.csv", index=False)
        failed = sum(r["status"] == "failed" for r in details)
        manifest.update(status="failed" if not results else "partial" if failed else "incomplete" if missing_predictions else "complete",
                        successful_models=len(results), failed_models=failed, missing_predictions=missing_predictions,
                        coverage_scope="declared series and intervals only", completed_utc=datetime.now(timezone.utc).isoformat())
        dump(out / "manifest.json", manifest)
        write_run_report(out, manifest)
        return out
    except Exception as error:
        manifest.update(status="failed", error=f"{type(error).__name__}: {error}")
        dump(out / "manifest.json", manifest)
        raise
