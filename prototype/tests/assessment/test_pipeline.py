"""Pipeline behavior and contract tests; thermal calculations are not duplicated."""
import csv
import json
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

from dt_prototype import pipeline
from dt_prototype.assessment.contract import AssessmentInputError, load_asset_results
from dt_prototype.assessment.quantities import resolve_quantities
from dt_prototype.assessment.workflow import OPERATIONAL_METRICS, run_assessment
from dt_prototype.energy_carriers.config import EnergyConfig
from dt_prototype.common.project import ProjectInputs

ROOT = Path(__file__).resolve().parents[2]


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def case(tmp_path):
    energy = tmp_path / "prior_energy"
    energy.mkdir()
    config = EnergyConfig.load(ROOT / "configs/energy_example.json")
    (energy / "energy_config_resolved.json").write_text(json.dumps(config.data))
    manifest = {"status": "complete", "input_hashes": ProjectInputs.load(ROOT / "configs/example.json").hashes(),
                "energy_config_sha256": config.sha256, "code_hashes": pipeline._simulation_code_hashes()}
    (energy / "manifest.json").write_text(json.dumps(manifest))
    rows = []
    for bid in ["1", "18", "19", "20", "21"]:
        for model in ["Monthly_SS", "Monthly_SS_VBDD"]:
            row = dict(building_id=bid, building_name=f"Building {bid}", year=2023,
                       model=model, representation="collapsed", resolution="monthly")
            row.update({key: 1.0 for key in OPERATIONAL_METRICS})
            rows.append(row)
    pd.DataFrame(rows).to_csv(energy / "energy_annual.csv", index=False)
    assets = tmp_path / "assets.csv"
    assets.write_bytes((ROOT / "configs/pipeline_assets_example.csv").read_bytes())
    quantities = tmp_path / "quantities.csv"
    quantities.write_bytes((ROOT / "configs/pipeline_quantities_example.csv").read_bytes())
    data = {"schema_version": "1.0", "project_config": str(ROOT / "configs/example.json"),
            "energy_config": str(ROOT / "configs/energy_example.json"),
            "energy": {"mode": "reuse", "results": str(energy)},
            "assessment": {"enabled": True, "assessment_id": "pipeline-demo",
                           "asset_results": str(assets), "resolved_quantities": str(quantities)}}
    return data, energy, assets, quantities


def _run(tmp_path, data, name="out"):
    config = tmp_path / (name + ".json")
    config.write_text(json.dumps(data))
    out = pipeline.run_pipeline(config, tmp_path / name)
    return out, _read(out / "manifest.json")


def test_default_disabled_ignores_unused_fields_and_does_not_read_assets(case, tmp_path, monkeypatch):
    data, _, _, _ = case
    data["assessment"] = {"asset_results": "nonexistent.csv", "modules": "inactive nonsense", "resolved_quantities": False}
    select = Mock(side_effect=AssertionError("disabled asset stage was invoked"))
    monkeypatch.setattr(pipeline, "_select_assets", select)
    out, manifest = _run(tmp_path, data)
    assert manifest["status"] == "complete"
    assert manifest["stages"]["assessment"]["status"] == "skipped"
    assert not (out / "assessment").exists()
    assert not (out / "inputs").exists()
    select.assert_not_called()


def test_enabled_equals_existing_runner_without_repeating_static_assets(case, tmp_path):
    data, energy, assets, quantities = case
    before = {p.name: pipeline._sha(p) for p in energy.iterdir()}
    out, manifest = _run(tmp_path, data)
    old = run_assessment(assets, tmp_path / "old", energy, quantities)
    for name in ["validated_asset_results.csv", "building_asset_results.csv", "building_operational_results.csv"]:
        pd.testing.assert_frame_equal(pd.read_csv(out / "assessment" / name), pd.read_csv(old / name))
    assert len(pd.read_csv(out / "assessment/building_asset_results.csv")) == 15
    assert len(pd.read_csv(out / "assessment/building_operational_results.csv")) == 120
    assert manifest["status"] == "complete"
    assert manifest["energy_source"]["annual_sha256"]
    assert manifest["assessment_binding"]["quantities_applied_to_simulation"] is False
    assert manifest["coverage"]["scope"].startswith("declared_selected_rows_only")
    assert before == {p.name: pipeline._sha(p) for p in energy.iterdir()}


def test_disabled_module_values_are_not_validated_but_legacy_reader_stays_strict(case, tmp_path):
    data, _, assets, _ = case
    frame = pd.read_csv(assets, dtype=str, keep_default_na=False)
    frame.loc[frame.module == "LCA", "value"] = "not completed yet"
    frame.to_csv(assets, index=False)
    data["assessment"]["modules"] = ["LCC", "MCI"]
    out, manifest = _run(tmp_path, data)
    assert manifest["assessment_binding"]["modules_skipped"] == ["LCA"]
    assert set(pd.read_csv(out / "assessment/building_asset_results.csv").module) == {"LCC", "MCI"}
    with pytest.raises(AssessmentInputError, match="not numeric"):
        load_asset_results(assets)


