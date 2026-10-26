"""Thermal solvers → common positive interval-energy contract.

The shared comparison boundary is sensible zone plus separate sensible AHU,
with ideal thermal emitters. This intentionally excludes latent/reheat loads
which the monthly thermal methods do not resolve.
"""
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd

from dt_prototype.common.output_paths import output_component
from .config import SERVICES
from .engine import calculate, ENERGY_INPUTS, aggregate_inputs

THERMAL = [f"{s}_kWh" for s in SERVICES if s != "dhw"]


@dataclass
class ThermalCase:
    name: str
    resolution: str
    representation: str
    zones: dict[str, pd.DataFrame]

    def total(self):
        frames = list(self.zones.values())
        base = frames[0][["time", "period_id"]].copy()
        for f in frames[1:]:
            if not f[["time", "period_id"]].equals(base):
                raise ValueError("Zone time axes do not match")
        for field in THERMAL:
            base[field] = sum(f[field].to_numpy() for f in frames)
        return base


def _frame(index, values):
    index = pd.DatetimeIndex(index)
    result = pd.DataFrame(dict(time=index.astype(str), period_id=index.to_period("M").astype(str), **values))
    if not np.isfinite(result[THERMAL]).all().all() or (result[THERMAL] < -1e-8).any().any():
        raise ValueError("Invalid thermal demand from solver")
    result[THERMAL] = result[THERMAL].clip(lower=0)
    return result


def solve_cases(building, weather, operating, engine, directory: Path, *, dynamic_options=None,
                zone_mode="both", vb_solar="direct", vb_options=None):
    """Return native zone sums and, where supported, a separate collapsed case."""
    operation = {k: tuple(v) if k.endswith("_season") else v for k, v in operating.items()}
    multiple = len(building.zones) > 1
    representation = "sum_of_independent_zones" if multiple else "native_single_zone"
    if engine == "Dynamic_RC":
        from dt_prototype.dynamic_rc.simulation.config import SimulationConfig
        from dt_prototype.dynamic_rc.simulation.runner import run_building
        options = dict(dynamic_options or {})
        if options.get("plants", False) or options.get("latent", True) or options.get("pv_battery", False):
            raise ValueError("Shared sensible comparison requires dynamic plants=false, latent=false, pv_battery=false; legacy plants alter emitter physics")
        result = run_building(building, weather, SimulationConfig(**operation, **options))
        directory.mkdir(parents=True, exist_ok=True)
        result.to_csv(directory / "thermal_dynamic.csv", index_label="time")
        dt = weather.timestep_seconds / 3.6e6
        zones = {}
        for zi in building.zones:
            label = str(zi.geometry.zone_label)
            prefix = f"zone_{label}_" if multiple else ""
            zones[label] = _frame(result.index, dict(
                zone_heating_kWh=result[prefix + "heating_load"].to_numpy() * dt,
                zone_cooling_kWh=-result[prefix + "cooling_load"].to_numpy() * dt,
                ahu_heating_kWh=result[prefix + "ahu_sensible_load"].clip(lower=0).to_numpy() * dt,
                ahu_cooling_kWh=-result[prefix + "ahu_sensible_load"].clip(upper=0).to_numpy() * dt,
            ))
        return [ThermalCase("Dynamic_RC " + options.get("model", "7R2C"), "dynamic", representation, zones)]
    from dt_prototype.monthly_ss.simulation.config import SimulationConfig
    config = SimulationConfig(**operation)
    if engine == "Monthly_SS":
        from dt_prototype.monthly_ss.run import run_building
        result = run_building(building, weather, config)
        zones = {}
        for zi in building.zones:
            label = str(zi.geometry.zone_label)
            prefix = f"zone_{label}_" if multiple else ""
            zones[label] = _frame(result.index, {field: result[prefix + original].to_numpy() for field, original in zip(
                THERMAL, ["heating_demand_kWh", "ahu_heating_demand_kWh", "cooling_demand_kWh", "ahu_cooling_demand_kWh"])})
        return [ThermalCase("Monthly_SS", "monthly", representation, zones)]
    if engine == "Monthly_SS_simplified":
        from dt_prototype.monthly_ss_simplified.mapping.prepared_inputs import prepare_mapping_inputs
        from dt_prototype.monthly_ss_simplified.mapping import write_reference_case_as_model3_inputs
        from dt_prototype.monthly_ss_simplified.engines.model3 import Model3Engine
        prepared = prepare_mapping_inputs(building, weather, config)
        labels = [str(z.geometry.zone_label) for z in building.zones] if multiple else [None]
        if multiple and zone_mode == "collapsed":
            labels = [None]
        elif multiple and zone_mode == "both":
            labels += [None]
        zones, collapsed = {}, None
        for label in labels:
            mapped = write_reference_case_as_model3_inputs(directory / "mapped" / output_component(label or "collapsed"),
                reference_results=prepared, reference_building=building, reference_weather=weather,
                run_id=directory.name, scenario_id="shared_energy", weather_id="shared_epw",
                zone_id=label, comparison_mode="seasonal_ahu", config=config)
            result = Model3Engine().simulate(mapped.request).to_frame().sort_values("period_id")
            frame = _frame(pd.to_datetime(result.period_id + "-01"), {field: result[original].to_numpy() for field, original in zip(
                THERMAL, ["zone_sensible_heating_kWh", "ahu_sensible_heating_kWh", "zone_sensible_cooling_kWh", "ahu_sensible_cooling_kWh"])})
            if label is None and multiple:
                collapsed = ThermalCase("Monthly_SS_simplified collapsed", "monthly", "single_zone_collapsed", {"collapsed": frame})
            else:
                zones[label or str(building.zones[0].geometry.zone_label)] = frame
        cases = [ThermalCase("Monthly_SS_simplified zone sum", "monthly", representation, zones)] if zones else []
        return cases + ([collapsed] if collapsed else [])
    if engine == "Monthly_SS_VBDD":
        from dt_prototype.monthly_ss_vbdd import simulate, VBOptions
        from dt_prototype.monthly_ss_vbdd.preprocessing import prepare_building
        from dt_prototype.monthly_ss_vbdd.weather import temperature_linear_solar
        rows = prepare_building(building, weather, config)
        if vb_solar == "temperature_linear":
            rows, fit = temperature_linear_solar(rows)
            directory.mkdir(parents=True, exist_ok=True)
            fit.to_csv(directory / "vb_solar_fit.csv", index=False)
        options = vb_options or VBOptions()
        result = simulate(rows, options)
        variant = ("Monthly_SS_VBDD fixed linear" if vb_solar == "temperature_linear" else "Monthly_SS_VBDD fixed") if options.utilisation == "fixed" else ("Monthly_SS_VBDD linear" if vb_solar == "temperature_linear" else "Monthly_SS_VBDD monthly")
        zones, collapsed = {}, None
        for case, g in result.groupby("case_id", sort=True):
            g = g.sort_values("period_id")
            frame = _frame(pd.to_datetime(g.period_id + "-01"), {field: g[field].to_numpy() for field in THERMAL})
            if str(g.iloc[0].representation).startswith("single_zone_collapsed"):
                collapsed = ThermalCase(variant + " collapsed", "monthly", "single_zone_collapsed", {"collapsed": frame})
            else:
                zones[str(g.iloc[0].zone_id)] = frame
        cases = [] if multiple and zone_mode == "collapsed" else [ThermalCase(variant + " zone sum", "monthly", representation, zones)]
        if collapsed and zone_mode in ("collapsed", "both"):
            cases.append(collapsed)
        return cases
    raise ValueError(f"Unknown thermal engine {engine}")


