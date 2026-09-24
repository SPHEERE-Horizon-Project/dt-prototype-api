from __future__ import annotations

import csv

import pytest

from dt_prototype.integration.comparison import verify_zonal_energy_aggregation
from dt_prototype.integration.engines import (
    Model3Engine,
    Model3Request,
    SemiStationaryEngine,
    SemiStationaryRequest,
)
from dt_prototype.integration.project_paths import model3_pipeline_root


def test_model3_adapter_preserves_legacy_monthly_values(project_root) -> None:
    model_root = model3_pipeline_root()
    result = Model3Engine().simulate(
        Model3Request(
            run_id="test-model3-adapter",
            data_dir=model_root / "example_data",
            building_id="B001",
            scenario_id="S00",
            weather_id="model3-example-weather",
        )
    )
    assert len(result.records) == 12
    assert result.metadata["equations_modified_by_adapter"] is False
    assert result.metadata["source_module"] == str((model_root / "model3.py").resolve())
    with (model_root / "reference_outputs" / "forward_monthly.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        golden = list(csv.DictReader(handle))
    for mapped, expected in zip(result.records, golden):
        assert mapped.period_id == expected["period_id"]
        assert mapped.H_total_W_K == pytest.approx(float(expected["H_total_W_K"]))
        assert mapped.useful_heating_kWh == pytest.approx(
            float(expected["useful_heating_kWh"])
        )
        assert mapped.useful_cooling_kWh == pytest.approx(
            float(expected["useful_cooling_kWh"])
        )


def test_reference_adapter_single_zone(reference_district) -> None:
    building = next(item for item in reference_district.buildings if item.name == "Test building 5")
    result = SemiStationaryEngine().simulate(
        SemiStationaryRequest(
            run_id="test-reference-single",
            building_id=building.geometry.building_id,
            scenario_id="baseline",
            weather_id="venezia_161050",
            building=building,
            weather=reference_district.weather,
        )
    )
    assert len(result.records) == 12
    assert {record.zone_id for record in result.records} == {None}
    assert sum(record.useful_heating_kWh for record in result.records) / 1000.0 == pytest.approx(
        2931.188, abs=0.002
    )
    assert sum(record.useful_cooling_kWh for record in result.records) / 1000.0 == pytest.approx(
        269.089, abs=0.002
    )
    assert all(record.time_constant_h is not None for record in result.records)
    assert result.metadata["reference_engine"] is True
    assert result.metadata["equations_modified_by_adapter"] is False


def test_reference_adapter_two_zone_and_aggregation(reference_district) -> None:
    building = next(item for item in reference_district.buildings if item.name == "Test building 1")
    result = SemiStationaryEngine().simulate(
        SemiStationaryRequest(
            run_id="test-reference-two-zone",
            building_id=building.geometry.building_id,
            scenario_id="baseline",
            weather_id="venezia_161050",
            building=building,
            weather=reference_district.weather,
            include_zone_results=True,
        )
    )
    assert len(result.records) == 36
    assert {record.zone_id for record in result.records} == {None, "upper", "lower"}
    aggregate = [record for record in result.records if record.zone_id is None]
    assert sum(record.useful_heating_kWh for record in aggregate) / 1000.0 == pytest.approx(
        320.081, abs=0.002
    )
    assert sum(record.useful_cooling_kWh for record in aggregate) / 1000.0 == pytest.approx(
        72.104, abs=0.002
    )
    assert all(record.time_constant_h is None for record in aggregate)
    assert all(
        record.time_constant_h is not None
        for record in result.records
        if record.zone_id is not None
    )
    diagnostics = verify_zonal_energy_aggregation(result)
    assert len(diagnostics) == 12 * 6
    assert {diagnostic.status for diagnostic in diagnostics} == {"PASS"}