@pytest.mark.parametrize("defect", ["duplicate_header", "extra_header", "short_row", "unknown_module"])
def test_csv_structure_is_checked_even_for_disabled_modules(case, tmp_path, defect):
    data, _, assets, _ = case
    data["assessment"]["modules"] = ["LCC"]
    with assets.open(newline="") as source:
        rows = list(csv.reader(source))
    if defect == "duplicate_header":
        rows[0][-1] = rows[0][0]
    elif defect == "extra_header":
        rows[0].append("extra")
    elif defect == "short_row":
        rows[2].pop()
    else:
        rows[2][rows[0].index("module")] = "LCAA"
    with assets.open("w", newline="") as target:
        csv.writer(target).writerows(rows)
    with pytest.raises(ValueError):
        _run(tmp_path, data)
    assert _read(tmp_path / "out/manifest.json")["stages"]["energy"]["status"] == "not_run"


def test_missing_selected_module_and_missing_values_are_incomplete_not_zero(case, tmp_path):
    data, _, assets, _ = case
    frame = pd.read_csv(assets, dtype=str, keep_default_na=False)
    frame = frame[~((frame.building_id == "18") & (frame.module == "MCI"))]
    frame.loc[(frame.building_id == "1") & (frame.module == "LCC"), ["status", "value"]] = ["missing", ""]
    frame.to_csv(assets, index=False)
    out, manifest = _run(tmp_path, data)
    assert manifest["status"] == "incomplete"
    assert manifest["stages"]["assessment"]["status"] == "complete"
    assert manifest["coverage"]["missing_requested_modules"] == [{"building_id": "18", "module": "MCI"}]
    result = pd.read_csv(out / "assessment/building_asset_results.csv", dtype={"building_id": str})
    assert result.loc[(result.building_id == "1") & (result.module == "LCC"), "value"].isna().all()


def test_not_applicable_is_preserved(case, tmp_path):
    data, _, assets, _ = case
    frame = pd.read_csv(assets, dtype=str, keep_default_na=False)
    frame.loc[frame.module == "MCI", ["value", "status"]] = ["", "not_applicable"]
    frame.to_csv(assets, index=False)
    _, manifest = _run(tmp_path, data)
    assert manifest["status"] == "complete"
    assert manifest["coverage"]["not_applicable_aggregate_rows"] == 5


@pytest.mark.parametrize("column,value", [("quantity_unit", "unit"), ("assessed_quantity", "43"),
                                          ("category_id", "wrong.category"), ("scope_action", "retained")])
def test_mismatched_inventory_fails_before_energy(case, tmp_path, column, value):
    data, _, _, quantities = case
    frame = pd.read_csv(quantities, dtype=str, keep_default_na=False)
    frame.loc[0, column] = value
    frame.to_csv(quantities, index=False)
    with pytest.raises(AssessmentInputError):
        _run(tmp_path, data)
    assert _read(tmp_path / "out/manifest.json")["stages"]["energy"]["status"] == "not_run"


def test_auto_inventory_can_be_used_without_running_auto_sizing_inside_pipeline(case, tmp_path):
    data, _, _, quantities = case
    inputs = _read(ROOT / "configs/pipeline_quantity_inputs_example.json")
    inputs["default_mode"] = "auto"
    for building in inputs["buildings"]:
        asset = building["assets"][0]
        del asset["direct_quantity"]
        asset.update(rule_id="fixed_estimate", parameters={"estimate": 42})
    resolve_quantities(inputs, _read(ROOT / "configs/asset_catalogue.json")).to_csv(quantities, index=False)
    _, manifest = _run(tmp_path, data)
    assert manifest["status"] == "complete"


@pytest.mark.parametrize("defect", ["project", "configuration", "resolved", "code", "status", "absent_manifest"])
def test_reuse_requires_compatible_completed_source(case, tmp_path, defect):
    data, energy, _, _ = case
    source = _read(energy / "manifest.json")
    if defect == "project":
        source["input_hashes"]["geometry"] = "wrong"
    elif defect == "configuration":
        source["energy_config_sha256"] = "wrong"
    elif defect == "resolved":
        resolved = _read(energy / "energy_config_resolved.json")
        resolved["currency"] = "USD"
        (energy / "energy_config_resolved.json").write_text(json.dumps(resolved))
    elif defect == "code":
        source["code_hashes"]["Monthly_SS/model.py"] = "wrong"
        # Also corrupt a guaranteed existing key.
        source["code_hashes"][next(iter(pipeline._simulation_code_hashes()))] = "wrong"
    elif defect == "status":
        source["status"] = "failed"
    (energy / "manifest.json").write_text(json.dumps(source))
    if defect == "absent_manifest":
        (energy / "manifest.json").unlink()
    with pytest.raises((ValueError, OSError)):
        _run(tmp_path, data)


