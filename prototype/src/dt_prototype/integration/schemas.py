"""Canonical, unit-bearing input and monthly-result contracts.

The contracts deliberately separate immutable baseline inputs, scenario
overlays, calibration overlays, meters, and calculated results.  They contain
no heat-balance equations.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Sequence

import pandas as pd

from dt_prototype.integration.validation import (
    ContractValidationError,
    ValidationIssue,
    require_valid_collection,
)


_PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class CalibrationValidationFlag(str, Enum):
    CALIBRATION = "calibration"
    VALIDATION = "validation"
    EXCLUDED = "excluded"


class CalculationStatus(str, Enum):
    OK = "OK"
    WARNING = "WARNING"
    FAILED = "FAILED"


def _required_text(
    value: str, field_name: str, record_key: str
) -> list[ValidationIssue]:
    if isinstance(value, str) and value.strip():
        return []
    return [
        ValidationIssue(
            "REQUIRED", field_name, "must be a non-empty string", record_key
        )
    ]


def _finite_range(
    value: float | None,
    field_name: str,
    record_key: str,
    minimum: float | None = None,
    maximum: float | None = None,
    required: bool = True,
) -> list[ValidationIssue]:
    if value is None:
        return (
            [ValidationIssue("REQUIRED", field_name, "must not be null", record_key)]
            if required
            else []
        )
    if not math.isfinite(value):
        return [ValidationIssue("NON_FINITE", field_name, "must be finite", record_key)]
    issues: list[ValidationIssue] = []
    if minimum is not None and value < minimum:
        issues.append(
            ValidationIssue(
                "OUT_OF_RANGE", field_name, f"must be >= {minimum}", record_key
            )
        )
    if maximum is not None and value > maximum:
        issues.append(
            ValidationIssue(
                "OUT_OF_RANGE", field_name, f"must be <= {maximum}", record_key
            )
        )
    return issues


def _period_issues(period_id: str, record_key: str) -> list[ValidationIssue]:
    if _PERIOD_PATTERN.fullmatch(period_id or ""):
        return []
    return [
        ValidationIssue(
            "INVALID_PERIOD",
            "period_id",
            "must use YYYY-MM with a valid month",
            record_key,
        )
    ]


@dataclass(frozen=True)
class MonthlyWeatherRecord:
    weather_id: str
    period_id: str
    days: int
    hours_valid: float
    outdoor_temp_C: float
    solar_N_kWh_m2: float
    solar_E_kWh_m2: float
    solar_S_kWh_m2: float
    solar_W_kWh_m2: float
    solar_HOR_kWh_m2: float
    source_epw: str
    source_hash: str
    timezone: float
    aggregation_method: str
    data_quality_flag: str

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = f"{self.weather_id}|{self.period_id}"
        issues = _required_text(self.weather_id, "weather_id", key)
        issues += _period_issues(self.period_id, key)
        issues += _finite_range(float(self.days), "days", key, 28, 31)
        issues += _finite_range(self.hours_valid, "hours_valid", key, 0, self.days * 24)
        issues += _finite_range(self.outdoor_temp_C, "outdoor_temp_C", key, -100, 100)
        for name in (
            "solar_N_kWh_m2",
            "solar_E_kWh_m2",
            "solar_S_kWh_m2",
            "solar_W_kWh_m2",
            "solar_HOR_kWh_m2",
        ):
            issues += _finite_range(getattr(self, name), name, key, 0)
        issues += _required_text(self.source_epw, "source_epw", key)
        if not _SHA256_PATTERN.fullmatch(self.source_hash or ""):
            issues.append(
                ValidationIssue(
                    "INVALID_HASH",
                    "source_hash",
                    "must be a 64-character SHA-256 hex digest",
                    key,
                )
            )
        issues += _finite_range(self.timezone, "timezone", key, -14, 14)
        issues += _required_text(self.aggregation_method, "aggregation_method", key)
        issues += _required_text(self.data_quality_flag, "data_quality_flag", key)
        return tuple(issues)


@dataclass(frozen=True)
class BuildingRecord:
    building_id: str
    site_id: str
    building_name: str
    conditioned_floor_area_m2: float
    conditioned_volume_m3: float
    geometry_source: str
    geometry_source_hash: str

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = self.building_id
        issues = _required_text(self.building_id, "building_id", key)
        issues += _required_text(self.site_id, "site_id", key)
        issues += _required_text(self.building_name, "building_name", key)
        issues += _finite_range(
            self.conditioned_floor_area_m2,
            "conditioned_floor_area_m2",
            key,
            minimum=0,
        )
        issues += _finite_range(
            self.conditioned_volume_m3,
            "conditioned_volume_m3",
            key,
            minimum=0,
        )
        issues += _required_text(self.geometry_source, "geometry_source", key)
        if not _SHA256_PATTERN.fullmatch(self.geometry_source_hash or ""):
            issues.append(
                ValidationIssue(
                    "INVALID_HASH",
                    "geometry_source_hash",
                    "must be a 64-character SHA-256 hex digest",
                    key,
                )
            )
        return tuple(issues)


@dataclass(frozen=True)
class ZoneRecord:
    building_id: str
    zone_id: str
    zone_label: str
    end_use: str
    n_floors: int
    conditioned_floor_area_m2: float
    conditioned_volume_m3: float
    interface_boundary: str

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = f"{self.building_id}|{self.zone_id}"
        issues = _required_text(self.building_id, "building_id", key)
        issues += _required_text(self.zone_id, "zone_id", key)
        issues += _required_text(self.zone_label, "zone_label", key)
        issues += _required_text(self.end_use, "end_use", key)
        issues += _finite_range(float(self.n_floors), "n_floors", key, 1)
        issues += _finite_range(
            self.conditioned_floor_area_m2,
            "conditioned_floor_area_m2",
            key,
            minimum=0,
        )
        issues += _finite_range(
            self.conditioned_volume_m3,
            "conditioned_volume_m3",
            key,
            minimum=0,
        )
        issues += _required_text(self.interface_boundary, "interface_boundary", key)
        return tuple(issues)


@dataclass(frozen=True)
class ConstructionRecord:
    construction_id: str
    construction_type: str
    solar_absorptance: float
    source: str
    source_hash: str

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = self.construction_id
        issues = _required_text(self.construction_id, "construction_id", key)
        issues += _required_text(self.construction_type, "construction_type", key)
        issues += _finite_range(
            self.solar_absorptance, "solar_absorptance", key, 0, 1
        )
        issues += _required_text(self.source, "source", key)
        if not _SHA256_PATTERN.fullmatch(self.source_hash or ""):
            issues.append(
                ValidationIssue(
                    "INVALID_HASH",
                    "source_hash",
                    "must be a 64-character SHA-256 hex digest",
                    key,
                )
            )
        return tuple(issues)


@dataclass(frozen=True)
class ConstructionLayerRecord:
    construction_id: str
    layer_index: int
    thickness_m: float
    conductivity_W_mK: float
    density_kg_m3: float
    specific_heat_J_kgK: float

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = f"{self.construction_id}|{self.layer_index}"
        issues = _required_text(self.construction_id, "construction_id", key)
        issues += _finite_range(float(self.layer_index), "layer_index", key, 0)
        for name in (
            "thickness_m",
            "conductivity_W_mK",
            "density_kg_m3",
            "specific_heat_J_kgK",
        ):
            issues += _finite_range(getattr(self, name), name, key, minimum=0)
            if getattr(self, name) == 0:
                issues.append(
                    ValidationIssue(
                        "NON_POSITIVE", name, "must be greater than zero", key
                    )
                )
        return tuple(issues)


@dataclass(frozen=True)
class WindowRecord:
    window_id: str
    u_value_W_m2K: float
    shgc: float
    frame_fraction: float
    shading_coefficient: float
    source: str

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = self.window_id
        issues = _required_text(self.window_id, "window_id", key)
        issues += _finite_range(self.u_value_W_m2K, "u_value_W_m2K", key, 0)
        for name in ("shgc", "frame_fraction", "shading_coefficient"):
            issues += _finite_range(getattr(self, name), name, key, 0, 1)
        issues += _required_text(self.source, "source", key)
        return tuple(issues)


@dataclass(frozen=True)
class SurfaceRecord:
    building_id: str
    zone_id: str
    surface_id: str
    surface_type: str
    gross_area_m2: float
    glazed_area_m2: float
    azimuth_deg: float
    tilt_deg: float
    construction_id: str
    window_id: str | None
    boundary_condition: str

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = f"{self.building_id}|{self.zone_id}|{self.surface_id}"
        issues: list[ValidationIssue] = []
        for name in (
            "building_id",
            "zone_id",
            "surface_id",
            "surface_type",
            "construction_id",
            "boundary_condition",
        ):
            issues += _required_text(getattr(self, name), name, key)
        issues += _finite_range(self.gross_area_m2, "gross_area_m2", key, 0)
        issues += _finite_range(self.glazed_area_m2, "glazed_area_m2", key, 0)
        if self.glazed_area_m2 > self.gross_area_m2:
            issues.append(
                ValidationIssue(
                    "AREA_INCONSISTENT",
                    "glazed_area_m2",
                    "must not exceed gross_area_m2",
                    key,
                )
            )
        issues += _finite_range(self.azimuth_deg, "azimuth_deg", key, 0, 360)
        if self.azimuth_deg == 360:
            issues.append(
                ValidationIssue(
                    "ANGLE_CANONICALIZATION",
                    "azimuth_deg",
                    "use 0 rather than 360 degrees",
                    key,
                )
            )
        issues += _finite_range(self.tilt_deg, "tilt_deg", key, 0, 180)
        if self.glazed_area_m2 > 0 and not (self.window_id or "").strip():
            issues.append(
                ValidationIssue(
                    "REQUIRED",
                    "window_id",
                    "is required when glazed_area_m2 is positive",
                    key,
                )
            )
        return tuple(issues)


@dataclass(frozen=True)
class ScheduleValueRecord:
    schedule_id: str
    timestamp: str
    internal_gain_convective_W_m2: float
    internal_gain_radiative_W_m2: float
    heating_setpoint_C: float
    cooling_setpoint_C: float
    ventilation_ach: float
    infiltration_ach: float
    data_quality_flag: str

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = f"{self.schedule_id}|{self.timestamp}"
        issues = _required_text(self.schedule_id, "schedule_id", key)
        try:
            datetime.fromisoformat(self.timestamp)
        except (TypeError, ValueError):
            issues.append(
                ValidationIssue(
                    "INVALID_TIMESTAMP",
                    "timestamp",
                    "must be an ISO-8601 timestamp",
                    key,
                )
            )
        for name in (
            "internal_gain_convective_W_m2",
            "internal_gain_radiative_W_m2",
            "ventilation_ach",
            "infiltration_ach",
        ):
            issues += _finite_range(getattr(self, name), name, key, 0)
        issues += _finite_range(self.heating_setpoint_C, "heating_setpoint_C", key, -100, 100)
        issues += _finite_range(self.cooling_setpoint_C, "cooling_setpoint_C", key, -100, 100)
        issues += _required_text(self.data_quality_flag, "data_quality_flag", key)
        return tuple(issues)


@dataclass(frozen=True)
class ScenarioOverlayRecord:
    building_id: str
    scenario_id: str
    parameter_name: str
    operation: str
    value: float
    unit: str
    source: str

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = f"{self.building_id}|{self.scenario_id}|{self.parameter_name}"
        issues = _required_text(self.building_id, "building_id", key)
        issues += _required_text(self.scenario_id, "scenario_id", key)
        issues += _required_text(self.parameter_name, "parameter_name", key)
        if self.operation not in {"replace", "multiply", "add"}:
            issues.append(
                ValidationIssue(
                    "INVALID_OPERATION",
                    "operation",
                    "must be replace, multiply, or add",
                    key,
                )
            )
        issues += _finite_range(self.value, "value", key)
        issues += _required_text(self.unit, "unit", key)
        issues += _required_text(self.source, "source", key)
        return tuple(issues)


@dataclass(frozen=True)
class CalibrationOverrideRecord:
    run_id: str
    building_id: str
    scenario_id: str
    parameter_name: str
    baseline_value: float
    calibrated_value: float
    lower_bound: float
    upper_bound: float
    unit: str
    calibration_data_hash: str

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = f"{self.run_id}|{self.building_id}|{self.parameter_name}"
        issues: list[ValidationIssue] = []
        for name in ("run_id", "building_id", "scenario_id", "parameter_name", "unit"):
            issues += _required_text(getattr(self, name), name, key)
        for name in (
            "baseline_value",
            "calibrated_value",
            "lower_bound",
            "upper_bound",
        ):
            issues += _finite_range(getattr(self, name), name, key)
        if self.lower_bound > self.upper_bound:
            issues.append(
                ValidationIssue(
                    "INVALID_BOUNDS",
                    "lower_bound,upper_bound",
                    "lower_bound must not exceed upper_bound",
                    key,
                )
            )
        if not self.lower_bound <= self.calibrated_value <= self.upper_bound:
            issues.append(
                ValidationIssue(
                    "OUT_OF_BOUNDS",
                    "calibrated_value",
                    "must lie within declared bounds",
                    key,
                )
            )
        if not _SHA256_PATTERN.fullmatch(self.calibration_data_hash or ""):
            issues.append(
                ValidationIssue(
                    "INVALID_HASH",
                    "calibration_data_hash",
                    "must be a 64-character SHA-256 hex digest",
                    key,
                )
            )
        return tuple(issues)


@dataclass(frozen=True)
class SystemServiceRecord:
    system_id: str
    service_id: str
    end_use: str
    carrier: str
    efficiency_form: str
    coefficient_c0: float
    coefficient_c1: float = 0.0
    coefficient_c2: float = 0.0
    source: str = ""

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = f"{self.system_id}|{self.service_id}"
        issues = _required_text(self.system_id, "system_id", key)
        issues += _required_text(self.service_id, "service_id", key)
        issues += _required_text(self.end_use, "end_use", key)
        issues += _required_text(self.carrier, "carrier", key)
        if self.efficiency_form not in {"constant", "linear", "quadratic", "piecewise"}:
            issues.append(
                ValidationIssue(
                    "INVALID_EFFICIENCY_FORM",
                    "efficiency_form",
                    "unsupported efficiency/COP form",
                    key,
                )
            )
        for name in ("coefficient_c0", "coefficient_c1", "coefficient_c2"):
            issues += _finite_range(getattr(self, name), name, key)
        issues += _required_text(self.source, "source", key)
        return tuple(issues)


@dataclass(frozen=True)
class CarrierFactorRecord:
    factor_set_id: str
    carrier: str
    primary_energy_factor: float
    carbon_factor_kgCO2e_kWh: float
    geography: str
    year: int
    convention: str
    source: str

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = f"{self.factor_set_id}|{self.carrier}"
        issues: list[ValidationIssue] = []
        for name in (
            "factor_set_id",
            "carrier",
            "geography",
            "convention",
            "source",
        ):
            issues += _required_text(getattr(self, name), name, key)
        issues += _finite_range(
            self.primary_energy_factor, "primary_energy_factor", key, 0
        )
        issues += _finite_range(
            self.carbon_factor_kgCO2e_kWh,
            "carbon_factor_kgCO2e_kWh",
            key,
        )
        issues += _finite_range(float(self.year), "year", key, 1900, 2200)
        return tuple(issues)


@dataclass(frozen=True)
class MeterBoundaryRecord:
    meter_boundary_id: str
    carrier: str
    included_end_uses: tuple[str, ...]
    gross_net_basis: str
    import_export_convention: str
    source: str

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = self.meter_boundary_id
        issues: list[ValidationIssue] = []
        for name in (
            "meter_boundary_id",
            "carrier",
            "gross_net_basis",
            "import_export_convention",
            "source",
        ):
            issues += _required_text(getattr(self, name), name, key)
        if not self.included_end_uses:
            issues.append(
                ValidationIssue(
                    "REQUIRED",
                    "included_end_uses",
                    "must declare at least one included end use",
                    key,
                )
            )
        elif any(not item.strip() for item in self.included_end_uses):
            issues.append(
                ValidationIssue(
                    "INVALID_END_USE",
                    "included_end_uses",
                    "must not contain empty values",
                    key,
                )
            )
        return tuple(issues)


@dataclass(frozen=True)
class MeteredEnergyRecord:
    building_id: str
    scenario_id: str
    period_id: str
    carrier: str
    measured_energy_kWh: float | None
    calibration_validation_flag: CalibrationValidationFlag
    data_quality_flag: str
    meter_boundary_id: str

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = (
            f"{self.building_id}|{self.scenario_id}|{self.period_id}|"
            f"{self.carrier}|{self.meter_boundary_id}"
        )
        issues = _required_text(self.building_id, "building_id", key)
        issues += _required_text(self.scenario_id, "scenario_id", key)
        issues += _period_issues(self.period_id, key)
        issues += _required_text(self.carrier, "carrier", key)
        issues += _finite_range(
            self.measured_energy_kWh,
            "measured_energy_kWh",
            key,
            required=False,
        )
        issues += _required_text(self.data_quality_flag, "data_quality_flag", key)
        issues += _required_text(self.meter_boundary_id, "meter_boundary_id", key)
        return tuple(issues)


@dataclass(frozen=True)
class CalculationWarning:
    run_id: str
    engine_id: str
    building_id: str
    scenario_id: str
    weather_id: str
    code: str
    message: str
    period_id: str | None = None
    zone_id: str | None = None
    severity: str = "warning"

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = f"{self.run_id}|{self.engine_id}|{self.building_id}|{self.code}"
        issues: list[ValidationIssue] = []
        for name in (
            "run_id",
            "engine_id",
            "building_id",
            "scenario_id",
            "weather_id",
            "code",
            "message",
            "severity",
        ):
            issues += _required_text(getattr(self, name), name, key)
        if self.period_id is not None:
            issues += _period_issues(self.period_id, key)
        return tuple(issues)


@dataclass(frozen=True)
class MonthlyPhysicsRecord:
    run_id: str
    engine_id: str
    building_id: str
    scenario_id: str
    weather_id: str
    period_id: str
    calculation_boundary_id: str
    calculation_status: CalculationStatus
    zone_id: str | None = None
    days: int | None = None
    hours_valid: float | None = None
    outdoor_temp_C: float | None = None
    H_transmission_W_K: float | None = None
    H_ventilation_W_K: float | None = None
    H_infiltration_W_K: float | None = None
    H_ground_W_K: float | None = None
    H_total_W_K: float | None = None
    thermal_capacity_J_K: float | None = None
    time_constant_h: float | None = None
    heating_heat_transfer_kWh: float | None = None
    cooling_heat_transfer_kWh: float | None = None
    solar_gain_kWh: float | None = None
    internal_gain_kWh: float | None = None
    total_gain_kWh: float | None = None
    gamma_heating: float | None = None
    gamma_cooling: float | None = None
    utilisation_factor_heating: float | None = None
    utilisation_factor_cooling: float | None = None
    zone_sensible_heating_kWh: float | None = None
    zone_sensible_cooling_kWh: float | None = None
    ahu_sensible_heating_kWh: float | None = None
    ahu_sensible_cooling_kWh: float | None = None
    useful_heating_kWh: float | None = None
    useful_cooling_kWh: float | None = None
    warning_codes: tuple[str, ...] = ()

    @property
    def stable_key(self) -> tuple[str, str, str, str, str, str, str | None]:
        return (
            self.run_id,
            self.engine_id,
            self.building_id,
            self.scenario_id,
            self.weather_id,
            self.period_id,
            self.zone_id,
        )

    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        key = "|".join("" if item is None else str(item) for item in self.stable_key)
        issues: list[ValidationIssue] = []
        for name in (
            "run_id",
            "engine_id",
            "building_id",
            "scenario_id",
            "weather_id",
            "calculation_boundary_id",
        ):
            issues += _required_text(getattr(self, name), name, key)
        issues += _period_issues(self.period_id, key)
        if self.days is not None:
            issues += _finite_range(float(self.days), "days", key, 28, 31)
        if self.hours_valid is not None:
            upper = self.days * 24 if self.days is not None else None
            issues += _finite_range(
                self.hours_valid, "hours_valid", key, 0, upper, required=False
            )
        optional_nonnegative = (
            "H_transmission_W_K",
            "H_ventilation_W_K",
            "H_infiltration_W_K",
            "H_ground_W_K",
            "H_total_W_K",
            "thermal_capacity_J_K",
            "time_constant_h",
            "internal_gain_kWh",
            "zone_sensible_heating_kWh",
            "zone_sensible_cooling_kWh",
            "ahu_sensible_heating_kWh",
            "ahu_sensible_cooling_kWh",
            "useful_heating_kWh",
            "useful_cooling_kWh",
        )
        for name in optional_nonnegative:
            issues += _finite_range(
                getattr(self, name), name, key, 0, required=False
            )
        for name in ("utilisation_factor_heating", "utilisation_factor_cooling"):
            issues += _finite_range(
                getattr(self, name), name, key, 0, 1, required=False
            )
        for name in (
            "outdoor_temp_C",
            "heating_heat_transfer_kWh",
            "cooling_heat_transfer_kWh",
            "solar_gain_kWh",
            "total_gain_kWh",
            "gamma_heating",
            "gamma_cooling",
        ):
            issues += _finite_range(
                getattr(self, name), name, key, required=False
            )
        return tuple(issues)


@dataclass(frozen=True)
class MonthlyPhysicsResults:
    engine_id: str
    engine_version: str
    records: tuple[MonthlyPhysicsRecord, ...]
    warnings: tuple[CalculationWarning, ...] = ()
    metadata: Mapping[str, Any] | None = None

    def validate(self) -> "MonthlyPhysicsResults":
        issues: list[ValidationIssue] = []
        if not self.engine_id.strip():
            issues.append(
                ValidationIssue("REQUIRED", "engine_id", "must be non-empty")
            )
        if not self.engine_version.strip():
            issues.append(
                ValidationIssue("REQUIRED", "engine_version", "must be non-empty")
            )
        for record in self.records:
            if record.engine_id != self.engine_id:
                issues.append(
                    ValidationIssue(
                        "ENGINE_ID_MISMATCH",
                        "engine_id",
                        f"record uses {record.engine_id}, expected {self.engine_id}",
                    )
                )
        try:
            require_valid_collection(
                self.records,
                (
                    "run_id",
                    "engine_id",
                    "building_id",
                    "scenario_id",
                    "weather_id",
                    "period_id",
                    "zone_id",
                ),
                "monthly physics result",
            )
            require_valid_collection(
                self.warnings,
                (
                    "run_id",
                    "engine_id",
                    "building_id",
                    "scenario_id",
                    "weather_id",
                    "period_id",
                    "zone_id",
                    "code",
                ),
                "warning",
            )
        except ContractValidationError as exc:
            issues.extend(exc.issues)
        if issues:
            raise ContractValidationError(issues)
        return self

    def to_frame(self) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for record in self.records:
            row = asdict(record)
            row["calculation_status"] = record.calculation_status.value
            row["warning_codes"] = "|".join(record.warning_codes)
            rows.append(row)
        return pd.DataFrame(rows, columns=[field.name for field in fields(MonthlyPhysicsRecord)])

    def warnings_frame(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(warning) for warning in self.warnings])


def records_frame(records: Sequence[object]) -> pd.DataFrame:
    """Convert canonical dataclass records to a numeric-preserving DataFrame."""

    rows: list[dict[str, Any]] = []
    for record in records:
        row = asdict(record)
        for name, value in tuple(row.items()):
            if isinstance(value, Enum):
                row[name] = value.value
        rows.append(row)
    return pd.DataFrame(rows)
