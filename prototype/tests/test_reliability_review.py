"""Boundary regressions found in the 22 October forward/inverse review."""
import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from dt_prototype import pipeline
from dt_prototype.common.project import ProjectInputs
from dt_prototype.energy_carriers.config import EnergyConfig
from dt_prototype.inverse_models.adapters import _split, load_dataset
from dt_prototype.inverse_models.data import load_json
from dt_prototype.inverse_models.workflow import run_inverse, dump

ROOT = Path(__file__).resolve().parents[1]
CLOCK = {"convention":"standard", "timezone":"Etc/GMT-1"}


def project_config():
    config = load_json(ROOT/"configs/example.json")
    for key in ["geometry", "weather_epw", "envelopes", "schedules", "systems"]:
        config["inputs"][key] = str((ROOT/"configs"/config["inputs"][key]).resolve())
    return config


def inverse_config():
    config = load_json(ROOT/"configs/inverse_billing_example.json")
    config["models"] = ["5p_monthly"]
    for key in ["observations", "weather"]:
        config["source"][key] = str((ROOT/"configs"/config["source"][key]).resolve())
    return config


def run(tmp_path, config, name):
    file = tmp_path/(name+".json")
    file.write_text(json.dumps(config), encoding="utf-8")
    return run_inverse(file, tmp_path/name)


@pytest.mark.parametrize("loader,filename", [(ProjectInputs.load,"example.json"), (EnergyConfig.load,"energy_example.json")])
def test_forward_json_duplicate_fields_rejected(tmp_path, loader, filename):
    text = (ROOT/"configs"/filename).read_text(encoding="utf-8")
    text = text.replace('"schema_version": "1.0"', '"schema_version": "0.0", "schema_version": "1.0"')
    file = tmp_path/"duplicate.json"
    file.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        loader(file)


@pytest.mark.parametrize("loader,config", [(ProjectInputs.load,project_config),
    (EnergyConfig.load,lambda: load_json(ROOT/"configs/energy_example.json"))])
def test_forward_json_accepts_utf8_bom(tmp_path, loader, config):
    file = tmp_path/"bom.json"
    file.write_text(json.dumps(config()), encoding="utf-8-sig")
    loader(file)


@pytest.mark.parametrize("section", [None, "inputs", "simplified"])
def test_unknown_forward_settings_cannot_be_silently_ignored(tmp_path, section):
    config = project_config()
    (config if section is None else config[section])["misspelled_setting"] = 1
    file = tmp_path/"typo.json"
    file.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="[Uu]nknown"):
        ProjectInputs.load(file)


def test_chronological_splits_preserve_excluded_and_prediction_rows():
    starts = pd.date_range("2022-01-01", periods=4, freq="MS", tz=CLOCK["timezone"])
    data = pd.DataFrame(dict(interval_start=starts, interval_end=starts+pd.offsets.MonthBegin(1),
        split=["excluded", "predict", "train", "train"]))
    result = _split(data, {"train_end":"2022-04-01"}, CLOCK)
    assert result.split.tolist() == ["excluded", "predict", "train", "validation"]


@pytest.mark.parametrize("defect", ["quality", "split", "extra_observation_column", "extra_weather_column", "validation_without_train", "wrong_source_fields"])
def test_bad_inverse_fields_fail_before_aggregation_or_defaults(tmp_path, defect):
    config = inverse_config()
    starts = pd.date_range("2022-01-01", periods=4, freq="15min")
    data = pd.DataFrame(dict(series_id=next(iter(config["source"]["series"])), interval_start=starts,
        interval_end=starts+pd.Timedelta(minutes=15), energy_kWh=1.0, split="train", quality="valid"))
    if defect in {"quality", "split"}:
        data[defect] = "typo"
        if defect == "split": config["source"]["train_end"] = "2023-01-01"
    elif defect == "extra_observation_column": data["energy_Kwh"] = 1.0
    elif defect == "extra_weather_column":
        weather = pd.read_csv(config["source"]["weather"])
        weather["GHI_wrong"] = 0
        weather.to_csv(tmp_path/"weather.csv", index=False)
        config["source"]["weather"] = str(tmp_path/"weather.csv")
    elif defect == "validation_without_train": config["source"]["validation_end"] = "2023-01-01"
    else: config["source"]["resolution"] = "hourly"
    data.to_csv(tmp_path/"observations.csv", index=False)
    config["source"]["observations"] = str(tmp_path/"observations.csv")
    with pytest.raises(ValueError):
        load_dataset(config, tmp_path)


