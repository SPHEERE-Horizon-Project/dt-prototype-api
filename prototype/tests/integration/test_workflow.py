from __future__ import annotations

import json

import pandas as pd
import pytest

from dt_prototype.integration.energy_signature import (
    build_five_parameter_report_from_reference_run,
)
from dt_prototype.integration.workflow import run_supplied_reference_comparison


def test_supplied_reference_workflow_is_traceable_and_immutable(
    project_root, tmp_path
) -> None:
    run_id = "test-supplied-reference"
    run_dir = run_supplied_reference_comparison(project_root, tmp_path, run_id)
    assert run_dir == tmp_path / run_id
    expected = {
        "manifest.json",
        "physics_full_monthly.csv",
        "physics_model3_comparison_monthly.csv",
        "cross_model_diagnostics.csv",
        "warnings.csv",
    }
    assert expected.issubset({path.name for path in run_dir.iterdir()})
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["comparison_counts"]["buildings"] == 5
    assert manifest["comparison_counts"]["equivalent_fail"] == 0
    assert manifest["comparison_cases"]["individual_zones"] is True
    assert manifest["comparison_cases"]["reference_dynamic_rerun_required"] is False

    full = pd.read_csv(run_dir / "physics_full_monthly.csv")
    assert len(full) == 5 * 12 + 4 * 2 * 12
    assert {"upper", "lower"}.issubset(set(full["zone_id"].dropna()))
    diagnostics = pd.read_csv(run_dir / "cross_model_diagnostics.csv")
    assert {"PASS", "REVIEW"}.issubset(set(diagnostics["status"]))
    assert "MISSING_QUANTITY" not in set(diagnostics["status"])
    assert "NOT_COMPARABLE" in set(diagnostics["status"])
    with pytest.raises(FileExistsError):
        run_supplied_reference_comparison(project_root, tmp_path, run_id)


def test_seasonal_ahu_mode_reports_separate_coil_and_preserves_totals(
    project_root, tmp_path
) -> None:
    run_dir = run_supplied_reference_comparison(
        project_root,
        tmp_path,
        "seasonal-ahu",
        comparison_mode="seasonal_ahu",
    )
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["comparison_mode"] == "seasonal_ahu"
    assert manifest["comparison_cases"]["seasonal_mask_enabled"] is True
    assert manifest["comparison_cases"]["separate_ahu_enabled"] is True

    model3 = pd.read_csv(run_dir / "physics_model3_comparison_monthly.csv")
    lower_food = model3[(model3["building_id"] == 1) & (model3["zone_id"] == "lower")]
    assert lower_food["ahu_sensible_heating_kWh"].sum() > 0.0
    assert lower_food["ahu_sensible_cooling_kWh"].sum() > 0.0
    assert (
        lower_food["useful_heating_kWh"]
        - lower_food["zone_sensible_heating_kWh"]
        - lower_food["ahu_sensible_heating_kWh"]
    ).abs().max() < 1e-8
    may = lower_food[lower_food["period_id"] == "2023-05"].iloc[0]
    assert may["zone_sensible_cooling_kWh"] == pytest.approx(0.0)
    assert "zone_plus_separate_ahu" in may["calculation_boundary_id"]

    reference = pd.read_csv(run_dir / "physics_full_monthly.csv")
    for building_id in (1, 18, 19):
        ref_cooling = reference[
            (reference["building_id"] == building_id)
            & (reference["zone_id"] == "lower")
        ]["useful_cooling_kWh"].sum()
        model_cooling = model3[
            (model3["building_id"] == building_id)
            & (model3["zone_id"] == "lower")
        ]["useful_cooling_kWh"].sum()
        assert abs(model_cooling - ref_cooling) / ref_cooling < 0.05

    regression_dir = build_five_parameter_report_from_reference_run(
        run_dir, tmp_path, "seasonal-ahu-5p"
    )
    parameters = pd.read_csv(regression_dir / "regression_parameters_metrics.csv")
    assert len(parameters) == 5 * 2
    assert set(parameters["source_id"]) == {"semi_stationary", "model3_legacy"}
    assert parameters["building_id"].nunique() == 5
    assert not parameters["fit_status"].eq("FAILED").any()
    assert len(list((regression_dir / "figures").glob("*.svg"))) == 5
