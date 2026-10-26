from __future__ import annotations

import json
import math

import pandas as pd
import pytest

from dt_prototype.assessment.contract import AssessmentInputError, REQUIRED_COLUMNS, validate_asset_results
from dt_prototype.assessment.workflow import aggregate_assets, run_assessment


def _row(**updates):
    row = {
        "assessment_id": "retrofit-a", "building_id": "B1", "asset_id": "hp-system",
        "category_id": "technical_system.heat_pump_group", "asset_name": "Heat pump system",
        "building_layer": "technical_system", "scope_action": "installed",
        "base_quantity": 3.0, "sizing_factor": 1.0, "assessed_quantity": 3.0,
        "quantity_unit": "unit", "sizing_basis": "three heat pumps in the system",
        "module": "LCC", "metric_id": "global_cost", "life_cycle_stage": "whole_life",
        "value": 90000.0, "unit": "EUR", "value_basis": "full_study_period",
        "study_period_years": 30.0, "currency": "EUR", "price_year": 2026.0,
        "mass_kg": "", "status": "complete", "source": "external workbook v1",
    }
    row.update(updates)
    return row


def _frame(rows):
    return pd.DataFrame(rows, columns=REQUIRED_COLUMNS)


def test_additive_results_and_mci_are_aggregated_at_building_level():
    rows = [
        _row(),
        _row(asset_id="dhw-hp", category_id="technical_system.heat_pump.dhw", asset_name="DHW heat pump",
             base_quantity=20.0, assessed_quantity=20.0, quantity_unit="kW",
             sizing_basis="dedicated DHW heat-pump capacity", value=20000.0),
        _row(module="MCI", metric_id="mci", life_cycle_stage="current_asset", value=0.8,
             unit="1", value_basis="current_asset", study_period_years="", currency="", price_year="", mass_kg=1000.0),
        _row(asset_id="dhw-hp", category_id="technical_system.heat_pump.dhw", asset_name="DHW heat pump",
             base_quantity=20.0, assessed_quantity=20.0, quantity_unit="kW",
             sizing_basis="dedicated DHW heat-pump capacity", module="MCI", metric_id="mci",
             life_cycle_stage="current_asset", value=0.5, unit="1", value_basis="current_asset",
             study_period_years="", currency="", price_year="", mass_kg=500.0),
    ]
    aggregate = aggregate_assets(validate_asset_results(_frame(rows)))
    lcc = aggregate[aggregate.module == "LCC"].iloc[0]
    mci = aggregate[aggregate.module == "MCI"].iloc[0]
    assert lcc.value == pytest.approx(110000.0)
    assert mci.value == pytest.approx((0.8 * 1000 + 0.5 * 500) / 1500)
    assert mci.mass_kg == pytest.approx(1500.0)


def test_sizing_mismatch_is_rejected():
    with pytest.raises(AssessmentInputError, match=r"base_quantity \* sizing_factor"):
        validate_asset_results(_frame([_row(sizing_factor=1.2, assessed_quantity=3.0)]))
    with pytest.raises(AssessmentInputError, match="base_quantity is not numeric"):
        validate_asset_results(_frame([_row(base_quantity="three")]))


def test_missing_result_is_not_converted_to_zero():
    rows = [_row(), _row(asset_id="water-tank", category_id="technical_system.water_tank",
                         asset_name="Water tank", value="", status="missing")]
    aggregate = aggregate_assets(validate_asset_results(_frame(rows))).iloc[0]
    assert aggregate.status == "missing"
    assert math.isnan(aggregate.value)


def test_workflow_keeps_static_assets_separate_from_solver_cases(tmp_path):
    asset_csv = tmp_path / "assets.csv"
    _frame([_row()]).to_csv(asset_csv, index=False)
    energy_dir = tmp_path / "energy"
    energy_dir.mkdir()
    energy = pd.DataFrame([
        {"building_id": "B1", "building_name": "Building 1", "year": 2026,
         "model": "Monthly_SS", "representation": "collapsed", "resolution": "monthly",
         "grid_import_kWh": 100, "grid_export_kWh": 5, "pv_self_consumed_kWh": 20,
         "import_primary_nonrenewable_kWh": 200, "import_primary_renewable_kWh": 40,
         "net_primary_total_kWh": 230, "import_carbon_kgCO2e": 25,
         "export_carbon_kgCO2e": 1, "net_carbon_kgCO2e": 24,
         "import_energy_cost": 30, "export_energy_credit": 2, "net_energy_cost": 28},
        {"building_id": "B1", "building_name": "Building 1", "year": 2026,
         "model": "Monthly_SS_VBDD", "representation": "collapsed", "resolution": "monthly",
         "grid_import_kWh": 101, "grid_export_kWh": 4, "pv_self_consumed_kWh": 19,
         "import_primary_nonrenewable_kWh": 202, "import_primary_renewable_kWh": 40.4,
         "net_primary_total_kWh": 234, "import_carbon_kgCO2e": 25.25,
         "export_carbon_kgCO2e": 0.8, "net_carbon_kgCO2e": 24.45,
         "import_energy_cost": 30.3, "export_energy_credit": 1.6, "net_energy_cost": 28.7},
    ])
    energy.to_csv(energy_dir / "energy_annual.csv", index=False)
    (energy_dir / "energy_config_resolved.json").write_text(json.dumps({"currency": "EUR"}), encoding="utf-8")

    out = run_assessment(asset_csv, tmp_path / "out", energy_dir)
    static = pd.read_csv(out / "building_asset_results.csv")
    operational = pd.read_csv(out / "building_operational_results.csv")
    assert len(static) == 1
    assert len(operational) == 2 * 12
    assert set(operational.model) == {"Monthly_SS", "Monthly_SS_VBDD"}
    assert set(operational[operational.metric_id == "net_energy_cost"].unit) == {"EUR/year"}