def test_default_reload_only_requests_each_series_available_artifacts(tmp_path, monkeypatch):
    from dt_prototype.inverse_models import workflow
    config = inverse_config()
    sid = next(iter(config["source"]["series"]))
    frame = pd.read_csv(config["source"]["observations"])
    second = frame.assign(series_id="second")
    pd.concat([frame,second]).to_csv(tmp_path/"two.csv", index=False)
    config["source"]["observations"] = str(tmp_path/"two.csv")
    config["source"]["series"]["second"] = dict(config["source"]["series"][sid], building_id="002")
    trained = run(tmp_path, config, "fit")
    # One series has a second saved backend; the other legitimately has only 5P.
    index = load_json(trained/"model_index.json")
    item = next(v for v in index["models"] if v["series_id"]==sid)
    artifact = load_json(trained/item["artifact"])
    artifact.update(backend="opendsm_billing", model_id="opendsm_billing", options={})
    extra = trained/"billing.json"
    dump(extra, artifact)
    from dt_prototype.inverse_models.data import sha
    index["models"].append(dict(series_id=sid, model_id="opendsm_billing", artifact="billing.json", sha256=sha(extra)))
    dump(trained/"model_index.json", index)
    def worker(tasks, executable, directory, timeout):
        for task in tasks:
            observed = pd.read_csv(task["observations"])
            pd.DataFrame(dict(predicted_energy_kWh=observed.energy_kWh, prediction_reason="ok",native_uncertainty=np.nan)).to_csv(task["prediction_output"], index=False)
            dump(task["payload_output"], {})
        return {"tasks":[{"task_id":t["task_id"],"status":"complete"} for t in tasks],"versions":{}}
    monkeypatch.setattr(workflow, "call_worker", worker)
    del config["models"]
    config.update(operation="predict", model_dir=str(trained))
    out = run(tmp_path, config, "predict")
    result = load_json(out/"manifest.json")
    assert result["status"] == "complete" and result["successful_models"] == 3


def test_missing_holdout_targets_are_not_reported_as_validation(tmp_path):
    config = inverse_config()
    data = pd.read_csv(config["source"]["observations"])
    data.loc[data.split.eq("validation"), "energy_kWh"] = np.nan
    data.to_csv(tmp_path/"empty_validation.csv", index=False)
    config["source"]["observations"] = str(tmp_path/"empty_validation.csv")
    out = run(tmp_path, config, "fit")
    assert "NO_HELD_OUT_OBSERVATIONS" in load_json(out/"manifest.json")["models"][0]["warnings"]
    config.update(operation="evaluate", model_dir=str(out))
    data["energy_kWh"] = np.nan
    data.to_csv(tmp_path/"empty_validation.csv", index=False)
    evaluated = run(tmp_path, config, "evaluate")
    assert load_json(evaluated/"manifest.json")["status"] == "failed"
    assert "evaluate requires eligible observed energy" in (evaluated/"report.md").read_text(encoding="utf-8")


def test_forward_analysis_rejects_a_csv_source_before_running_energy(tmp_path, monkeypatch):
    config = load_json(ROOT/"configs/pipeline_example.json")
    for key in ["project_config", "energy_config"]:
        config[key] = str((ROOT/"configs"/config[key]).resolve())
    config["analysis"] = {"enabled":True, "config":str(ROOT/"configs/inverse_5p_example.json")}
    file = tmp_path/"pipeline.json"
    file.write_text(json.dumps(config))
    solver = Mock(side_effect=AssertionError("energy must not run for an invalid analysis source"))
    monkeypatch.setattr("dt_prototype.energy_carriers.workflow.run_project",solver)
    with pytest.raises(ValueError, match="energy_run"):
        pipeline.run_pipeline(file,tmp_path/"out")
    solver.assert_not_called()


@pytest.mark.parametrize("selector", ["buildings", "models"])
def test_simulation_selectors_require_lists_of_exact_ids(selector):
    config = load_json(ROOT/"configs/inverse_simulation_example.json")
    config["source"][selector] = "18" if selector == "buildings" else "Dynamic_RC 5R1C"
    with pytest.raises(ValueError, match=selector):
        load_dataset(config, ROOT/"configs")


def test_unknown_requested_building_does_not_silently_drop_from_a_subset():
    config = load_json(ROOT/"configs/inverse_simulation_example.json")
    config["source"]["buildings"] = ["1", "missing-building"]
    with pytest.raises(ValueError, match="requested buildings"):
        load_dataset(config, ROOT/"configs")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1e999"])
def test_forward_reader_rejects_all_nonfinite_json_numbers(tmp_path, value):
    from dt_prototype.common.json_io import load_json as strict_json
    file = tmp_path/"nonfinite.json"
    file.write_text('{"unused_metadata":'+value+'}')
    with pytest.raises(ValueError, match="non-finite"):
        strict_json(file)


def test_vbdd_thermal_runner_exports_separate_inverse_zone_series(tmp_path):
    from dt_prototype.monthly_ss_vbdd.cli import main
    directory = tmp_path/"vb"
    main(["--config",str(ROOT/"configs/example.json"),"--output",str(directory)])
    manifest = load_json(directory/"manifest.json")
    assert manifest["status"] == "complete" and manifest["engine"] == "Monthly_SS_VBDD"
    config = {"source":{"type":"thermal_monthly", "results":str(directory),
        "project_config":str(ROOT/"configs/example.json"), "target":"heating_kWh"}}
    data = load_dataset(config, ROOT/"configs")
    assert len(data.series) == 13 and len(data.observations) == 156
    assert len({v["zone_id"] for v in data.series.values() if v["building_id"] == "1" and "zone_id" in v}) == 2
    original = pd.read_csv(directory/"monthly.csv")
    assert data.observations.energy_kWh.sum() == pytest.approx(original.heating_kWh.sum())
