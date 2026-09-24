"""Simulation orchestration: single building, portfolio, parallel batch.

Migrated from the run loops of ``reference_building.building.Building.simulate``
and ``reference_ubem.city.City.simulate``. Pure functions over serialisable
inputs — FastAPI-ready (NFR-04) and picklable for process-based parallelism
(FR-04, ``concurrent.futures``).
"""

from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from dt_prototype.common.constants import AIR_SPECIFIC_HEAT
from dt_prototype.common.preprocessing.building_input import BuildingInput, DistrictInput
from dt_prototype.common.preprocessing.weather import WeatherData
from dt_prototype.dynamic.simulation.config import SimulationConfig, season_mask
from dt_prototype.dynamic.simulation.design import design_cooling_power, design_heating_power
from dt_prototype.dynamic.simulation.dhw_tank import DhwTank
from dt_prototype.dynamic.simulation.model_base import ThermalModel, get_model_class
from dt_prototype.dynamic.simulation.pv_system import Battery, PVSystem
from dt_prototype.dynamic.simulation.solar_thermal import SolarThermalCollector
from dt_prototype.dynamic.simulation.systems import (
    IdealLoad,
    resolve_cooling_system,
    resolve_heating_system,
)

_SIZING_SAFETY_FACTOR = 1.25


def _design_powers(model: ThermalModel, weather: WeatherData) -> tuple[float, float]:
    """Static design heating/cooling powers [W] for plant sizing.

    Simplified steady-state sizing, used when ``config.sizing == "static"``
    (the EXTENDED default is the design-day simulation in
    :mod:`dt_prototype.dynamic.simulation.design`): transmission + ventilation losses
    at the extreme outdoor temperatures, plus internal gains on the cooling
    side, with a safety factor.
    """
    zone = model.zone
    hve_max = float(
        (zone.ventilation_mass_flow + zone.infiltration_mass_flow).max() * AIR_SPECIFIC_HEAT
    )
    t_min = float(weather.df["temp_air"].min())
    t_max = float(weather.df["temp_air"].max())
    dhw_peak = float(zone.dhw_demand.max()) if zone.dhw_demand.size else 0.0
    heating = (
        (model.UA_tot + hve_max)
        * (float(zone.heating_setpoint.max()) - t_min)
        * _SIZING_SAFETY_FACTOR
        + dhw_peak
    )
    heating = max(heating, 1000.0)
    gains_max = float((zone.gains_convective + zone.gains_radiative).max())
    cooling = (
        (model.UA_tot + hve_max) * (t_max - float(zone.cooling_setpoint.min())) + gains_max
    ) * _SIZING_SAFETY_FACTOR
    return heating, max(cooling, 1000.0)


def _roof_zone_index(building: BuildingInput) -> int:
    """Index of the zone whose surfaces include the Roof — the upper zone of
    a two-zone building (the retained reference's roof-only-upper convention), or the single
    zone otherwise. Used to size roof-mounted PV/solar thermal."""
    for i, zone_input in enumerate(building.zones):
        if any(s.surface_type == "Roof" for s in zone_input.geometry.surfaces):
            return i
    return 0


_PER_ZONE_KEYS = (
    "air_temperature",
    "operative_temperature",
    "mean_radiant_temperature",
    "relative_humidity",
    "sensible_load",
    "latent_load",
    "ahu_sensible_load",
    "ahu_latent_load",
    "heating_load",
    "cooling_load",
    "natural_ventilation_ach",
)


