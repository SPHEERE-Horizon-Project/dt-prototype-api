from __future__ import annotations

import pytest

from dt_prototype.integration.comparison import (
    ComparisonRule,
    MappingClassification,
    compare_monthly_results,
)
from dt_prototype.integration.engines import (
    Model3Engine,
    SemiStationaryEngine,
    SemiStationaryRequest,
)
from dt_prototype.integration.mapping import write_reference_case_as_model3_inputs
from dt_prototype.integration.schemas import MonthlyPhysicsResults
from dt_prototype.integration.verification_cases import make_reference_verification_case


@pytest.mark.parametrize(
    "case_id",
    (
        "transmission_only",
        "ventilation_only",
        "infiltration_only",
        "no_temperature_difference",
    ),
)
def test_matched_reference_limiting_cases(project_root, tmp_path, case_id) -> None:
    case = make_reference_verification_case(case_id)
    run_id = f"limiting-{case_id}"
    reference = SemiStationaryEngine().simulate(
        SemiStationaryRequest(
            run_id=run_id,
            building_id=case.case_id,
            scenario_id="baseline",
            weather_id=f"weather-{case_id}",
            building=case.building,
            weather=case.weather,
        )
    )
    mapped = write_reference_case_as_model3_inputs(
        tmp_path / "model3-input",
        reference_results=reference,
        reference_building=case.building,
        reference_weather=case.weather,
        run_id=run_id,
        scenario_id="baseline",
        weather_id=f"weather-{case_id}",
        zone_id=None,
    )
    model3_all = Model3Engine().simulate(mapped.request)
    reference_january = MonthlyPhysicsResults(
        engine_id=reference.engine_id,
        engine_version=reference.engine_version,
        records=tuple(
            row for row in reference.records if row.period_id == case.comparison_month
        ),
        warnings=reference.warnings,
    ).validate()
    legacy_january = MonthlyPhysicsResults(
        engine_id=model3_all.engine_id,
        engine_version=model3_all.engine_version,
        records=tuple(
            row for row in model3_all.records if row.period_id == case.comparison_month
        ),
        warnings=model3_all.warnings,
    ).validate()
    rules = (
        ComparisonRule(
            "H_transmission_W_K",
            MappingClassification.EQUIVALENT_AFTER_CONVERSION,
            absolute_tolerance=1e-9,
            comparison_basis="prescribed matched component",
        ),
        ComparisonRule(
            "H_ground_W_K",
            MappingClassification.EQUIVALENT_AFTER_CONVERSION,
            absolute_tolerance=1e-9,
            comparison_basis="prescribed matched component",
        ),
        ComparisonRule(
            "H_total_W_K",
            MappingClassification.EQUIVALENT_AFTER_CONVERSION,
            absolute_tolerance=1e-9,
            comparison_basis="constant matched transmission/air-exchange boundary",
        ),
        ComparisonRule(
            "total_gain_kWh",
            MappingClassification.EQUIVALENT_AFTER_CONVERSION,
            absolute_tolerance=1e-9,
            comparison_basis="zero prescribed gains",
        ),
        ComparisonRule(
            "useful_heating_kWh",
            MappingClassification.EQUIVALENT_AFTER_CONVERSION,
            absolute_tolerance=1e-8,
            relative_tolerance=1e-12,
            comparison_basis="January has full reference heating availability and identical boundary",
        ),
    )
    diagnostics = compare_monthly_results(legacy_january, reference_january, rules)
    assert {diagnostic.status for diagnostic in diagnostics} == {"PASS"}
    if case_id == "no_temperature_difference":
        reference_value = reference_january.records[0].useful_heating_kWh
        assert reference_value == pytest.approx(0.0, abs=1e-8)
