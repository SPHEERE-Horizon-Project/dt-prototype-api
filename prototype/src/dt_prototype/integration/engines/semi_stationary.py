"""Adapter for the validated ISO 13790 semi-stationary reference engine."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from dt_prototype.integration.engines.base import ForwardPhysicsEngine
from dt_prototype.integration.schemas import (
    CalculationStatus,
    CalculationWarning,
    MonthlyPhysicsRecord,
    MonthlyPhysicsResults,
)


@dataclass(frozen=True)
class SemiStationaryRequest:
    run_id: str
    building_id: str
    scenario_id: str
    weather_id: str
    building: Any
    weather: Any
    config: Any | None = None
    include_zone_results: bool = True


@dataclass(frozen=True)
class _ZoneDiagnostics:
    zone_id: str
    H_transmission_W_K: float
    H_ground_W_K: float
    H_infiltration_monthly_W_K: np.ndarray
    H_ventilation_external_monthly_W_K: np.ndarray
    H_total_monthly_W_K: np.ndarray
    thermal_capacity_J_K: float
    reference_time_constant_h: float
    internal_gain_monthly_kWh: np.ndarray
    solar_gain_monthly_kWh: np.ndarray
    result: pd.DataFrame
    has_ahu: bool


def _monthly(values: np.ndarray, index: pd.DatetimeIndex, how: str) -> np.ndarray:
    grouped = pd.Series(values, index=index).groupby(index.month)
    if how == "sum":
        return grouped.sum().to_numpy(dtype=float)
    if how == "mean":
        return grouped.mean().to_numpy(dtype=float)
    raise ValueError(f"Unsupported monthly aggregation: {how}")


class SemiStationaryEngine(ForwardPhysicsEngine[SemiStationaryRequest]):
    """Map the unchanged reference calculation to transparent canonical rows."""

    engine_id = "semi_stationary"

    def __init__(self) -> None:
        from dt_prototype.monthly import __version__

        self.engine_version = __version__

    @staticmethod
    def _zone_diagnostics(
        building: Any,
        weather: Any,
        config: Any,
        zone_index: int,
        zone_result: pd.DataFrame,
    ) -> _ZoneDiagnostics:
        from dt_prototype.common.constants import AIR_SPECIFIC_HEAT
        from dt_prototype.monthly.simulation.air_handling_unit import AirHandlingUnit
        from dt_prototype.monthly.simulation.models.model_5r1c import Model5R1C

        model = Model5R1C(building, weather, config, zone_index=zone_index)
        zone = model.zone
        h_ground = sum(
            surface.opaque_area * surface.construction.u_value
            for surface in zone.surfaces
            if surface.surface_type == "GroundFloor"
        )
        h_transmission = model.UA_tot - h_ground
        h_infiltration = zone.infiltration_mass_flow * AIR_SPECIFIC_HEAT
        h_ventilation_raw = zone.ventilation_mass_flow * AIR_SPECIFIC_HEAT
        if zone.ahu is None:
            h_ventilation_external = h_ventilation_raw
        else:
            ahu = AirHandlingUnit.from_dict(zone.ahu, mode=config.ahu_mode)
            outdoor_air_ratio = 1.0 if config.ahu_mode == "basic" else ahu.outdoor_air_ratio
            h_ventilation_external = (
                h_ventilation_raw * outdoor_air_ratio * (1.0 - ahu.eta_sensible)
            )

        h_infiltration_monthly = _monthly(h_infiltration, weather.df.index, "mean")
        h_ventilation_monthly = _monthly(
            h_ventilation_external, weather.df.index, "mean"
        )
        h_total_monthly = (
            model.UA_tot + h_infiltration_monthly + h_ventilation_monthly
        )
        reference_time_constant = model.Cm / (
            3600.0
            * (
                model.UA_tot
                + float(np.max(h_infiltration + h_ventilation_external))
            )
        )
        dt = weather.timestep_seconds
        internal_gain = _monthly(
            zone.gains_convective + zone.gains_radiative,
            weather.df.index,
            "sum",
        ) * dt / 3.6e6
        solar_gain = (
            _monthly(model.phi_sol, weather.df.index, "sum") * dt / 3.6e6
        )
        zone_id = building.zones[zone_index].geometry.zone_label
        return _ZoneDiagnostics(
            zone_id=zone_id,
            H_transmission_W_K=float(h_transmission),
            H_ground_W_K=float(h_ground),
            H_infiltration_monthly_W_K=h_infiltration_monthly,
            H_ventilation_external_monthly_W_K=h_ventilation_monthly,
            H_total_monthly_W_K=h_total_monthly,
            thermal_capacity_J_K=float(model.Cm),
            reference_time_constant_h=float(reference_time_constant),
            internal_gain_monthly_kWh=internal_gain,
            solar_gain_monthly_kWh=solar_gain,
            result=zone_result,
            has_ahu=zone.ahu is not None,
        )

    @staticmethod
    def _zone_result_frame(
        building_result: pd.DataFrame, zone_id: str, zone_count: int
    ) -> pd.DataFrame:
        if zone_count == 1:
            return building_result
        prefix = f"zone_{zone_id}_"
        columns = {
            column: column.removeprefix(prefix)
            for column in building_result.columns
            if column.startswith(prefix)
        }
        return building_result[list(columns)].rename(columns=columns)

    @staticmethod
    def _period_weather(weather: Any, month: int) -> tuple[int, float, float]:
        monthly = weather.df.loc[weather.df.index.month == month]
        year = int(weather.df.index[0].year)
        days = calendar.monthrange(year, month)[1]
        hours = float(len(monthly) / weather.time_steps_per_hour)
        outdoor = float(monthly["temp_air"].mean())
        return days, hours, outdoor

    def _record(
        self,
        inputs: SemiStationaryRequest,
        diagnostics: _ZoneDiagnostics,
        month_index: int,
        *,
        zone_id: str | None,
        result: pd.DataFrame,
        time_constant_h: float | None,
        warning_codes: tuple[str, ...],
    ) -> MonthlyPhysicsRecord:
        month = month_index + 1
        year = int(inputs.weather.df.index[0].year)
        days, hours, outdoor = self._period_weather(inputs.weather, month)
        row = result.iloc[month_index]
        gains = float(row["gains_kWh"])
        losses = float(row["heat_losses_kWh"])
        gamma_h = gains / losses if losses > 0.0 else None
        internal = float(diagnostics.internal_gain_monthly_kWh[month_index])
        solar = float(diagnostics.solar_gain_monthly_kWh[month_index])
        return MonthlyPhysicsRecord(
            run_id=inputs.run_id,
            engine_id=self.engine_id,
            building_id=inputs.building_id,
            scenario_id=inputs.scenario_id,
            weather_id=inputs.weather_id,
            period_id=f"{year:04d}-{month:02d}",
            zone_id=zone_id,
            calculation_boundary_id="useful_sensible_reference_including_separate_ahu",
            calculation_status=(
                CalculationStatus.WARNING if warning_codes else CalculationStatus.OK
            ),
            days=days,
            hours_valid=hours,
            outdoor_temp_C=outdoor,
            H_transmission_W_K=diagnostics.H_transmission_W_K,
            H_ventilation_W_K=float(
                diagnostics.H_ventilation_external_monthly_W_K[month_index]
            ),
            H_infiltration_W_K=float(
                diagnostics.H_infiltration_monthly_W_K[month_index]
            ),
            H_ground_W_K=diagnostics.H_ground_W_K,
            H_total_W_K=float(diagnostics.H_total_monthly_W_K[month_index]),
            thermal_capacity_J_K=diagnostics.thermal_capacity_J_K,
            time_constant_h=time_constant_h,
            heating_heat_transfer_kWh=losses,
            cooling_heat_transfer_kWh=None,
            solar_gain_kWh=solar,
            internal_gain_kWh=internal,
            total_gain_kWh=gains,
            gamma_heating=gamma_h,
            gamma_cooling=None,
            utilisation_factor_heating=float(row["eta_gain_heating"]),
            utilisation_factor_cooling=float(row["eta_loss_cooling"]),
            zone_sensible_heating_kWh=float(row["heating_demand_kWh"]),
            zone_sensible_cooling_kWh=float(row["cooling_demand_kWh"]),
            ahu_sensible_heating_kWh=float(row["ahu_heating_demand_kWh"]),
            ahu_sensible_cooling_kWh=float(row["ahu_cooling_demand_kWh"]),
            useful_heating_kWh=float(row["total_sensible_heating_demand_kWh"]),
            useful_cooling_kWh=float(row["total_sensible_cooling_demand_kWh"]),
            warning_codes=warning_codes,
        )

    def simulate(self, inputs: SemiStationaryRequest) -> MonthlyPhysicsResults:
        from dt_prototype.monthly.simulation.config import SimulationConfig
        from dt_prototype.monthly.simulation.quasi_steady_state import run_quasi_steady_state

        config = inputs.config or SimulationConfig()
        building_result = run_quasi_steady_state(inputs.building, inputs.weather, config)
        zone_count = len(inputs.building.zones)
        zone_diagnostics: list[_ZoneDiagnostics] = []
        for zone_index in range(zone_count):
            zone_id = inputs.building.zones[zone_index].geometry.zone_label
            zone_result = self._zone_result_frame(building_result, zone_id, zone_count)
            zone_diagnostics.append(
                self._zone_diagnostics(
                    inputs.building,
                    inputs.weather,
                    config,
                    zone_index,
                    zone_result,
                )
            )

        warnings: list[CalculationWarning] = []
        base_codes = [
            "REFERENCE_GROUND_0P7_U",
            "REFERENCE_SOLAR_TERM_INCLUDES_LONGWAVE",
        ]
        warnings.extend(
            (
                CalculationWarning(
                run_id=inputs.run_id,
                engine_id=self.engine_id,
                building_id=inputs.building_id,
                scenario_id=inputs.scenario_id,
                weather_id=inputs.weather_id,
                code="REFERENCE_GROUND_0P7_U",
                message=(
                    "Ground-floor U follows the validated reference 0.7 multiplier convention."
                ),
                ),
                CalculationWarning(
                    run_id=inputs.run_id,
                    engine_id=self.engine_id,
                    building_id=inputs.building_id,
                    scenario_id=inputs.scenario_id,
                    weather_id=inputs.weather_id,
                    code="REFERENCE_SOLAR_TERM_INCLUDES_LONGWAVE",
                    message=(
                        "The mapped solar_gain_kWh is the reference phi_sol term and includes "
                        "opaque long-wave sky exchange as well as solar gains."
                    ),
                ),
            )
        )
        if any(item.has_ahu for item in zone_diagnostics):
            base_codes.append("AHU_SENSIBLE_REPORTED_SEPARATELY")
            warnings.append(
                CalculationWarning(
                    run_id=inputs.run_id,
                    engine_id=self.engine_id,
                    building_id=inputs.building_id,
                    scenario_id=inputs.scenario_id,
                    weather_id=inputs.weather_id,
                    code="AHU_SENSIBLE_REPORTED_SEPARATELY",
                    message=(
                        "Useful sensible totals include separately reported AHU coil demand; "
                        "AHU demand is not folded into H_effective."
                    ),
                )
            )
        if zone_count > 1:
            base_codes.extend(
                (
                    "TWO_ZONE_ADIABATIC_UNCOUPLED",
                    "AGGREGATED_TIME_CONSTANT_NOT_UNIQUE",
                )
            )
            warnings.extend(
                (
                    CalculationWarning(
                        run_id=inputs.run_id,
                        engine_id=self.engine_id,
                        building_id=inputs.building_id,
                        scenario_id=inputs.scenario_id,
                        weather_id=inputs.weather_id,
                        code="TWO_ZONE_ADIABATIC_UNCOUPLED",
                        message=(
                            "Upper and lower zones are solved independently with an adiabatic interface."
                        ),
                    ),
                    CalculationWarning(
                        run_id=inputs.run_id,
                        engine_id=self.engine_id,
                        building_id=inputs.building_id,
                        scenario_id=inputs.scenario_id,
                        weather_id=inputs.weather_id,
                        code="AGGREGATED_TIME_CONSTANT_NOT_UNIQUE",
                        message=(
                            "No single building time constant is reported for independently solved zones."
                        ),
                    ),
                )
            )

        records: list[MonthlyPhysicsRecord] = []
        if zone_count == 1:
            diagnostics = zone_diagnostics[0]
            for month_index in range(12):
                records.append(
                    self._record(
                        inputs,
                        diagnostics,
                        month_index,
                        zone_id=None,
                        result=building_result,
                        time_constant_h=diagnostics.reference_time_constant_h,
                        warning_codes=tuple(base_codes),
                    )
                )
        else:
            aggregate_diagnostics = _ZoneDiagnostics(
                zone_id="aggregate",
                H_transmission_W_K=sum(
                    item.H_transmission_W_K for item in zone_diagnostics
                ),
                H_ground_W_K=sum(item.H_ground_W_K for item in zone_diagnostics),
                H_infiltration_monthly_W_K=sum(
                    (item.H_infiltration_monthly_W_K for item in zone_diagnostics),
                    start=np.zeros(12),
                ),
                H_ventilation_external_monthly_W_K=sum(
                    (
                        item.H_ventilation_external_monthly_W_K
                        for item in zone_diagnostics
                    ),
                    start=np.zeros(12),
                ),
                H_total_monthly_W_K=sum(
                    (item.H_total_monthly_W_K for item in zone_diagnostics),
                    start=np.zeros(12),
                ),
                thermal_capacity_J_K=sum(
                    item.thermal_capacity_J_K for item in zone_diagnostics
                ),
                reference_time_constant_h=float("nan"),
                internal_gain_monthly_kWh=sum(
                    (item.internal_gain_monthly_kWh for item in zone_diagnostics),
                    start=np.zeros(12),
                ),
                solar_gain_monthly_kWh=sum(
                    (item.solar_gain_monthly_kWh for item in zone_diagnostics),
                    start=np.zeros(12),
                ),
                result=building_result,
                has_ahu=any(item.has_ahu for item in zone_diagnostics),
            )
            for month_index in range(12):
                records.append(
                    self._record(
                        inputs,
                        aggregate_diagnostics,
                        month_index,
                        zone_id=None,
                        result=building_result,
                        time_constant_h=None,
                        warning_codes=tuple(base_codes),
                    )
                )
            if inputs.include_zone_results:
                for diagnostics in zone_diagnostics:
                    zone_codes = tuple(
                        code
                        for code in base_codes
                        if code != "AGGREGATED_TIME_CONSTANT_NOT_UNIQUE"
                    )
                    for month_index in range(12):
                        records.append(
                            self._record(
                                inputs,
                                diagnostics,
                                month_index,
                                zone_id=diagnostics.zone_id,
                                result=diagnostics.result,
                                time_constant_h=diagnostics.reference_time_constant_h,
                                warning_codes=zone_codes,
                            )
                        )

        return MonthlyPhysicsResults(
            engine_id=self.engine_id,
            engine_version=self.engine_version,
            records=tuple(records),
            warnings=tuple(warnings),
            metadata={
                "reference_engine": True,
                "benchmark_validated_in_prior_project_phases": True,
                "zone_count": zone_count,
                "zone_aggregation": (
                    "single" if zone_count == 1 else "independent_adiabatic_sum"
                ),
                "ground_method_id": "reference_ground_floor_u_times_0p7",
                "ventilation_boundary": "external_air_effect;ahu_coil_separate",
                "equations_modified_by_adapter": False,
            },
        ).validate()