def run_building(
    building: BuildingInput,
    weather: WeatherData,
    config: SimulationConfig,
    system_templates: dict | None = None,
) -> pd.DataFrame:
    """Simulate one building over the whole weather period (FR-01).

    A building has one or two thermal zones (``building.zones`` — see the
    two-zone convention in ``preprocessing.geometry``); each is solved by
    its own, fully independent :class:`~dt_prototype.dynamic.simulation.model_base.
    ThermalModel` instance (the retained reference's zones are uncoupled RC networks, so
    this reproduces that exactly), sharing one HVAC plant/DHW tank/solar
    thermal collector sized from the sum of both zones' loads. For a
    single-zone building this reduces exactly to the single-model behaviour.

    Parameters
    ----------
    building : BuildingInput
        Serialised preprocessing output (FR-08 artefact).
    weather : WeatherData
        Processed weather (shared across buildings).
    config : SimulationConfig
        Run settings (model choice, latent, plants, seasons, limits).
    system_templates : dict, optional
        HVAC template database (``DistrictInput.system_templates``); used to
        resolve short system codes before catalog-name parsing.

    Returns
    -------
    pandas.DataFrame
        Time-indexed whole-building results (SI units): air/operative/mean-
        radiant temperatures [°C] (simple mean across zones), relative
        humidity [-] (simple mean), ``sensible_load``/``latent_load`` [W]
        and AHU coil loads (summed across zones), ``heating_load`` /
        ``cooling_load`` [W] (each zone's own sensible load bucketed into
        heat/cool *before* summing, so simultaneous heating in one zone and
        cooling in another is not netted away), ``dhw_demand`` [W],
        ``natural_ventilation_ach`` [1/h] (volume-weighted mean across
        zones — a diagnostic, not a physically summable quantity),
        ``electric_appliances`` [W] (summed). With ``config.plants`` also
        the plant carriers ``electric_plant``, ``gas``, ``district_heat``,
        ``other_fuel``, ``pv_production`` and ``solar_thermal_production``
        [W]; plus ``dhw_tank_temperature`` [°C] when a DHW tank is attached
        and — with ``config.pv_battery`` — ``battery_soc`` [0-1],
        ``grid_import`` / ``grid_export`` / ``pv_self_consumed`` [W]. For a
        two-zone building, the same per-zone quantities are also exposed as
        ``zone_upper_*`` / ``zone_lower_*`` columns.
    """
    n_zones = len(building.zones)
    models = [
        get_model_class(config.model)(building, weather, config, zone_index=i)
        for i in range(n_zones)
    ]
    roof_idx = _roof_zone_index(building)

    # structured warnings (also attached to the result DataFrame attrs)
    run_warnings: list[str] = []
    if config.plants:
        heating_sys, warn_h = resolve_heating_system(
            building.geometry.heating_system, system_templates
        )
        cooling_sys, warn_c = resolve_cooling_system(
            building.geometry.cooling_system, system_templates
        )
        for warning in (warn_h, warn_c):
            if warning:
                run_warnings.append(f"{building.name}: {warning}")
                logging.warning(f"{building.name}: {warning}")
        # plant sizing: explicit config limits win; otherwise design-day
        # simulations (EXTENDED, default; already zone-aware internally —
        # see simulation.design) or the static estimate summed across zones
        if config.sizing == "design_day":
            design_h = config.heating_max_power or design_heating_power(
                building, weather, config
            )
            design_c = abs(config.cooling_max_power or design_cooling_power(
                building, weather, config
            ))
        else:
            static_h = static_c = 0.0
            for model in models:
                h, c = _design_powers(model, weather)
                static_h += h
                static_c += c
            design_h = config.heating_max_power or static_h
            design_c = abs(config.cooling_max_power or -static_c)
        heating_sys.set_capacity(design_h)
        cooling_sys.set_capacity(design_c)
    else:
        heating_sys = IdealLoad()
        cooling_sys = IdealLoad()
    sigma_h = heating_sys.sigma(models[0].n_sigma)
    sigma_c = cooling_sys.sigma(models[0].n_sigma)

    # roof PV, when declared in the GeoJSON "Solar technologies" attribute
    # (sized from the zone that owns the Roof surface)
    pv_production = None
    if config.plants and "pv" in building.geometry.solar_technologies.lower():
        pv_production = PVSystem(models[roof_idx].zone).production(
            weather.df["temp_air"].to_numpy()
        )

    index = weather.df.index
    heating_on = season_mask(index, config.heating_season)
    cooling_on = season_mask(index, config.cooling_season)
    t_ext = weather.df["temp_air"].to_numpy()

    n = weather.n_steps
    out = {
        k: np.zeros(n)
        for k in (
            "air_temperature",
            "operative_temperature",
            "mean_radiant_temperature",
            "relative_humidity",
            "sensible_load",
            "latent_load",
            "ahu_sensible_load",
            "ahu_latent_load",
            "heating_load",
            "cooling_load",
            "electric_plant",
            "gas",
            "district_heat",
            "other_fuel",
        )
    }
    zone_labels = [zi.geometry.zone_label for zi in building.zones]
    zone_volumes = [model.zone.volume for model in models]
    total_volume = sum(zone_volumes) or 1.0
    zone_out = (
        [{k: np.zeros(n) for k in _PER_ZONE_KEYS} for _ in range(n_zones)]
        if n_zones > 1
        else None
    )

    dhw_per_zone = [
        model.zone.dhw_demand if model.zone.dhw_demand.size else np.zeros(n) for model in models
    ]
    dhw = sum(dhw_per_zone)

    # DHW storage tank between generator and draw-off (EXTENDED), sized from
    # the combined, whole-building draw-off — one physical tank/generator
    # serves every zone, as in the retained reference.
    tank = None
    if config.plants and config.dhw_tank and dhw.size and dhw.max() > 0.0:
        tank = DhwTank.autosize(dhw, weather.timestep_seconds)
        heating_sys.dhw_tank = tank
    tank_temperature = np.zeros(n) if tank is not None else None

    # EXTENDED: solar thermal collectors offset the DHW demand ("ST" tag),
    # sized from the zone that owns the Roof surface, against the combined
    # whole-building DHW demand.
    st_useful = np.zeros(n)
    if config.plants and "st" in building.geometry.solar_technologies.lower() and dhw.max() > 0.0:
        daily_dhw_kwh = float(dhw.mean()) * 24.0 / 1000.0
        collector = SolarThermalCollector(models[roof_idx].zone, weather, daily_dhw_kwh)
        st_useful = np.minimum(collector.production(t_ext), dhw)
    dhw_to_plant = dhw - st_useful
    nat_vent_ach = np.zeros(n)

    for t in range(n):
        # sensible-only heat/cool split (matches the `sensible_load` column
        # semantics), bucketed per zone BEFORE summing so a zone heating
        # while another cools in the same step is not netted to zero
        heat_bucket = 0.0
        cool_bucket = 0.0
        # AHU-inclusive load actually fed to the shared plant this step
        plant_heat = 0.0
        plant_cool = 0.0
        air_t_sum = 0.0
        top_sum = 0.0
        tmr_sum = 0.0
        air_rh_sum = 0.0
        sens_sum = 0.0
        lat_sum = 0.0
        ahu_s_sum = 0.0
        ahu_l_sum = 0.0
        ahu_e_sum = 0.0
        nat_ach_weighted = 0.0
        for i, model in enumerate(models):
            res = model.solve_timestep(
                t, bool(heating_on[t]), bool(cooling_on[t]), sigma_h, sigma_c
            )
            z_heat = max(res.sensible_load, 0.0)
            z_cool = min(res.sensible_load, 0.0)
            heat_bucket += z_heat
            cool_bucket += z_cool
            if config.plants:
                # zone heating + AHU heating coil (incl. reheat) +
                # humidification
                plant_heat += z_heat + res.ahu_heating_coil_load + max(
                    res.ahu_latent_load, 0.0
                )
                # zone cooling + AHU cooling coil (incl. dehumidification) +
                # zone/AHU latent cooling
                plant_cool += (
                    z_cool
                    + min(res.latent_load, 0.0)
                    + res.ahu_cooling_coil_load
                    + min(res.ahu_latent_load, 0.0)
                )
            air_t_sum += res.air_temperature
            top_sum += res.operative_temperature
            tmr_sum += res.mean_radiant_temperature
            air_rh_sum += res.relative_humidity
            sens_sum += res.sensible_load
            lat_sum += res.latent_load
            ahu_s_sum += res.ahu_sensible_load
            ahu_l_sum += res.ahu_latent_load
            ahu_e_sum += res.ahu_electric
            nat_ach_weighted += res.natural_ventilation_ach * zone_volumes[i]
            if zone_out is not None:
                zo = zone_out[i]
                zo["air_temperature"][t] = res.air_temperature
                zo["operative_temperature"][t] = res.operative_temperature
                zo["mean_radiant_temperature"][t] = res.mean_radiant_temperature
                zo["relative_humidity"][t] = res.relative_humidity
                zo["sensible_load"][t] = res.sensible_load
                zo["latent_load"][t] = res.latent_load
                zo["ahu_sensible_load"][t] = res.ahu_sensible_load
                zo["ahu_latent_load"][t] = res.ahu_latent_load
                zo["heating_load"][t] = z_heat
                zo["cooling_load"][t] = z_cool
                zo["natural_ventilation_ach"][t] = res.natural_ventilation_ach

        out["air_temperature"][t] = air_t_sum / n_zones
        out["operative_temperature"][t] = top_sum / n_zones
        out["mean_radiant_temperature"][t] = tmr_sum / n_zones
        out["relative_humidity"][t] = air_rh_sum / n_zones
        out["sensible_load"][t] = sens_sum
        out["latent_load"][t] = lat_sum
        out["ahu_sensible_load"][t] = ahu_s_sum
        out["ahu_latent_load"][t] = ahu_l_sum
        out["heating_load"][t] = heat_bucket
        out["cooling_load"][t] = cool_bucket
        # single zone: exact value, no weighting arithmetic (keeps the
        # single-zone case bit-identical to before two-zone support existed)
        nat_vent_ach[t] = res.natural_ventilation_ach if n_zones == 1 else (
            nat_ach_weighted / total_volume
        )

        if config.plants:
            heat = heating_sys.solve(plant_heat, float(t_ext[t]), dhw=float(dhw_to_plant[t]))
            cool = cooling_sys.solve(plant_cool, float(t_ext[t]))
            out["electric_plant"][t] = heat.electric + cool.electric + ahu_e_sum
            out["gas"][t] = heat.gas + cool.gas
            out["district_heat"][t] = heat.district_heat + cool.district_heat
            out["other_fuel"][t] = heat.other_fuel + cool.other_fuel
            if tank_temperature is not None:
                tank_temperature[t] = tank.temperature

    df = pd.DataFrame(out, index=index)
    df["dhw_demand"] = dhw
    df["natural_ventilation_ach"] = nat_vent_ach
    df["electric_appliances"] = sum(model.zone.electric_load for model in models)
    if zone_out is not None:
        for i, label in enumerate(zone_labels):
            zo = zone_out[i]
            for key, arr in zo.items():
                df[f"zone_{label}_{key}"] = arr
            df[f"zone_{label}_dhw_demand"] = dhw_per_zone[i]
            df[f"zone_{label}_electric_appliances"] = models[i].zone.electric_load
    if config.plants:
        df["pv_production"] = pv_production if pv_production is not None else 0.0
        df["solar_thermal_production"] = st_useful
        if tank_temperature is not None:
            df["dhw_tank_temperature"] = tank_temperature
        # PV battery dispatch and grid exchange (EXTENDED)
        if config.pv_battery and pv_production is not None:
            dt_hours = weather.timestep_seconds / 3600.0
            electric_load = (
                df["electric_plant"].to_numpy() + df["electric_appliances"].to_numpy()
            )
            flows = Battery().dispatch(pv_production, electric_load, dt_hours)
            df["battery_soc"] = flows["soc"]
            df["grid_import"] = flows["from_grid"]
            df["grid_export"] = flows["to_grid"]
            df["pv_self_consumed"] = flows["direct_solar"] + flows["from_battery"]
    else:
        df = df.drop(columns=["electric_plant", "gas", "district_heat", "other_fuel"])
    df.attrs["warnings"] = run_warnings
    return df