def energy_inputs(case, common):
    frame = common.intervals.copy() if case.resolution == "dynamic" else common.monthly()
    thermal = case.total()
    # Compare parsed time axes, since midnight string formatting can differ.
    if not np.array_equal(pd.to_datetime(frame.time), pd.to_datetime(thermal.time)):
        raise ValueError("Thermal and common input times differ")
    if not np.array_equal(frame.period_id, thermal.period_id):
        raise ValueError("Thermal and common input months differ")
    frame[THERMAL] = thermal[THERMAL].to_numpy()
    return frame


def zone_allocations(case, common, result):
    """Allocate converted service energy to original zones by their useful demand.

    This reports the common building systems, not independent zone meters.
    Collapsed calculations have no reconstructable individual zone demands.
    """
    allocations = []
    for label, thermal in case.zones.items():
        if label == "collapsed":
            supplemental = common.intervals if case.resolution == "dynamic" else common.monthly()
        else:
            supplemental = common.zones[label]
            if case.resolution == "monthly":
                supplemental = aggregate_inputs(supplemental)
        for service in SERVICES:
            demand = supplemental.dhw_kWh.to_numpy() if service == "dhw" else thermal[f"{service}_kWh"].to_numpy()
            total = result.services[result.services.service == service].reset_index(drop=True)
            ratio = np.divide(demand, total.useful_demand_kWh.to_numpy(), out=np.zeros(len(demand)), where=total.useful_demand_kWh.to_numpy() > 0)
            row = total[["period_id", "service", "technology", "carrier"]].copy()
            row["zone_id"] = label
            row["useful_demand_kWh"] = demand
            for field in ("delivered_kWh", "auxiliary_kWh", "solar_thermal_used_kWh", "generator_output_kWh"):
                row[field] = total[field].to_numpy() * ratio
            allocations.append(row)
    fields = ["useful_demand_kWh", "delivered_kWh", "auxiliary_kWh", "solar_thermal_used_kWh", "generator_output_kWh"]
    return pd.concat(allocations).groupby(["period_id", "zone_id", "service", "technology", "carrier"], as_index=False)[fields].sum()