def test_assessment_failure_keeps_completed_energy(case, tmp_path):
    data, energy, _, _ = case
    frame = pd.read_csv(energy / "energy_annual.csv")
    frame = frame[frame.building_id != 18]
    frame.to_csv(energy / "energy_annual.csv", index=False)
    before = pipeline._sha(energy / "energy_annual.csv")
    with pytest.raises(AssessmentInputError, match="absent from energy"):
        _run(tmp_path, data)
    manifest = _read(tmp_path / "out/manifest.json")
    assert manifest["stages"]["energy"]["status"] == "reused"
    assert manifest["stages"]["assessment"]["status"] == "failed"
    assert _read(energy / "manifest.json")["status"] == "complete"
    assert before == pipeline._sha(energy / "energy_annual.csv")


def test_run_mode_forwards_options_and_uses_pinned_inputs(case, tmp_path, monkeypatch):
    data, energy, assets, _ = case
    data["energy"] = {"mode": "run", "engine": "Monthly_SS_VBDD", "zone_mode": "collapsed",
                      "vb_solar": "temperature_linear", "vb_options": {"utilisation": "fixed", "eta_heating": 0.8}}
    calls = []

    def fake_run(project, config, output, **kwargs):
        calls.append((project, config, output, kwargs))
        assets.write_text("changed externally after preflight")
        return energy

    monkeypatch.setattr("dt_prototype.energy_carriers.workflow.run_project", fake_run)
    _, manifest = _run(tmp_path, data)
    assert manifest["status"] == "complete"
    assert len(calls) == 1
    assert calls[0][3]["engine"] == "Monthly_SS_VBDD"
    assert calls[0][3]["vb_options"].eta_heating == 0.8


@pytest.mark.parametrize("setting,value", [("enabled", "false"), ("modules", []),
                                         ("modules", ["LCC", "LCC"]), ("modules", ["Other"]),
                                         ("assessment_id", "another-scenario")])
def test_invalid_active_assessment_settings_rejected(case, tmp_path, setting, value):
    data, _, _, _ = case
    data["assessment"][setting] = value
    with pytest.raises(ValueError):
        _run(tmp_path, data)


def test_paths_are_relative_to_configuration_and_existing_outputs_refused(case, tmp_path):
    data, energy, assets, quantities = case
    data["energy"]["results"] = energy.name
    data["assessment"]["asset_results"] = assets.name
    data["assessment"]["resolved_quantities"] = quantities.name
    _, manifest = _run(tmp_path, data)
    assert manifest["status"] == "complete"
    with pytest.raises(FileExistsError):
        pipeline.run_pipeline(tmp_path / "out.json", tmp_path / "out")


def test_example_csvs_are_exactly_the_direct_input_inventory():
    expected = resolve_quantities(_read(ROOT / "configs/pipeline_quantity_inputs_example.json"),
                                  _read(ROOT / "configs/asset_catalogue.json"))
    actual = pd.read_csv(ROOT / "configs/pipeline_quantities_example.csv", keep_default_na=False)
    assert list(expected.assessed_quantity) == list(actual.assessed_quantity)
    assert set(actual.quantity_unit) == {"kW"}


@pytest.mark.parametrize("payload", ['{"schema_version":"1.0","schema_version":"1.0"}', '{"schema_version":NaN}'])
def test_ambiguous_json_is_rejected(tmp_path, payload):
    file = tmp_path / "invalid.json"
    file.write_text(payload)
    with pytest.raises(ValueError):
        pipeline.load_configuration(file)


def test_cli_returns_two_for_incomplete_export_and_one_for_failure(case, tmp_path):
    data, _, assets, _ = case
    data["assessment"]["modules"] = ["LCC", "MCI"]
    frame = pd.read_csv(assets, dtype=str, keep_default_na=False)
    frame = frame[frame.module != "MCI"]
    frame.to_csv(assets, index=False)
    config = tmp_path / "cli.json"
    config.write_text(json.dumps(data))
    assert pipeline.main(["--config", str(config), "--output", str(tmp_path / "cli_out")]) == 2
    config.write_text("invalid json")
    with pytest.raises(SystemExit) as error:
        pipeline.main(["--config", str(config), "--output", str(tmp_path / "failed_out")])
    assert error.value.code == 1
