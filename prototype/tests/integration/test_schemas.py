from __future__ import annotations

import pandas as pd
import pytest

from dt_prototype.integration.schemas import (
    CalibrationOverrideRecord,
    CalibrationValidationFlag,
    MeteredEnergyRecord,
    MonthlyWeatherRecord,
    SurfaceRecord,
    records_frame,
)
from dt_prototype.integration.validation import (
    ContractValidationError,
    require_valid,
    require_valid_collection,
)


def weather_record(period_id: str = "2023-01") -> MonthlyWeatherRecord:
    return MonthlyWeatherRecord(
        weather_id="weather-test",
        period_id=period_id,
        days=31,
        hours_valid=744.0,
        outdoor_temp_C=5.0,
        solar_N_kWh_m2=20.0,
        solar_E_kWh_m2=30.0,
        solar_S_kWh_m2=50.0,
        solar_W_kWh_m2=30.0,
        solar_HOR_kWh_m2=40.0,
        source_epw="weather.epw",
        source_hash="a" * 64,
        timezone=1.0,
        aggregation_method="test",
        data_quality_flag="good",
    )


def test_weather_schema_and_uniqueness() -> None:
    record = require_valid(weather_record())
    assert record.hours_valid == 744.0
    with pytest.raises(ContractValidationError) as duplicate:
        require_valid_collection(
            (record, record), ("weather_id", "period_id"), "monthly weather"
        )
    assert any(issue.code == "DUPLICATE_KEY" for issue in duplicate.value.issues)


def test_weather_schema_rejects_invalid_period_and_hash() -> None:
    invalid = MonthlyWeatherRecord(
        **{
            **weather_record().__dict__,
            "period_id": "2023-13",
            "source_hash": "not-a-hash",
        }
    )
    with pytest.raises(ContractValidationError) as exc:
        require_valid(invalid)
    assert {issue.code for issue in exc.value.issues} == {
        "INVALID_PERIOD",
        "INVALID_HASH",
    }


def test_missing_meter_value_remains_null_not_zero() -> None:
    row = MeteredEnergyRecord(
        building_id="B001",
        scenario_id="baseline",
        period_id="2023-01",
        carrier="electricity",
        measured_energy_kWh=None,
        calibration_validation_flag=CalibrationValidationFlag.CALIBRATION,
        data_quality_flag="missing",
        meter_boundary_id="whole_building_import",
    )
    require_valid(row)
    frame = records_frame((row,))
    assert pd.isna(frame.loc[0, "measured_energy_kWh"])
    assert frame.loc[0, "calibration_validation_flag"] == "calibration"


def test_surface_requires_consistent_glazing_and_window() -> None:
    surface = SurfaceRecord(
        building_id="B001",
        zone_id="zone",
        surface_id="south-wall",
        surface_type="ExtWall",
        gross_area_m2=10.0,
        glazed_area_m2=12.0,
        azimuth_deg=180.0,
        tilt_deg=90.0,
        construction_id="wall",
        window_id=None,
        boundary_condition="outdoor",
    )
    with pytest.raises(ContractValidationError) as exc:
        require_valid(surface)
    assert {issue.code for issue in exc.value.issues} == {
        "AREA_INCONSISTENT",
        "REQUIRED",
    }


def test_calibration_override_cannot_mutate_outside_declared_bounds() -> None:
    override = CalibrationOverrideRecord(
        run_id="calibration-run",
        building_id="B001",
        scenario_id="baseline",
        parameter_name="infiltration_ach",
        baseline_value=0.3,
        calibrated_value=2.0,
        lower_bound=0.1,
        upper_bound=1.0,
        unit="1/h",
        calibration_data_hash="b" * 64,
    )
    with pytest.raises(ContractValidationError) as exc:
        require_valid(override)
    assert [issue.code for issue in exc.value.issues] == ["OUT_OF_BOUNDS"]
