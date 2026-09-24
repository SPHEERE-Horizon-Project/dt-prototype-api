"""Adapter around the embedded, preserved Model 3 Python pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from dt_prototype.integration.model3 import model3
from dt_prototype.integration.engines.base import ForwardPhysicsEngine
from dt_prototype.integration.schemas import (
    CalculationStatus,
    CalculationWarning,
    MonthlyPhysicsRecord,
    MonthlyPhysicsResults,
)
from dt_prototype.integration.weather import sha256_file


@dataclass(frozen=True)
class Model3Request:
    run_id: str
    data_dir: Path
    building_id: str
    scenario_id: str
    weather_id: str
    zone_id: str | None = None
    result_building_id: str | None = None
    result_scenario_id: str | None = None
    additional_warnings: tuple[tuple[str, str], ...] = ()
    mapping_metadata: Mapping[str, Any] | None = None
    comparison_mode: str = "legacy"


class Model3Engine(ForwardPhysicsEngine[Model3Request]):
    """Run Model 3 unchanged and expose its existing scientific boundary."""

    engine_id = "model3_legacy"
    engine_version = "3.0.0-legacy"

    def simulate(self, inputs: Model3Request) -> MonthlyPhysicsResults:
        module_path = Path(model3.__file__).resolve()
        data_dir = inputs.data_dir.resolve()
        if not data_dir.is_dir():
            raise FileNotFoundError(data_dir)

        all_rows, _metered_rows = model3.run_forward(data_dir)
        selected = [
            row
            for row in all_rows
            if row["building_id"] == inputs.building_id
            and row["scenario_id"] == inputs.scenario_id
        ]
        if not selected:
            raise KeyError(
                f"No Model 3 rows for {inputs.building_id}/{inputs.scenario_id}"
            )

        result_building_id = inputs.result_building_id or inputs.building_id
        result_scenario_id = inputs.result_scenario_id or inputs.scenario_id
        standard_warnings = (
            (
                "MODEL3_AIR_EXCHANGE_COMPONENTS_COMBINED",
                "Model 3 H_ventilation_W_K combines mechanical ventilation and infiltration.",
            ),
            (
                "MODEL3_GROUND_DIRECT_STEADY_INPUT",
                "Model 3 H_ground_W_K is a direct steady input; its method must be declared when mapped.",
            ),
        )
        all_warnings = standard_warnings + inputs.additional_warnings
        warning_codes = tuple(code for code, _message in all_warnings)
        enhanced = inputs.comparison_mode == "seasonal_ahu"
        records = tuple(
            MonthlyPhysicsRecord(
                run_id=inputs.run_id,
                engine_id=self.engine_id,
                building_id=result_building_id,
                scenario_id=result_scenario_id,
                weather_id=inputs.weather_id,
                period_id=row["period_id"],
                zone_id=inputs.zone_id,
                calculation_boundary_id=(
                    "useful_sensible_model3_zone_plus_separate_ahu"
                    if enhanced
                    else "useful_sensible_model3_zone_no_separate_ahu"
                ),
                calculation_status=CalculationStatus.WARNING,
                days=int(round(float(row["days"]))),
                hours_valid=float(row["hours"]),
                outdoor_temp_C=float(row["outdoor_temp_C"]),
                H_transmission_W_K=float(row["H_transmission_W_K"]),
                H_ventilation_W_K=float(row["H_ventilation_W_K"]),
                H_infiltration_W_K=None,
                H_ground_W_K=float(row["H_ground_W_K"]),
                H_total_W_K=float(row["H_total_W_K"]),
                thermal_capacity_J_K=float(row["thermal_capacity_J_K"]),
                time_constant_h=float(row["tau_h"]),
                heating_heat_transfer_kWh=float(row["heat_transfer_kWh"]),
                cooling_heat_transfer_kWh=float(row["cool_transfer_kWh"]),
                solar_gain_kWh=float(row["solar_gain_kWh"]),
                internal_gain_kWh=float(row["internal_gain_kWh"]),
                total_gain_kWh=float(row["total_gain_kWh"]),
                gamma_heating=(
                    None
                    if row["gamma_heating"] is None
                    else float(row["gamma_heating"])
                ),
                gamma_cooling=(
                    None
                    if row["gamma_cooling"] is None
                    else float(row["gamma_cooling"])
                ),
                utilisation_factor_heating=float(row["eta_heating"]),
                utilisation_factor_cooling=float(row["eta_cooling"]),
                zone_sensible_heating_kWh=float(
                    row.get("zone_sensible_heating_kWh", row["useful_heating_kWh"])
                ),
                zone_sensible_cooling_kWh=float(
                    row.get("zone_sensible_cooling_kWh", row["useful_cooling_kWh"])
                ),
                ahu_sensible_heating_kWh=float(
                    row.get("ahu_sensible_heating_kWh", 0.0)
                ),
                ahu_sensible_cooling_kWh=float(
                    row.get("ahu_sensible_cooling_kWh", 0.0)
                ),
                useful_heating_kWh=float(row["useful_heating_kWh"]),
                useful_cooling_kWh=float(row["useful_cooling_kWh"]),
                warning_codes=warning_codes,
            )
            for row in selected
        )
        warnings = tuple(
            CalculationWarning(
                run_id=inputs.run_id,
                engine_id=self.engine_id,
                building_id=result_building_id,
                scenario_id=result_scenario_id,
                weather_id=inputs.weather_id,
                code=code,
                message=message,
                zone_id=inputs.zone_id,
            )
            for code, message in all_warnings
        )
        metadata: dict[str, Any] = {
            "source_module": str(module_path),
            "source_module_sha256": sha256_file(module_path),
            "data_dir": str(data_dir),
            "equations_modified_by_adapter": False,
            "comparison_mode": inputs.comparison_mode,
        }
        if inputs.mapping_metadata is not None:
            metadata["mapping"] = dict(inputs.mapping_metadata)
        return MonthlyPhysicsResults(
            engine_id=self.engine_id,
            engine_version=self.engine_version,
            records=records,
            warnings=warnings,
            metadata=metadata,
        ).validate()
