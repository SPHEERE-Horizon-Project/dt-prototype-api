from __future__ import annotations

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


def test_single_and_two_zone_reference_to_model3_comparison(
    project_root, reference_district, tmp_path
) -> None:
    building = next(item for item in reference_district.buildings if item.name == "Test building 1")
    run_id = "cross-engine-building_1"
    building_id = building.geometry.building_id
    scenario_id = "baseline"
    weather_id = "venezia_161050"
    reference = SemiStationaryEngine().simulate(
        SemiStationaryRequest(
            run_id=run_id,
            building_id=building_id,
            scenario_id=scenario_id,
            weather_id=weather_id,
            building=building,
            weather=reference_district.weather,
            include_zone_results=True,
        )
    )

    mapped_results = []
    mapped_warnings = []
    manifests = []
    for label, zone_id in (("aggregate", None), ("upper", "upper"), ("lower", "lower")):
        mapped = write_reference_case_as_model3_inputs(
            tmp_path / label,
            reference_results=reference,
            reference_building=building,
            reference_weather=reference_district.weather,
            run_id=run_id,
            scenario_id=scenario_id,
            weather_id=weather_id,
            zone_id=zone_id,
        )
        result = Model3Engine().simulate(mapped.request)
        mapped_results.extend(result.records)
        mapped_warnings.extend(result.warnings)
        manifests.append(mapped.manifest)

    model3 = MonthlyPhysicsResults(
        engine_id="model3_legacy",
        engine_version="3.0.0-legacy",
        records=tuple(mapped_results),
        warnings=tuple(mapped_warnings),
        metadata={"mappings": manifests},
    ).validate()
    rules = (
        ComparisonRule(
            "outdoor_temp_C",
            MappingClassification.EQUIVALENT_AFTER_CONVERSION,
            absolute_tolerance=1e-12,
            comparison_basis="same reference monthly weather",
        ),
        ComparisonRule(
            "H_transmission_W_K",
            MappingClassification.EQUIVALENT_AFTER_CONVERSION,
            absolute_tolerance=1e-8,
            comparison_basis="reference non-ground UA mapped as Model 3 opaque UA",
        ),
        ComparisonRule(
            "H_ground_W_K",
            MappingClassification.EQUIVALENT_AFTER_CONVERSION,
            absolute_tolerance=1e-8,
            comparison_basis="same validated reference 0.7-U ground component",
        ),
        ComparisonRule(
            "total_gain_kWh",
            MappingClassification.EQUIVALENT_AFTER_CONVERSION,
            absolute_tolerance=1e-8,
            comparison_basis="reference total gains prescribed through Model 3 internal-gain channel",
        ),
        ComparisonRule(
            "H_total_W_K",
            MappingClassification.APPROXIMATE,
            comparison_basis="reference monthly air exchange mapped to Model 3 annual mean",
        ),
        ComparisonRule(
            "thermal_capacity_J_K",
            MappingClassification.APPROXIMATE,
            comparison_basis="reference layer capacity mapped to nearest Model 3 mass class",
        ),
        ComparisonRule(
            "useful_heating_kWh",
            MappingClassification.APPROXIMATE,
            comparison_basis="schedule and independent-zone representations differ",
        ),
    )
    diagnostics = compare_monthly_results(model3, reference, rules)
    assert len(diagnostics) == 36 * len(rules)
    exact = [
        item
        for item in diagnostics
        if item.mapping_classification
        == MappingClassification.EQUIVALENT_AFTER_CONVERSION
    ]
    assert exact
    assert {item.status for item in exact} == {"PASS"}
    approximate = [
        item
        for item in diagnostics
        if item.mapping_classification == MappingClassification.APPROXIMATE
    ]
    assert {item.status for item in approximate} == {"REVIEW"}
    assert any(
        "two_zone_to_single_zone" in manifest["approximate_mappings"]
        for manifest in manifests
    )
