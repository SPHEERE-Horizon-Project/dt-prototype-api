"""Create declared Model 3 comparison inputs from reference-engine results.

The transformation is intentionally visible.  It preserves quantities that
Model 3 can represent directly and records approximations for schedules,
air-exchange variation, thermal mass classes, and collapsed zones.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from dt_prototype.integration.engines.model3 import Model3Request
from dt_prototype.integration.model3 import model3
from dt_prototype.integration.schemas import MonthlyPhysicsRecord, MonthlyPhysicsResults


@dataclass(frozen=True)
class MappedModel3Case:
    """Written legacy inputs plus the request needed to execute them."""

    data_dir: Path
    request: Model3Request
    manifest: Mapping[str, Any]


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _selected_zones(building: Any, zone_id: str | None) -> list[Any]:
    if zone_id is None:
        return list(building.zones)
    zones = [zone for zone in building.zones if zone.geometry.zone_label == zone_id]
    if not zones:
        raise KeyError(f"Reference building has no zone_id={zone_id!r}")
    return zones


def _weighted_active_setpoint(
    zones: Sequence[Any], weather: Any, config: Any, *, heating: bool
) -> float:
    from dt_prototype.monthly.simulation.config import season_mask
    from dt_prototype.monthly.simulation.quasi_steady_state import (
        _COOLING_SETPOINT_THRESHOLD,
        _HEATING_SETPOINT_THRESHOLD,
    )

    available = season_mask(
        weather.df.index, config.heating_season if heating else config.cooling_season
    )
    values: list[float] = []
    weights: list[float] = []
    for zone in zones:
        schedule = zone.schedule
        series = schedule.heating_setpoint if heating else schedule.cooling_setpoint
        active = (
            series > _HEATING_SETPOINT_THRESHOLD
            if heating
            else series < _COOLING_SETPOINT_THRESHOLD
        ) & available
        if active.any():
            values.append(float(series[active].mean()))
            weights.append(float(zone.geometry.net_floor_area))
    if not values:
        return 20.0 if heating else 26.0
    return float(np.average(values, weights=weights))


def _monthly_operation_fractions(
    zones: Sequence[Any], weather: Any, config: Any, *, heating: bool
) -> dict[str, float]:
    """Collapse hourly conditioning availability to area-weighted monthly fractions."""
    from dt_prototype.monthly.simulation.config import season_mask
    from dt_prototype.monthly.simulation.quasi_steady_state import (
        _COOLING_SETPOINT_THRESHOLD,
        _HEATING_SETPOINT_THRESHOLD,
    )

    index = weather.df.index
    available = season_mask(
        index, config.heating_season if heating else config.cooling_season
    )
    total_area = sum(float(zone.geometry.net_floor_area) for zone in zones)
    active_area = np.zeros(len(index), dtype=float)
    for zone in zones:
        setpoint = (
            zone.schedule.heating_setpoint
            if heating
            else zone.schedule.cooling_setpoint
        )
        intended = (
            setpoint > _HEATING_SETPOINT_THRESHOLD
            if heating
            else setpoint < _COOLING_SETPOINT_THRESHOLD
        )
        active_area += intended * available * float(zone.geometry.net_floor_area)
    fraction = active_area / total_area
    year = int(index[0].year)
    return {
        f"{year:04d}-{month:02d}": float(fraction[index.month == month].mean())
        for month in range(1, 13)
    }


def _enhanced_airflow_mapping(
    building: Any, zones: Sequence[Any], weather: Any
) -> dict[str, float | bool]:
    """Map resolved reference airflows to independent monthly Model 3 inputs."""
    from dt_prototype.common.constants import AIR_DENSITY
    from dt_prototype.monthly.simulation.air_handling_unit import AirHandlingUnit
    from dt_prototype.monthly.simulation.zone import build_zone

    selected = {id(zone) for zone in zones}
    direct_airflow_m3_h = 0.0
    ahu_airflow_m3_h = 0.0
    external_ahu_airflow_m3_h = 0.0
    recovery_weighted = 0.0
    outdoor_ratio_weighted = 0.0
    supply_heating_weighted = 0.0
    supply_cooling_weighted = 0.0

    for zone_index, input_zone in enumerate(building.zones):
        if id(input_zone) not in selected:
            continue
        resolved = build_zone(building, weather, zone_index)
        infiltration = float(np.mean(resolved.infiltration_mass_flow)) * 3600.0 / AIR_DENSITY
        ventilation = float(np.mean(resolved.ventilation_mass_flow)) * 3600.0 / AIR_DENSITY
        direct_airflow_m3_h += infiltration
        if resolved.ahu is None or ventilation <= 0.0:
            direct_airflow_m3_h += ventilation
            continue

        ahu = AirHandlingUnit.from_dict(resolved.ahu, mode="extended")
        ahu_airflow_m3_h += ventilation
        external_ahu_airflow_m3_h += ventilation * ahu.outdoor_air_ratio * (
            1.0 - ahu.eta_sensible
        )
        recovery_weighted += ventilation * ahu.eta_sensible
        outdoor_ratio_weighted += ventilation * ahu.outdoor_air_ratio
        supply_heating_weighted += ventilation * ahu.t_sup_heating
        supply_cooling_weighted += ventilation * ahu.t_sup_cooling

    if ahu_airflow_m3_h <= 0.0:
        return {
            "direct_airflow_m3_h": direct_airflow_m3_h,
            "ahu_airflow_m3_h": 0.0,
            "effective_heat_recovery_efficiency": 0.0,
            "ahu_enabled": False,
            "ahu_sensible_recovery_efficiency": 0.0,
            "ahu_outdoor_air_ratio": 1.0,
            "ahu_supply_heating_C": 0.0,
            "ahu_supply_cooling_C": 0.0,
        }

    return {
        "direct_airflow_m3_h": direct_airflow_m3_h,
        "ahu_airflow_m3_h": ahu_airflow_m3_h,
        # Model 3's legacy HTC accepts one recovery efficiency. This equivalent
        # value preserves the resolved external-air coefficient exactly.
        "effective_heat_recovery_efficiency": 1.0
        - external_ahu_airflow_m3_h / ahu_airflow_m3_h,
        "ahu_enabled": True,
        "ahu_sensible_recovery_efficiency": recovery_weighted / ahu_airflow_m3_h,
        "ahu_outdoor_air_ratio": outdoor_ratio_weighted / ahu_airflow_m3_h,
        "ahu_supply_heating_C": supply_heating_weighted / ahu_airflow_m3_h,
        "ahu_supply_cooling_C": supply_cooling_weighted / ahu_airflow_m3_h,
    }


def _nearest_mass_class(
    specific_capacity_J_m2K: float, mass_capacity: Mapping[str, float]
) -> tuple[str, float]:
    name = min(
        mass_capacity,
        key=lambda key: abs(float(mass_capacity[key]) - specific_capacity_J_m2K),
    )
    return name, float(mass_capacity[name])


def write_reference_case_as_model3_inputs(
    target_dir: str | Path,
    *,
    reference_results: MonthlyPhysicsResults,
    reference_building: Any,
    reference_weather: Any,
    run_id: str,
    scenario_id: str,
    weather_id: str,
    zone_id: str | None,
    config: Any | None = None,
    comparison_mode: str = "legacy",
) -> MappedModel3Case:
    """Write one aggregate or individual-zone Model 3 comparison case."""

    from dt_prototype.monthly.simulation.config import SimulationConfig

    if reference_results.engine_id not in {"semi_stationary", "dt_prototype_inputs"}:
        raise ValueError("Expected reference results or canonical prepared mapping inputs")
    config = config or SimulationConfig()
    if comparison_mode not in {"legacy", "seasonal_ahu"}:
        raise ValueError("comparison_mode must be 'legacy' or 'seasonal_ahu'")
    target = Path(target_dir).resolve()
    target.mkdir(parents=True, exist_ok=False)
    zones = _selected_zones(reference_building, zone_id)
    rows = sorted(
        (
            row
            for row in reference_results.records
            if row.zone_id == zone_id
        ),
        key=lambda row: row.period_id,
    )
    if len(rows) != 12:
        raise ValueError(
            f"Expected 12 reference rows for zone_id={zone_id!r}, got {len(rows)}"
        )

    source_building_id = "REFERENCE_MAPPED_CASE"
    source_scenario_id = "REFERENCE_MAPPED_SCENARIO"
    result_building_id = reference_results.records[0].building_id
    area = sum(float(zone.geometry.net_floor_area) for zone in zones)
    volume = sum(float(zone.geometry.volume) for zone in zones)
    H_transmission = float(rows[0].H_transmission_W_K or 0.0)
    H_ground = float(rows[0].H_ground_W_K or 0.0)
    H_air_values = [
        float(row.H_ventilation_W_K or 0.0) + float(row.H_infiltration_W_K or 0.0)
        for row in rows
    ]
    hours = [float(row.hours_valid or (row.days or 0) * 24.0) for row in rows]
    H_air_annual_mean = float(np.average(H_air_values, weights=hours))
    q_infiltration_m3_h = (
        H_air_annual_mean
        * 3600.0
        / (float(model3.DEFAULTS["rho_air"]) * float(model3.DEFAULTS["cp_air"]))
    )
    thermal_capacity = float(rows[0].thermal_capacity_J_K or 0.0)
    specific_capacity = thermal_capacity / area
    mass_class, mapped_specific_capacity = _nearest_mass_class(
        specific_capacity, model3.MASS_CAPACITY
    )
    heating_setpoint = _weighted_active_setpoint(
        zones, reference_weather, config, heating=True
    )
    cooling_setpoint = _weighted_active_setpoint(
        zones, reference_weather, config, heating=False
    )
    heating_fractions = _monthly_operation_fractions(
        zones, reference_weather, config, heating=True
    )
    cooling_fractions = _monthly_operation_fractions(
        zones, reference_weather, config, heating=False
    )
    enhanced_airflow = (
        _enhanced_airflow_mapping(reference_building, zones, reference_weather)
        if comparison_mode == "seasonal_ahu"
        else None
    )

    building_fields = [
        "building_id",
        "building_name",
        "configuration_id",
        "conditioned_floor_area_m2",
        "conditioned_volume_m3",
        "H_transmission_opaque_W_K",
        "H_transmission_windows_W_K",
        "H_ground_W_K",
        "mechanical_ventilation_m3_h",
        "infiltration_m3_h",
        "heat_recovery_efficiency",
        "mass_class",
        "occupant_count",
        "electricity_to_heat_fraction",
        "heating_setpoint_C",
        "cooling_setpoint_C",
        "cooling_enabled",
        "bivalent_temp_C",
        "window_N_area_m2",
        "window_E_area_m2",
        "window_S_area_m2",
        "window_W_area_m2",
        "window_HOR_area_m2",
        "glazing_g_value",
        "shading_factor",
        "frame_fraction",
        "pv_enabled",
        "pv_peak_kWp",
        "pv_orientation",
        "pv_performance_ratio",
        "solar_thermal_enabled",
        "solar_thermal_area_m2",
        "solar_thermal_orientation",
        "solar_thermal_efficiency",
        "seasonal_ahu_comparison_enabled",
        "ahu_enabled",
        "ahu_sensible_recovery_efficiency",
        "ahu_outdoor_air_ratio",
        "ahu_supply_heating_C",
        "ahu_supply_cooling_C",
    ]
    _write_csv(
        target / "buildings.csv",
        building_fields,
        (
            {
                "building_id": source_building_id,
                "building_name": f"Mapped reference {result_building_id} {zone_id or 'aggregate'}",
                "configuration_id": 1,
                "conditioned_floor_area_m2": area,
                "conditioned_volume_m3": volume,
                "H_transmission_opaque_W_K": H_transmission,
                "H_transmission_windows_W_K": 0.0,
                "H_ground_W_K": H_ground,
                "mechanical_ventilation_m3_h": (
                    enhanced_airflow["ahu_airflow_m3_h"] if enhanced_airflow else 0.0
                ),
                "infiltration_m3_h": (
                    enhanced_airflow["direct_airflow_m3_h"]
                    if enhanced_airflow
                    else q_infiltration_m3_h
                ),
                "heat_recovery_efficiency": (
                    enhanced_airflow["effective_heat_recovery_efficiency"]
                    if enhanced_airflow
                    else 0.0
                ),
                "mass_class": mass_class,
                "occupant_count": 0.0,
                "electricity_to_heat_fraction": 1.0,
                "heating_setpoint_C": heating_setpoint,
                "cooling_setpoint_C": cooling_setpoint,
                "cooling_enabled": 1,
                "bivalent_temp_C": -100.0,
                "window_N_area_m2": 0.0,
                "window_E_area_m2": 0.0,
                "window_S_area_m2": 0.0,
                "window_W_area_m2": 0.0,
                "window_HOR_area_m2": 0.0,
                "glazing_g_value": 0.0,
                "shading_factor": 1.0,
                "frame_fraction": 0.0,
                "pv_enabled": 0,
                "pv_peak_kWp": 0.0,
                "pv_orientation": "S",
                "pv_performance_ratio": 0.0,
                "solar_thermal_enabled": 0,
                "solar_thermal_area_m2": 0.0,
                "solar_thermal_orientation": "S",
                "solar_thermal_efficiency": 0.0,
                "seasonal_ahu_comparison_enabled": int(
                    comparison_mode == "seasonal_ahu"
                ),
                "ahu_enabled": int(
                    bool(enhanced_airflow and enhanced_airflow["ahu_enabled"])
                ),
                "ahu_sensible_recovery_efficiency": (
                    enhanced_airflow["ahu_sensible_recovery_efficiency"]
                    if enhanced_airflow
                    else 0.0
                ),
                "ahu_outdoor_air_ratio": (
                    enhanced_airflow["ahu_outdoor_air_ratio"] if enhanced_airflow else 1.0
                ),
                "ahu_supply_heating_C": (
                    enhanced_airflow["ahu_supply_heating_C"] if enhanced_airflow else 0.0
                ),
                "ahu_supply_cooling_C": (
                    enhanced_airflow["ahu_supply_cooling_C"] if enhanced_airflow else 0.0
                ),
            },
        ),
    )

    scenario_fields = [
        "scenario_key",
        "building_id",
        "scenario_id",
        "scenario_name",
        "envelope_htc_multiplier",
        "ground_htc_multiplier",
        "ventilation_multiplier",
        "infiltration_multiplier",
        "occupancy_multiplier",
        "operation_multiplier",
        "solar_gain_multiplier",
        "heating_setpoint_delta_K",
        "cooling_setpoint_delta_K",
        "system_efficiency_multiplier",
        "dhw_multiplier",
        "pv_multiplier",
    ]
    _write_csv(
        target / "scenarios.csv",
        scenario_fields,
        (
            {
                "scenario_key": "mapped",
                "building_id": source_building_id,
                "scenario_id": source_scenario_id,
                "scenario_name": "Mapped validated reference",
                "envelope_htc_multiplier": 1.0,
                "ground_htc_multiplier": 1.0,
                "ventilation_multiplier": 1.0,
                "infiltration_multiplier": 1.0,
                "occupancy_multiplier": 1.0,
                "operation_multiplier": 1.0,
                "solar_gain_multiplier": 1.0,
                "heating_setpoint_delta_K": 0.0,
                "cooling_setpoint_delta_K": 0.0,
                "system_efficiency_multiplier": 1.0,
                "dhw_multiplier": 1.0,
                "pv_multiplier": 1.0,
            },
        ),
    )

    timeseries_fields = [
        "record_key",
        "building_id",
        "scenario_id",
        "period_id",
        "days",
        "outdoor_temp_C",
        "occupancy_fraction",
        "lighting_appliance_power_W",
        "solar_N_kWh_m2",
        "solar_E_kWh_m2",
        "solar_S_kWh_m2",
        "solar_W_kWh_m2",
        "solar_HOR_kWh_m2",
        "heating_operation_fraction",
        "cooling_operation_fraction",
    ]
    timeseries_rows = []
    for row in rows:
        row_hours = float(row.hours_valid or (row.days or 0) * 24.0)
        mapped_gain_power = float(row.total_gain_kWh or 0.0) * 1000.0 / row_hours
        timeseries_rows.append(
            {
                "record_key": f"{source_building_id}|{source_scenario_id}|{row.period_id}",
                "building_id": source_building_id,
                "scenario_id": source_scenario_id,
                "period_id": row.period_id,
                "days": row.days,
                "outdoor_temp_C": row.outdoor_temp_C,
                "occupancy_fraction": 0.0,
                "lighting_appliance_power_W": mapped_gain_power,
                "solar_N_kWh_m2": 0.0,
                "solar_E_kWh_m2": 0.0,
                "solar_S_kWh_m2": 0.0,
                "solar_W_kWh_m2": 0.0,
                "solar_HOR_kWh_m2": 0.0,
                "heating_operation_fraction": heating_fractions[row.period_id],
                "cooling_operation_fraction": cooling_fractions[row.period_id],
            }
        )
    _write_csv(target / "timeseries.csv", timeseries_fields, timeseries_rows)

    systems_fields = [
        "system_key",
        "configuration_id",
        "service",
        "carrier",
        "form",
        "c0",
        "c1",
        "c2",
        "breakpoint_C",
        "c0_high",
        "c1_high",
        "description",
    ]
    _write_csv(
        target / "systems.csv",
        systems_fields,
        tuple(
            {
                "system_key": f"1|{service}",
                "configuration_id": 1,
                "service": service,
                "carrier": "electricity",
                "form": "const",
                "c0": 1.0,
                "c1": 0.0,
                "c2": 0.0,
                "breakpoint_C": "",
                "c0_high": "",
                "c1_high": "",
                "description": "Unit efficiency for useful-load comparison",
            }
            for service in model3.SERVICES
        ),
    )
    factor_fields = [
        "factor_key",
        "scenario_id",
        "carrier",
        "primary_energy_factor",
        "carbon_factor_kgCO2e_kWh",
        "source",
    ]
    _write_csv(
        target / "factors.csv",
        factor_fields,
        tuple(
            {
                "factor_key": f"{source_scenario_id}|{carrier}",
                "scenario_id": source_scenario_id,
                "carrier": carrier,
                "primary_energy_factor": 1.0,
                "carbon_factor_kgCO2e_kWh": 0.0,
                "source": "comparison-only neutral factor",
            }
            for carrier in model3.CARRIERS
        ),
    )
    metered_fields = [
        "building_id",
        "scenario_id",
        "period_id",
        "carrier",
        "measured_energy_kWh",
        "calibration_validation_flag",
        "data_quality_flag",
    ]
    _write_csv(target / "metered.csv", metered_fields, ())

    mapping_warnings: list[tuple[str, str]] = [
        (
            "REFERENCE_TOTAL_GAINS_MAPPED_TO_MODEL3_INTERNAL",
            "Reference total phi_sol plus internal gains are mapped to Model 3's internal-gain channel; solar components are not equivalent.",
        ),
        (
            "REFERENCE_AIR_EXCHANGE_MAPPED_AS_ANNUAL_MEAN",
            "Monthly reference infiltration plus external ventilation coefficients are mapped to one annual-mean Model 3 infiltration flow.",
        ),
        (
            "REFERENCE_CAPACITY_MAPPED_TO_NEAREST_MODEL3_MASS_CLASS",
            "Reference surface-layer capacity is mapped to the nearest Model 3 specific mass class.",
        ),
        (
            "REFERENCE_TRANSMISSION_MAPPED_AS_OPAQUE_TOTAL",
            "Reference non-ground transmission is mapped to Model 3 opaque transmission; opaque/window subdivision is not preserved.",
        ),
    ]
    if comparison_mode == "legacy":
        mapping_warnings.append(
            (
                "REFERENCE_SCHEDULES_MAPPED_TO_CONSTANT_SETPOINTS",
                "Reference active setpoint schedules are mapped to area-weighted constants; operating-hour effects remain approximate.",
            )
        )
    else:
        mapping_warnings.extend(
            (
                (
                    "REFERENCE_SEASON_MASK_MAPPED_TO_MONTHLY_FRACTIONS",
                    "Hourly conditioning availability is mapped to explicit monthly fractions; setpoints remain area-weighted constants.",
                ),
                (
                    "MODEL3_AHU_MONTHLY_MEAN_APPROXIMATION",
                    "Model 3 calculates the AHU coil independently from monthly mean weather and mapped airflow/recovery/supply inputs.",
                ),
            )
        )
    if zone_id is None and len(reference_building.zones) > 1:
        mapping_warnings.append(
            (
                "REFERENCE_TWO_ZONE_COLLAPSED_TO_MODEL3_SINGLE_ZONE",
                "Independent upper/lower reference zones are collapsed to Model 3's single-zone representation.",
            )
        )

    manifest: dict[str, Any] = {
        "mapping_id": (
            "validated_reference_to_model3_seasonal_ahu_comparison_v2"
            if comparison_mode == "seasonal_ahu"
            else "validated_reference_to_model3_comparison_v1"
        ),
        "reference_engine_id": reference_results.engine_id,
        "reference_engine_version": reference_results.engine_version,
        "reference_building_id": result_building_id,
        "reference_zone_id": zone_id,
        "result_scenario_id": scenario_id,
        "weather_id": weather_id,
        "exact_or_direct_mappings": [
            "period_id",
            "days",
            "outdoor_temp_C",
            "H_transmission_W_K_total",
            "H_ground_W_K_reference_0p7_U",
            "monthly_total_gain_kWh_as_prescribed_internal_gain",
            "monthly_conditioning_availability_fraction"
            if comparison_mode == "seasonal_ahu"
            else None,
        ],
        "approximate_mappings": [
            "air_exchange_as_annual_mean",
            "thermal_capacity_as_nearest_model3_mass_class",
            "active_setpoints_as_area_weighted_constants",
            "reference_schedules_to_full_month_model3_operation"
            if comparison_mode == "legacy"
            else "monthly_mean_ahu_coil_calculation",
            "two_zone_to_single_zone" if zone_id is None and len(reference_building.zones) > 1 else None,
        ],
        "mapped_values": {
            "area_m2": area,
            "volume_m3": volume,
            "H_transmission_W_K": H_transmission,
            "H_ground_W_K": H_ground,
            "H_air_annual_mean_W_K": H_air_annual_mean,
            "reference_specific_capacity_J_m2K": specific_capacity,
            "model3_mass_class": mass_class,
            "model3_specific_capacity_J_m2K": mapped_specific_capacity,
            "heating_setpoint_C": heating_setpoint,
            "cooling_setpoint_C": cooling_setpoint,
            "comparison_mode": comparison_mode,
            "heating_operation_fraction_by_period": heating_fractions,
            "cooling_operation_fraction_by_period": cooling_fractions,
            "enhanced_airflow": enhanced_airflow,
        },
        "warning_codes": [code for code, _message in mapping_warnings],
        "equations_modified": comparison_mode == "seasonal_ahu",
    }
    manifest["exact_or_direct_mappings"] = [
        item for item in manifest["exact_or_direct_mappings"] if item is not None
    ]
    manifest["approximate_mappings"] = [
        item for item in manifest["approximate_mappings"] if item is not None
    ]
    (target / "mapping_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    request = Model3Request(
        run_id=run_id,
        data_dir=target,
        building_id=source_building_id,
        scenario_id=source_scenario_id,
        weather_id=weather_id,
        zone_id=zone_id,
        result_building_id=result_building_id,
        result_scenario_id=scenario_id,
        additional_warnings=tuple(mapping_warnings),
        mapping_metadata=manifest,
        comparison_mode=comparison_mode,
    )
    return MappedModel3Case(data_dir=target, request=request, manifest=manifest)
