"""Existing 5P facade and one batched subprocess boundary for OpenDSM."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from .data import load_json, monthly


def fivep(dataset, sid, options, payload=None):
    from dt_prototype.monthly_ss_simplified.five_parameter import FiveParameterConfig, FiveParameterFit, fit_five_parameter

    data = monthly(dataset, sid)
    train = data[data.split.eq("train") & data.quality.eq("valid") & data.energy_kWh.notna()]
    if payload is None:
        fit = fit_five_parameter(train.temperature_C, train.energy_kWh/train.days,
                                 FiveParameterConfig(**options.get("fit", {})))
        payload = {"parameters": asdict(fit), "temperature_min_C": float(train.temperature_C.min()),
                   "temperature_max_C": float(train.temperature_C.max()),
                   "power_basis": "legacy E/(24*calendar_days); civil elapsed-hour power reported separately"}
    else:
        fit = FiveParameterFit(**payload["parameters"])
    data["predicted_energy_kWh"] = fit.predict_daily_energy(data.temperature_C)*data.days
    outside = (data.temperature_C < payload["temperature_min_C"]) | (data.temperature_C > payload["temperature_max_C"])
    data["prediction_reason"] = np.where(outside, "temperature_extrapolation", "ok")
    data["native_uncertainty"] = np.nan
    return data, payload


def call_worker(tasks, executable, directory, timeout=1800):
    if not executable or not Path(executable).is_file():
        raise ValueError("OpenDSM models require an existing opendsm_python executable; see requirements-opendsm.txt")
    directory = Path(directory)
    response = directory / "response.json"
    request = directory / "request.json"
    request.write_text(json.dumps({"tasks": tasks, "response": str(response)}, indent=2), encoding="utf-8")
    environment = dict(os.environ)
    # Bounded resource use and reproducibility; these affect only the worker.
    environment.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMBA_NUM_THREADS="1")
    worker = Path(__file__).with_name("opendsm_worker.py")
    completed = subprocess.run([str(executable), str(worker), "--request", str(request)], shell=False,
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout, env=environment)
    (directory / "worker.log").write_text(completed.stdout + "\n" + completed.stderr, encoding="utf-8")
    if completed.returncode != 0 or not response.exists():
        raise RuntimeError(f"OpenDSM worker failed (exit {completed.returncode}); inspect {directory / 'worker.log'}")
    return load_json(response)
