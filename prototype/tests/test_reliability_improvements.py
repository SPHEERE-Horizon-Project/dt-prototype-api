"""Executable input contracts, synthetic measured-format acceptance and worker fix."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd
import pytest
from jsonschema import Draft202012Validator

from dt_prototype.validation import preflight, schema_errors, SCHEMAS
from dt_prototype.inverse_models.acceptance import assess_run, load_policy
from dt_prototype.inverse_models.data import load_json
from dt_prototype.inverse_models.workflow import run_inverse

ROOT = Path(__file__).resolve().parents[1]
WORKER = Path(os.environ.get("DT_OPENDSM_PYTHON", ROOT/".venv-opendsm/Scripts/python.exe"))


def write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def inverse_config():
    config = load_json(ROOT/"configs/inverse_5p_example.json")
    for key in ["observations", "weather"]:
        config["source"][key] = str((ROOT/"configs"/config["source"][key]).resolve())
    return config


def test_generated_schemas_are_valid_and_match_the_generator():
    spec = importlib.util.spec_from_file_location("builder", ROOT/"scripts/build_input_schemas.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in module.rendered().items():
        Draft202012Validator.check_schema(value)
        assert load_json(SCHEMAS/f"{name}.schema.json") == value


@pytest.mark.parametrize("pattern,kind", [("archetypes*.json", "envelopes"), ("schedules*.json", "schedules"),
                                          ("systems_templates.json", "systems")])
def test_supplied_libraries_match_versioned_contracts(pattern, kind):
    for path in (ROOT/"data/examples").glob(pattern):
        assert not schema_errors(load_json(path), kind), path


@pytest.mark.parametrize("file,kind", [("example.json", "project"), ("example_tabular.json", "project"),
    ("energy_example.json", "energy"), ("pipeline_example.json", "pipeline"),
    ("pipeline_assessment_example.json", "pipeline"), ("pipeline_inverse_example.json", "pipeline"),
    ("inverse_synthetic_example.json", "inverse"), ("inverse_measured_template.json", "inverse")])
def test_configuration_contract_examples(file, kind):
    assert not schema_errors(load_json(ROOT/"configs"/file), kind)


def test_preflight_forward_reads_inputs_without_solving(monkeypatch):
    monkeypatch.setattr("dt_prototype.pipeline.run_pipeline", lambda *a, **k: pytest.fail("solver invoked"))
    result = preflight(ROOT/"configs/pipeline_example.json")
    assert result["status"] == "passed", result
    assert any(c["check"] == "building coverage" for c in result["checks"])


def test_preflight_consolidates_independent_failures(tmp_path):
    config = load_json(ROOT/"configs/example.json")
    config["inputs"].update(envelopes="missing-envelope.json", schedules="missing-schedules.json", systems="missing-systems.json")
    config["dynamic"].update(typo=True)
    result = preflight(write(tmp_path/"project.json", config), "project")
    assert result["status"] == "failed"
    assert result["failed_checks"] >= 4


def test_preflight_inverse_does_not_fit_and_validates_saved_domains(tmp_path, monkeypatch):
    config = inverse_config()
    monkeypatch.setattr("dt_prototype.inverse_models.workflow.run_inverse", lambda *a, **k: pytest.fail("fitting invoked"))
    assert preflight(write(tmp_path/"good.json", config), "inverse")["status"] == "passed"
    config["models"] = [{"backend": "5p_monthly", "options": {"fit": {"change_point_step_C": -1}}}]
    assert preflight(write(tmp_path/"bad.json", config), "inverse")["status"] == "failed"


@pytest.mark.parametrize("bad", [None, [], {"source": None}, {"schema_version": "1.0", "source": {"type": "csv"}}])
def test_preflight_malformed_input_is_a_report_not_a_traceback(tmp_path, bad):
    assert preflight(write(tmp_path/"bad.json", bad), "inverse")["status"] == "failed"


def test_row_schema_rejects_wrong_units_field_negative_values_and_unknown_flags():
    row = dict(series_id="001/import", interval_start="2023-01-01", interval_end="2023-02-01", energy_kWh=2)
    assert not schema_errors(row, "observations-row")
    assert schema_errors({**row, "energy_kWh": -1}, "observations-row")
    assert schema_errors({**row, "energy_kW": 2}, "observations-row")
    assert schema_errors({**row, "quality": "guessed"}, "observations-row")


@pytest.fixture(scope="module")
def synthetic_run(tmp_path_factory):
    folder = tmp_path_factory.mktemp("acceptance")
    config = inverse_config()
    return run_inverse(write(folder/"fit.json", config), folder/"fit")


def test_synthetic_fixture_never_claims_empirical_validation(synthetic_run):
    result = assess_run(synthetic_run, ROOT/"configs/measured_acceptance_policy.json")
    assert result["status"] == "review_required"
    assert all(any("cannot establish empirical" in reason for reason in r["reasons"]) for r in result["models"])


def test_acceptance_rejects_prediction_label_tampering(synthetic_run, tmp_path):
    import shutil
    target = tmp_path/"copy"
    shutil.copytree(synthetic_run, target)
    path = target/"predictions.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "split"] = "validation"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="split differs"):
        assess_run(target, ROOT/"configs/measured_acceptance_policy.json")


def test_synthetic_measured_format_acceptance_path_and_missing_holdout(tmp_path):
    # This exercises the declaration contract only; it is NOT empirical evidence.
    config = inverse_config()
    for metadata in config["source"]["series"].values():
        metadata.update(source_type="measured", source_id="SYNTHETIC_UNIT_TEST_ONLY")
    run = run_inverse(write(tmp_path/"input.json", config), tmp_path/"fit")
    policy = load_json(ROOT/"configs/measured_acceptance_policy.json")
    policy.update(maximum_abs_NMBE_pct=100, maximum_CV_RMSE_pct={k: 100 for k in policy["maximum_CV_RMSE_pct"]})
    path = write(tmp_path/"policy.json", policy)
    assert assess_run(run, path)["status"] == "accepted"
    predictions = pd.read_csv(run/"predictions.csv")
    predictions.loc[predictions.split.eq("validation"), "predicted_energy_kWh"] = np.nan
    predictions.to_csv(run/"predictions.csv", index=False)
    result = assess_run(run, path)
    assert result["status"] == "review_required"
    assert "holdout coverage_fraction outside policy or undefined" in result["models"][0]["reasons"]


@pytest.mark.parametrize("field,value", [("holdout_split", "train"), ("minimum_prediction_coverage", 1.2),
    ("minimum_holdout_observations", 3.5), ("require_native_qualification", "true")])
def test_acceptance_policy_domains(tmp_path, field, value):
    policy = load_json(ROOT/"configs/measured_acceptance_policy.json")
    policy[field] = value
    with pytest.raises(ValueError):
        load_policy(write(tmp_path/"policy.json", policy))


def test_zero_skips_release_gate(tmp_path):
    from scripts.check_test_evidence import check
    path = tmp_path/"tests.xml"
    path.write_text('<testsuites><testsuite tests="2" failures="0" errors="0" skipped="1"/></testsuites>')
    with pytest.raises(ValueError, match="zero failures/errors/skips"):
        check(path)


@pytest.mark.opendsm
def test_real_zero_coefficient_metrics_preserve_count_and_restore_binding():
    assert WORKER.is_file(), "Full validation requires DT_OPENDSM_PYTHON or .venv-opendsm"
    result = subprocess.run([str(WORKER), str(ROOT/"tests/inverse_models/worker_compatibility_checks.py")],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout+result.stderr


@pytest.mark.opendsm
def test_previous_hourly_failure_fit_reload_and_qualification(tmp_path):
    assert WORKER.is_file(), "Full validation requires the worker"
    fixture = ROOT/"tests/fixtures/hourly_zero_coefficients"
    config = load_json(fixture/"config.json")
    for key in ["observations", "weather"]:
        config["source"][key] = str(fixture/config["source"][key])
    config["opendsm_python"] = str(WORKER)
    config["models"] = [{"backend": "opendsm_hourly", "options": {"allow_disqualified": True}}]
    run = run_inverse(write(tmp_path/"fit.json", config), tmp_path/"fit")
    manifest = load_json(run/"manifest.json")
    assert manifest["status"] == "complete", manifest
    model = manifest["models"][0]
    assert model["compatibility"]["zero_parameter_metric_calls"] > 0
    assert "HOURLY_ZERO_COEFFICIENT_METRICS_COMPATIBILITY" in model["warnings"]
    assert model["qualification"] == "review"
    config.update(operation="predict", model_dir=str(run))
    reload = run_inverse(write(tmp_path/"predict.json", config), tmp_path/"predict")
    assert load_json(reload/"manifest.json")["status"] == "complete"
    a, b = pd.read_csv(run/"predictions.csv"), pd.read_csv(reload/"predictions.csv")
    np.testing.assert_allclose(a.predicted_energy_kWh, b.predicted_energy_kWh, rtol=1e-12, atol=1e-10)
    np.testing.assert_allclose(a.native_uncertainty, b.native_uncertainty, rtol=1e-12, atol=1e-10, equal_nan=True)
