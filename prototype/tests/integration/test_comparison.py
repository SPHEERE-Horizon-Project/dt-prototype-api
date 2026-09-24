from __future__ import annotations

from dataclasses import replace

from dt_prototype.integration.comparison import (
    ComparisonRule,
    MappingClassification,
    compare_monthly_results,
)
from dt_prototype.integration.schemas import (
    CalculationStatus,
    MonthlyPhysicsRecord,
    MonthlyPhysicsResults,
)


def test_comparison_respects_mapping_classification() -> None:
    left_record = MonthlyPhysicsRecord(
        run_id="comparison-test",
        engine_id="left",
        building_id="B001",
        scenario_id="baseline",
        weather_id="weather",
        period_id="2023-01",
        calculation_boundary_id="matched",
        calculation_status=CalculationStatus.OK,
        useful_heating_kWh=100.0,
        solar_gain_kWh=20.0,
    )
    right_record = replace(
        left_record,
        engine_id="right",
        useful_heating_kWh=100.00001,
        solar_gain_kWh=25.0,
    )
    left = MonthlyPhysicsResults("left", "1", (left_record,)).validate()
    right = MonthlyPhysicsResults("right", "1", (right_record,)).validate()
    diagnostics = compare_monthly_results(
        left,
        right,
        (
            ComparisonRule(
                "useful_heating_kWh",
                MappingClassification.EQUIVALENT,
                absolute_tolerance=1e-3,
                comparison_basis="controlled identical boundary",
            ),
            ComparisonRule(
                "solar_gain_kWh",
                MappingClassification.DELIBERATELY_DIFFERENT,
                comparison_basis="reference includes opaque/long-wave terms",
            ),
        ),
    )
    assert [item.status for item in diagnostics] == ["PASS", "INFORMATIONAL"]
