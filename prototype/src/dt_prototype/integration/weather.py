"""Traceable adaptation of the validated reference EPW preprocessor.

The semi-stationary implementation remains the operational hourly weather
source.  This module adds source hashing, canonical monthly aggregation, and an
independent raw-EPW audit path; it does not duplicate the solar calculations.
"""

from __future__ import annotations

import calendar
import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from dt_prototype.integration.schemas import MonthlyWeatherRecord, records_frame
from dt_prototype.integration.validation import require_valid_collection


AGGREGATION_METHOD = (
    "dt_prototype.monthly.process_epw@1.0.0;"
    "temperature=monthly_arithmetic_mean;"
    "solar=hourly_reference_poa_integral;"
    "azimuths=N0,E90,S180,W270,HOR0_tilt0"
)


def sha256_file(path: str | Path) -> str:
    """Return the lowercase SHA-256 digest of a source file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class PreparedWeather:
    """Canonical monthly weather plus the unchanged reference hourly object."""

    weather_id: str
    monthly_records: tuple[MonthlyWeatherRecord, ...]
    reference_hourly_weather: Any
    metadata: Mapping[str, Any]

    def validate(self) -> "PreparedWeather":
        require_valid_collection(
            self.monthly_records,
            ("weather_id", "period_id"),
            "monthly weather",
        )
        if any(record.weather_id != self.weather_id for record in self.monthly_records):
            raise ValueError("PreparedWeather contains a different weather_id")
        return self

    def to_frame(self) -> pd.DataFrame:
        return records_frame(self.monthly_records)


@dataclass(frozen=True)
class EPWIngestionAudit:
    """Independent raw-field and monthly-aggregation comparison."""

    selected_record_indices: tuple[int, ...]
    selected_records_match: bool
    maximum_temperature_mean_difference_C: float
    maximum_ghi_sum_difference_kWh_m2: float
    raw_row_count: int

    @property
    def passed(self) -> bool:
        return (
            self.raw_row_count == 8760
            and self.selected_records_match
            and self.maximum_temperature_mean_difference_C <= 1e-12
            and self.maximum_ghi_sum_difference_kWh_m2 <= 1e-12
        )


def _monthly_integral_kwh_m2(
    frame: pd.DataFrame, column: str, timestep_hours: float, month: int
) -> float:
    values = frame.loc[frame.index.month == month, column].to_numpy(dtype=float)
    return float(np.nansum(values) * timestep_hours / 1000.0)


def process_epw_to_monthly(
    epw_path: str | Path,
    weather_id: str,
    *,
    year: int = 2023,
    time_steps_per_hour: int = 1,
    azimuth_subdivisions: int = 8,
) -> PreparedWeather:
    """Run the reference preprocessor once and create canonical monthly rows."""

    from dt_prototype.monthly import __version__ as reference_version
    from dt_prototype.common.preprocessing.weather import process_epw

    source = Path(epw_path).resolve()
    source_hash = sha256_file(source)
    weather = process_epw(
        source,
        year=year,
        time_steps_per_hour=time_steps_per_hour,
        azimuth_subdivisions=azimuth_subdivisions,
    )
    frame = weather.df
    timestep_hours = 1.0 / weather.time_steps_per_hour
    orientation_columns = {
        "N": weather.irradiance_columns(0.0, 90.0)[0],
        "E": weather.irradiance_columns(90.0, 90.0)[0],
        "S": weather.irradiance_columns(180.0, 90.0)[0],
        "W": weather.irradiance_columns(270.0, 90.0)[0],
        "HOR": weather.irradiance_columns(0.0, 0.0)[0],
    }
    required_for_valid_hour = [
        "temp_air",
        "ghi",
        "dni",
        "dhi",
        *orientation_columns.values(),
    ]

    records: list[MonthlyWeatherRecord] = []
    for month in range(1, 13):
        monthly = frame.loc[frame.index.month == month]
        valid = monthly[required_for_valid_hour].notna().all(axis=1)
        hours_valid = float(valid.sum() * timestep_hours)
        days = calendar.monthrange(year, month)[1]
        expected_hours = days * 24.0
        quality = "good" if abs(hours_valid - expected_hours) <= 1e-9 else "incomplete"
        records.append(
            MonthlyWeatherRecord(
                weather_id=weather_id,
                period_id=f"{year:04d}-{month:02d}",
                days=days,
                hours_valid=hours_valid,
                outdoor_temp_C=float(monthly["temp_air"].mean()),
                solar_N_kWh_m2=_monthly_integral_kwh_m2(
                    frame, orientation_columns["N"], timestep_hours, month
                ),
                solar_E_kWh_m2=_monthly_integral_kwh_m2(
                    frame, orientation_columns["E"], timestep_hours, month
                ),
                solar_S_kWh_m2=_monthly_integral_kwh_m2(
                    frame, orientation_columns["S"], timestep_hours, month
                ),
                solar_W_kWh_m2=_monthly_integral_kwh_m2(
                    frame, orientation_columns["W"], timestep_hours, month
                ),
                solar_HOR_kWh_m2=_monthly_integral_kwh_m2(
                    frame, orientation_columns["HOR"], timestep_hours, month
                ),
                source_epw=str(source),
                source_hash=source_hash,
                timezone=float(weather.timezone),
                aggregation_method=AGGREGATION_METHOD,
                data_quality_flag=quality,
            )
        )

    metadata: dict[str, Any] = {
        "reference_preprocessor": "dt_prototype.common.preprocessing.weather.process_epw",
        "reference_engine_version": reference_version,
        "source_epw": str(source),
        "source_hash": source_hash,
        "reference_year": year,
        "location_name": weather.location_name,
        "latitude": float(weather.latitude),
        "longitude": float(weather.longitude),
        "timezone": float(weather.timezone),
        "time_steps_per_hour": int(weather.time_steps_per_hour),
        "azimuth_subdivisions": int(weather.azimuth_subdivisions),
        "solar_position_method": "reference built-in Spencer/NOAA-style implementation",
        "transposition_method": "reference isotropic-sky implementation",
        "ground_albedo": 0.2,
        "epw_hour_assignment": "reference non-leap synthetic year, start-of-interval index",
        "aggregation_method": AGGREGATION_METHOD,
    }
    return PreparedWeather(
        weather_id=weather_id,
        monthly_records=tuple(records),
        reference_hourly_weather=weather,
        metadata=metadata,
    ).validate()


def audit_raw_epw_ingestion(
    epw_path: str | Path,
    reference_hourly_weather: Any,
    *,
    selected_zero_based_indices: tuple[int, ...] = (0, 1000, 8759),
) -> EPWIngestionAudit:
    """Check EPW field positions/monthly aggregates through the stdlib CSV path.

    This deliberately does not verify solar position or transposition; those
    quantities need separate reference cases rather than agreement with the
    same implementation.
    """

    source = Path(epw_path)
    with source.open("r", encoding="latin-1", newline="") as handle:
        rows = list(csv.reader(handle.readlines()[8:]))

    selected_match = True
    frame = reference_hourly_weather.df
    for index in selected_zero_based_indices:
        manual = tuple(float(rows[index][column]) for column in (6, 13, 14, 15))
        reference = tuple(
            float(frame.iloc[index][name]) for name in ("temp_air", "ghi", "dni", "dhi")
        )
        selected_match = selected_match and manual == reference

    temperature_differences: list[float] = []
    ghi_differences: list[float] = []
    for month in range(1, 13):
        manual_month = [row for row in rows if int(row[1]) == month]
        manual_temperature = sum(float(row[6]) for row in manual_month) / len(manual_month)
        manual_ghi = sum(float(row[13]) for row in manual_month) / 1000.0
        reference_month = frame.loc[frame.index.month == month]
        reference_temperature = float(reference_month["temp_air"].mean())
        timestep_hours = 1.0 / reference_hourly_weather.time_steps_per_hour
        reference_ghi = float(reference_month["ghi"].sum()) * timestep_hours / 1000.0
        temperature_differences.append(abs(manual_temperature - reference_temperature))
        ghi_differences.append(abs(manual_ghi - reference_ghi))

    return EPWIngestionAudit(
        selected_record_indices=selected_zero_based_indices,
        selected_records_match=selected_match,
        maximum_temperature_mean_difference_C=max(temperature_differences),
        maximum_ghi_sum_difference_kWh_m2=max(ghi_differences),
        raw_row_count=len(rows),
    )