def _run_building_task(
    args: tuple[BuildingInput, WeatherData, SimulationConfig, dict | None],
) -> tuple[str, pd.DataFrame]:
    """Module-level worker for process-based parallelism (picklable)."""
    building, weather, config, templates = args
    return building.name, run_building(building, weather, config, system_templates=templates)


def run_portfolio(
    district: DistrictInput,
    config: SimulationConfig,
    parallel: bool = False,
    max_workers: int | None = None,
) -> dict[str, pd.DataFrame]:
    """Simulate every building of a district/portfolio (FR-02, FR-04).

    Parameters
    ----------
    district : DistrictInput
        Preprocessed district (shared weather + building inputs).
    config : SimulationConfig
        Run settings applied to all buildings.
    parallel : bool
        Use a process pool. Worth it for large portfolios; for a handful of
        buildings the process start-up outweighs the gain.
    max_workers : int, optional
        Process pool size (default: CPU count).

    Returns
    -------
    dict
        Building name → results DataFrame (see :func:`run_building`).
    """
    templates = district.system_templates
    if not parallel:
        return {
            b.name: run_building(b, district.weather, config, system_templates=templates)
            for b in district.buildings
        }
    tasks = [(b, district.weather, config, templates) for b in district.buildings]
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        return dict(pool.map(_run_building_task, tasks))


def run_batch(
    district: DistrictInput,
    configs: dict[str, SimulationConfig],
    parallel: bool = False,
    max_workers: int | None = None,
) -> dict[str, dict[str, pd.DataFrame]]:
    """Run several model configurations over the same district (FR-03).

    Parameters
    ----------
    district : DistrictInput
        Preprocessed district.
    configs : dict
        Label → :class:`SimulationConfig` (e.g. ``{"5R1C": ..., "7R2C": ...}``).
    parallel, max_workers
        Passed to :func:`run_portfolio`.

    Returns
    -------
    dict
        Label → (building name → results DataFrame).
    """
    return {
        label: run_portfolio(district, cfg, parallel=parallel, max_workers=max_workers)
        for label, cfg in configs.items()
    }