@pytest.mark.parametrize("column,value", [
    ("asset_id", None), ("building_id", float("nan")), ("source", pd.NA),
    ("base_quantity", True), ("study_period_years", float("inf")),
    ("mass_kg", float("inf")), ("mass_kg", -1), ("price_year", ""),
    ("price_year", 2026.5), ("unit", "USD"), ("currency", None),
])
def test_invalid_assessment_metadata_fails(column, value):
    with pytest.raises(AssessmentInputError):
        validate_asset_results(_frame([_row(**{column: value})]))


def test_inconsistent_study_horizons_across_metrics_fail():
    with pytest.raises(AssessmentInputError, match="study_period_years must agree"):
        validate_asset_results(_frame([_row(), _row(metric_id="initial_cost", study_period_years=20)]))


def test_duplicate_mci_stages_cannot_double_count_an_asset():
    row = _row(module="MCI", metric_id="mci", value=0.8, unit="1",
               value_basis="current_asset", mass_kg=200)
    with pytest.raises(AssessmentInputError, match="one current-asset MCI"):
        validate_asset_results(_frame([row, dict(row, life_cycle_stage="another_stage")]))


def test_sizing_overflow_is_not_a_valid_comparison():
    with pytest.raises(AssessmentInputError, match="must be finite"):
        validate_asset_results(_frame([_row(base_quantity=1e300, sizing_factor=1e300)]))


def test_all_not_applicable_stays_not_applicable():
    result = aggregate_assets(_frame([_row(status="not_applicable", value="")])).iloc[0]
    assert result.status == "not_applicable"
    assert math.isnan(result.value)


def _write_energy_input(directory, building_id="001", duplicate=False):
    from dt_prototype.assessment.workflow import OPERATIONAL_METRICS
    directory.mkdir()
    row = dict(building_id=building_id, building_name="Building", year=2023,
               model="Monthly_SS", representation="native_single_zone", resolution="monthly")
    row.update({column: 0.0 for column in OPERATIONAL_METRICS})
    pd.DataFrame([row, row] if duplicate else [row]).to_csv(directory / "energy_annual.csv", index=False)
    (directory / "energy_config_resolved.json").write_text(json.dumps({"currency": "EUR"}), encoding="utf-8")


def test_operational_join_preserves_leading_zero_ids(tmp_path):
    asset_csv = tmp_path / "assets.csv"
    _frame([_row(building_id="001")]).to_csv(asset_csv, index=False)
    _write_energy_input(tmp_path / "energy")
    out = run_assessment(asset_csv, tmp_path / "out", tmp_path / "energy")
    result = pd.read_csv(out / "building_operational_results.csv", dtype={"building_id": str})
    assert set(result.building_id) == {"001"}
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["energy_config_sha256"]
    assert manifest["code_hashes"]


def test_duplicate_operational_cases_fail_with_diagnostic_manifest(tmp_path):
    asset_csv = tmp_path / "assets.csv"
    _frame([_row(building_id="001")]).to_csv(asset_csv, index=False)
    _write_energy_input(tmp_path / "energy", duplicate=True)
    with pytest.raises(AssessmentInputError, match="duplicate annual"):
        run_assessment(asset_csv, tmp_path / "out", tmp_path / "energy")
    manifest = json.loads((tmp_path / "out/manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert "duplicate annual" in manifest["error"]


@pytest.mark.parametrize("defect", ["missing_currency", "failed_source"])
def test_operational_source_provenance_is_required(tmp_path, defect):
    asset_csv = tmp_path / "assets.csv"
    _frame([_row(building_id="001")]).to_csv(asset_csv, index=False)
    _write_energy_input(tmp_path / "energy")
    if defect == "missing_currency":
        (tmp_path / "energy/energy_config_resolved.json").unlink()
    else:
        (tmp_path / "energy/manifest.json").write_text('{"status":"failed"}')
    with pytest.raises(AssessmentInputError):
        run_assessment(asset_csv, tmp_path / "out", tmp_path / "energy")
