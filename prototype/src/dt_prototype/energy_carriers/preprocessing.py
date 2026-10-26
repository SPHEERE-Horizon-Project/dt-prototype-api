"""Common ancillary schedules and renewable production for every thermal solver."""
from dataclasses import dataclass
import numpy as np
import pandas as pd

from dt_prototype.common.constants import AIR_DENSITY
from dt_prototype.dynamic_rc.simulation.zone import build_zone
from .config import EnergyConfig
from .engine import ENERGY_INPUTS, aggregate_inputs, validate_inputs


@dataclass
class CommonEnergyInputs:
    intervals: pd.DataFrame
    zones: dict[str, pd.DataFrame]
    metadata: dict

    def monthly(self):
        return aggregate_inputs(self.intervals)


def prepare_common(building, weather, config: EnergyConfig) -> CommonEnergyInputs:
    """Generate schedules once, independently of each solver's thermal gains.

    Roof irradiance comes from the existing shared weather/surface mapping.
    PV uses capacity × irradiation × PR. Solar thermal uses the specified
    optical/linear/quadratic collector loss curve at a fixed mean fluid temperature.
    Production is calculated at weather resolution and summed for monthly users.
    """
    bid = str(building.geometry.building_id)
    b = config.building(bid)
    dt = weather.timestep_seconds / 3600
    t = weather.df.temp_air.to_numpy()
    index = weather.df.index
    base = pd.DataFrame(dict(time=index.astype(str), period_id=index.to_period("M").astype(str),
                             duration_h=dt, outdoor_temp_C=t))
    for field in ENERGY_INPUTS:
        base[field] = 0.0
    zones = {}
    roof_area, pv_capacity, collector_area = 0.0, 0.0, 0.0
    for zi, zi_input in enumerate(building.zones):
        zone = build_zone(building, weather, zi)
        frame = base.copy()
        frame[list(ENERGY_INPUTS)] = 0.0
        frame["dhw_kWh"] = zone.dhw_demand * dt / 1000
        frame["appliances_kWh"] = zone.electric_load * dt / 1000
        # The shared schedule's mechanical flow already contains its time variation.
        # Existing AHU fan law uses this flow even when its thermal treatment is off.
        frame["fans_kWh"] = (zone.ventilation_mass_flow / AIR_DENSITY * 3600
                             * b["fan_W_per_m3_h"] * dt / 1000) if zone.ahu is not None else 0.0
        zones[str(zi_input.geometry.zone_label)] = frame
        for field in ("dhw_kWh", "appliances_kWh", "fans_kWh"):
            base[field] += frame[field]
        for roof in zone.surfaces:
            if roof.surface_type != "Roof":
                continue
            if roof.poa_global is None:
                raise ValueError("Roof irradiance unavailable")
            g = np.maximum(roof.poa_global, 0)
            roof_area += roof.gross_area
            pv = b["pv"]
            capacity = roof.gross_area * pv["roof_coverage"] * pv["module_kWp_per_m2"]
            pv_capacity += capacity
            base["pv_generation_kWh"] += capacity * g / 1000 * dt * pv["performance_ratio"]
            st = b["solar_thermal"]
            area = roof.gross_area * st["roof_coverage"]
            collector_area += area
            lift = np.maximum(st["mean_fluid_temperature_C"] - t, 0)
            power = area * np.maximum(st["eta0"] * g - st["a1_W_m2K"] * lift - st["a2_W_m2K2"] * lift**2, 0)
            base["solar_thermal_available_kWh"] += power * dt / 1000
    base["base_auxiliary_kWh"] = b["base_auxiliary_W"] * dt / 1000
    validate_inputs(base, "dynamic")
    return CommonEnergyInputs(base, zones, dict(
        building_id=bid, roof_area_m2=roof_area, pv_capacity_kWp=pv_capacity,
        solar_thermal_area_m2=collector_area,
        renewable_production="shared weather intervals integrated for monthly use",
        auxiliary_source="actual electric/DHW/ventilation schedules; no thermal-gain proxy",
    ))
