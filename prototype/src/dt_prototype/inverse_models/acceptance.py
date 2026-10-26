"""Project-defined holdout acceptance checks; never fit, tune or certify a model.

The policy is explicit and recorded. Processing completion is distinct from
measured-data acceptance. Simulated fixtures cannot pass empirical validation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .adapters import load_dataset
from .data import keys, load_json, sha
from .reporting import scores


def load_policy(path):
    policy = load_json(path)
    required = {"schema_version", "description", "holdout_split", "minimum_training_days",
                "minimum_holdout_days", "minimum_holdout_observations", "minimum_training_temperature_span_C",
                "minimum_prediction_coverage", "maximum_abs_NMBE_pct", "maximum_CV_RMSE_pct",
                "require_native_qualification"}
    keys(policy, required, "acceptance policy")
    if set(policy) != required or policy["schema_version"] != "1.0":
        raise ValueError("explicit policy v1 fields are required")
    if policy["holdout_split"] not in {"validation", "test"}:
        raise ValueError("select validation or test; training scores cannot establish acceptance")
    if type(policy["require_native_qualification"]) is not bool:
        raise ValueError("require_native_qualification must be boolean")
    if not isinstance(policy["description"], str) or not policy["description"].strip():
        raise ValueError("policy description is required")
    numeric = required - {"schema_version", "description", "holdout_split", "require_native_qualification", "maximum_CV_RMSE_pct"}
    for key in numeric:
        value = policy[key]
        if type(value) not in {int, float} or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{key} must be finite and positive")
    if policy["minimum_prediction_coverage"] > 1 or type(policy["minimum_holdout_observations"]) is not int:
        raise ValueError("coverage must be <=1 and observation count must be integer")
    limits = policy["maximum_CV_RMSE_pct"]
    keys(limits, {"5p_monthly", "opendsm_billing", "opendsm_hourly"}, "CV RMSE limits")
    if set(limits) != {"5p_monthly", "opendsm_billing", "opendsm_hourly"}:
        raise ValueError("specify a CV RMSE limit for each backend")
    if any(type(v) not in {int, float} or not math.isfinite(v) or v <= 0 for v in limits.values()):
        raise ValueError("CV RMSE limits must be positive finite numbers")
    return policy


def assess_run(directory, policy_path):
    directory, policy_path = Path(directory).resolve(), Path(policy_path).resolve()
    policy, manifest = load_policy(policy_path), load_json(directory / "manifest.json")
    if manifest.get("operation") not in {"fit", "evaluate"}:
        raise ValueError("acceptance requires fit or evaluate with observed holdout targets")
    # Use the immutable run snapshot; changed originals cannot relabel data.
    for name, expected in manifest["snapshot_hashes"].items():
        file = (directory / "inputs" / name).resolve()
        if not file.is_relative_to(directory / "inputs") or sha(file) != expected:
            raise ValueError("input snapshot integrity mismatch")
    metadata = load_json(directory / "inputs/series.json")
    if metadata != manifest["series"]:
        raise ValueError("snapshot/manifest identity mismatch")
    config = {"clock": manifest["clock"], "source": {"type": "csv",
        "observations": "observations.csv", "weather": "weather.csv", "series": metadata}}
    dataset = load_dataset(config, directory / "inputs")
    predictions = pd.read_csv(directory / "predictions.csv", dtype={"series_id": str})
    rows = []
    declared = [(model["series_id"], model.get("model_id", "unavailable")) for model in manifest["models"]]
    if len(declared) != len(set(declared)):
        raise ValueError("duplicate declared series/model identities")
    predicted_ids = set(zip(predictions.series_id, predictions.model_id))
    if not predicted_ids.issubset(set(declared)):
        raise ValueError("undeclared prediction series/model")
    for model in manifest["models"]:
        sid, mid = model["series_id"], model.get("model_id", "unavailable")
        reasons = []
        if model["status"] != "complete":
            rows.append(dict(series_id=sid, model_id=mid, status="failed", reasons=["model fit/evaluation failed"]))
            continue
        frame = predictions[predictions.series_id.eq(sid) & predictions.model_id.eq(mid)].copy()
        if frame.empty:
            raise ValueError(f"missing predictions for {sid}/{mid}")
        for key in ["interval_start", "interval_end"]:
            frame[key] = pd.to_datetime(frame[key], utc=True)
        numeric = pd.to_numeric(frame.predicted_energy_kWh, errors="raise")
        if np.isinf(numeric).any():
            raise ValueError("infinite predictions cannot be assessed")
        frame["predicted_energy_kWh"] = numeric
        if frame.duplicated(["interval_start", "interval_end"]).any():
            raise ValueError("duplicate prediction intervals")
        # Reconstruct monthly observed targets from the source, not from CSV labels.
        source = dataset.observations[dataset.observations.series_id.eq(sid)].copy()
        if model["backend"] == "5p_monthly" or (model["backend"] == "opendsm_billing" and source.duration_h.eq(1).all()):
            from .data import monthly
            source = monthly(dataset, sid)
        for key in ["interval_start", "interval_end"]:
            source[key] = pd.to_datetime(source[key], utc=True)
        joined = source.merge(frame, on=["interval_start", "interval_end"], suffixes=("_source", "_prediction"), how="outer", indicator=True, validate="one_to_one")
        if not joined._merge.eq("both").all():
            raise ValueError("prediction intervals differ from input snapshot")
        if not np.allclose(joined.energy_kWh, joined.observed_energy_kWh, equal_nan=True, rtol=1e-9, atol=1e-6):
            raise ValueError("observed targets differ from input snapshot")
        for key in ["split", "quality", "duration_h"]:
            if not (joined[key+"_source"] == joined[key+"_prediction"]).all():
                raise ValueError(f"prediction {key} differs from input snapshot")
        weather = dataset.weather_for(sid).set_index("time").temperature_C
        start = ((frame.interval_start-weather.index[0]).dt.total_seconds()/3600).to_numpy(dtype=int)
        stop = start+frame.duration_h.to_numpy(dtype=int)
        cumulative = np.r_[0, weather.to_numpy().cumsum()]
        frame["temperature_C"] = (cumulative[stop]-cumulative[start])/frame.duration_h.to_numpy()
        good = frame.quality.eq("valid") & frame.observed_energy_kWh.notna()
        train = frame[good & frame.split.eq("train")]
        holdout = frame[good & frame.split.eq(policy["holdout_split"])]
        if frame.predicted_energy_kWh.lt(0).any():
            reasons.append("negative energy predictions require review")
        # An evaluate run can supply only holdout observations: use saved training
        # provenance only when present, otherwise fail the coverage criterion.
        train_days, holdout_days = float(train.duration_h.sum()/24), float(holdout.duration_h.sum()/24)
        span = float(train.temperature_C.max()-train.temperature_C.min()) if len(train) else 0.0
        metric = scores(holdout)
        if train_days < policy["minimum_training_days"]: reasons.append("insufficient documented training coverage")
        if holdout_days < policy["minimum_holdout_days"]: reasons.append("insufficient observed holdout duration")
        if len(holdout) < policy["minimum_holdout_observations"]: reasons.append("insufficient holdout observation count")
        if len(train) and len(holdout) and train.interval_end.max() > holdout.interval_start.min():
            reasons.append("holdout must follow the training block")
        if span < policy["minimum_training_temperature_span_C"]: reasons.append("insufficient training temperature span")
        for name, bound in [("coverage_fraction", policy["minimum_prediction_coverage"]),
                            ("NMBE_pct", policy["maximum_abs_NMBE_pct"]),
                            ("CV_RMSE_pct", policy["maximum_CV_RMSE_pct"][model["backend"]])]:
            value = metric[name]
            passes = math.isfinite(value) and (value >= bound if name == "coverage_fraction" else abs(value) <= bound)
            if not passes: reasons.append(f"holdout {name} outside policy or undefined")
        native = model.get("diagnostics", {})
        reporting = model.get("reporting_diagnostics", [])
        if policy["require_native_qualification"] and (native.get("disqualification") or any(r.get("disqualification") for r in reporting)):
            reasons.append("native disqualification requires review")
        measured = metadata[sid]["source_type"] == "measured"
        if not measured:
            reasons.append("synthetic/simulated source cannot establish empirical validation")
        rows.append(dict(series_id=sid, model_id=mid, status="accepted" if not reasons else "review_required",
            reasons=reasons, training_days=train_days, holdout_days=holdout_days,
            training_temperature_span_C=span, metrics=metric))
    return dict(schema_version="1.0", created_utc=datetime.now(timezone.utc).isoformat(),
        status="accepted" if rows and all(r["status"] == "accepted" for r in rows) and manifest["status"] == "complete" else "review_required",
        scope="project-defined observed holdout accuracy; not statutory or M&V certification",
        run=str(directory), manifest_sha256=sha(directory / "manifest.json"),
        predictions_sha256=sha(directory / "predictions.csv"), policy_sha256=sha(policy_path), policy=policy, models=rows)


def main(argv=None):
    from .workflow import dump
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.report.exists():
        parser.error("report already exists")
    try:
        result = assess_run(args.results, args.policy)
    except Exception as error:
        parser.exit(1, f"Validation failed: {error}\n")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    dump(args.report, result)
    print(f"Measured-data acceptance: {result['status']}. {args.report}")
    return 0 if result["status"] == "accepted" else 2


if __name__ == "__main__":
    raise SystemExit(main())
