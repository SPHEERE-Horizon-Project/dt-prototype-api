"""Design-day plant sizing (EXTENDED).

Migration of the retained reference's design-day approach (``City.designdays`` /
``ThermalZone.design_heating_load`` / ``design_sensible_cooling_load``):
instead of a static steady-state estimate, the building's own thermal model
is run to regime on a design day and the peak load is taken.

- **Heating design day**: coldest annual outdoor temperature held constant,
  no sun, no internal gains, maximum set point and air flows — run for
  ``DESIGN_DAYS_TO_REGIME`` days, peak heating load of the last day.
- **Cooling design day**: the hottest real day of the weather year (maximum
  daily mean temperature), with its actual solar irradiance and the
  building's real schedules, repeated to regime — peak cooling load of the
  last day.

Both peaks carry a safety factor (the retained reference uses 1.2).
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from dt_prototype.common.preprocessing.building_input import BuildingInput, ZoneInput
from dt_prototype.common.preprocessing.weather import WeatherData
from dt_prototype.dynamic.simulation.config import SimulationConfig

DESIGN_SAFETY_FACTOR = 1.2
DESIGN_DAYS_TO_REGIME = 3


def _constant_weather(template: WeatherData, t_ext: float, n_steps: int) -> WeatherData:
    """Constant-condition weather (no sun) built on the template's columns."""
    index = pd.date_range("2023-01-01", periods=n_steps, freq=template.df.index.freq or "h")
    df = pd.DataFrame(0.0, index=index, columns=template.df.columns)
    df["temp_air"] = t_ext
    df["relative_humidity"] = 0.8
    df["pressure"] = 101325.0
    df["specific_humidity"] = 0.003
    return dataclasses.replace(template, df=df)


def _tiled_day_weather(template: WeatherData, day_start: int, n_days: int) -> WeatherData:
    """Weather made of one real day (rows from ``day_start``) tiled n times."""
    steps_day = 24 * template.time_steps_per_hour
    day = template.df.iloc[day_start : day_start + steps_day]
    df = pd.concat([day] * n_days, ignore_index=True)
    df.index = pd.date_range("2023-06-01", periods=len(df), freq=template.df.index.freq or "h")
    return dataclasses.replace(template, df=df)


def _schedule_slice_zone(zone_input: ZoneInput, day_start: int, steps_day: int, n_days: int) -> ZoneInput:
    """Zone copy whose schedule arrays are one day tiled ``n_days`` times."""
    schedule = zone_input.schedule
    replacements = {}
    for f in dataclasses.fields(schedule):
        value = getattr(schedule, f.name)
        if isinstance(value, np.ndarray) and value.size >= day_start + steps_day:
            replacements[f.name] = np.tile(value[day_start : day_start + steps_day], n_days)
    return dataclasses.replace(zone_input, schedule=dataclasses.replace(schedule, **replacements))


def _constant_schedule_zone(zone_input: ZoneInput, n_steps: int) -> ZoneInput:
    """Zone copy with design-heating schedules: no gains, no DHW, maximum
    set point and ventilation held constant."""
    schedule = zone_input.schedule
    replacements = {}
    for f in dataclasses.fields(schedule):
        value = getattr(schedule, f.name)
        if not isinstance(value, np.ndarray) or value.size == 0:
            continue
        if f.name == "heating_setpoint":
            replacements[f.name] = np.full(n_steps, float(value.max()))
        elif f.name == "cooling_setpoint":
            replacements[f.name] = np.full(n_steps, 50.0)  # never active
        elif f.name == "ventilation_ach":
            replacements[f.name] = np.full(n_steps, float(value.max()))
        elif f.name in ("humidity_setpoint_low", "humidity_setpoint_high"):
            replacements[f.name] = np.full(n_steps, float(value.mean()))
        else:  # gains, electric, dhw → zero (design condition)
            replacements[f.name] = np.zeros(n_steps)
    return dataclasses.replace(zone_input, schedule=dataclasses.replace(schedule, **replacements))


def _zone_only_building(building: BuildingInput, zone_input: ZoneInput) -> BuildingInput:
    """A design-day ``BuildingInput`` exposing exactly one zone, so
    ``ThermalModel(..., zone_index=0)`` picks it up. ``building.geometry``
    is kept as-is: the design-day mini-simulation of a single zone still
    needs its building-level heating/cooling-system/solar-technologies
    fields (read from ``BuildingInput.geometry``, not from ``.zones``)."""
    return dataclasses.replace(building, zones=[zone_input])


def design_heating_power(
    building: BuildingInput, weather: WeatherData, config: SimulationConfig
) -> float:
    """Design heating power [W] from a heating design-day simulation.

    A two-zone building (see ``preprocessing.geometry``'s convention) is
    sized zone by zone — one mini design-day simulation per zone, on its
    own RC network and schedule, exactly like the shared plant's per-zone
    real-time run in ``simulation.runner`` — and the peaks are summed
    (the retained reference sizes its single shared plant from the sum of both zones'
    design loads too). For a single-zone building this reduces to the
    original single-model sizing.

    Parameters
    ----------
    building : BuildingInput
        Building to size.
    weather : WeatherData
        Annual weather (provides the design outdoor temperature).
    config : SimulationConfig
        Run settings (selects the thermal model).

    Returns
    -------
    float
        Sum of each zone's peak heating load x safety factor, plus one
        combined DHW peak (the whole-building draw-off, not summed
        per-zone peaks, since one shared generator/tank serves every zone).
    """
    from dt_prototype.dynamic.simulation.model_base import get_model_class  # avoid cycle
    from dt_prototype.dynamic.simulation.zone import build_zone

    steps_day = 24 * weather.time_steps_per_hour
    n = steps_day * DESIGN_DAYS_TO_REGIME
    t_design = float(weather.df["temp_air"].min())
    design_weather = _constant_weather(weather, t_design, n)

    total_peak = 0.0
    for zone_input in building.zones:
        design_zone = _constant_schedule_zone(zone_input, n)
        design_building = _zone_only_building(building, design_zone)
        model = get_model_class(config.model)(
            design_building, design_weather, dataclasses.replace(config, latent=False),
            zone_index=0,
        )
        sigma = (0.0,) * (model.n_sigma - 1) + (1.0,)
        peak = 0.0
        for t in range(n):
            result = model.solve_timestep(t, True, False, sigma, sigma)
            if t >= n - steps_day:  # last day only (regime reached)
                peak = max(peak, result.sensible_load + result.ahu_sensible_load)
        total_peak += peak

    combined_dhw = sum(
        build_zone(building, weather, i).dhw_demand for i in range(len(building.zones))
    )
    dhw_peak = float(combined_dhw.max()) if combined_dhw.size else 0.0
    return total_peak * DESIGN_SAFETY_FACTOR + dhw_peak


def design_cooling_power(
    building: BuildingInput, weather: WeatherData, config: SimulationConfig
) -> float:
    """Design cooling power [W] (positive magnitude) from a cooling
    design-day simulation on the hottest real day of the weather year.

    A two-zone building is sized zone by zone and the peaks summed, as in
    :func:`design_heating_power` — see its docstring for the rationale.

    Parameters
    ----------
    building : BuildingInput
        Building to size.
    weather : WeatherData
        Annual weather (provides the hottest day, with its real solar).
    config : SimulationConfig
        Run settings (selects the thermal model).

    Returns
    -------
    float
        Sum of each zone's peak cooling load magnitude, x safety factor
        (incl. latent and AHU cooling coil).
    """
    from dt_prototype.dynamic.simulation.model_base import get_model_class  # avoid cycle

    steps_day = 24 * weather.time_steps_per_hour
    daily_means = weather.df["temp_air"].to_numpy()[: 365 * steps_day].reshape(365, steps_day)
    hottest_day = int(np.argmax(daily_means.mean(axis=1)))
    day_start = hottest_day * steps_day
    n = steps_day * DESIGN_DAYS_TO_REGIME

    design_weather = _tiled_day_weather(weather, day_start, DESIGN_DAYS_TO_REGIME)

    total_peak = 0.0
    for zone_input in building.zones:
        design_zone = _schedule_slice_zone(zone_input, day_start, steps_day, DESIGN_DAYS_TO_REGIME)
        design_building = _zone_only_building(building, design_zone)
        model = get_model_class(config.model)(
            design_building, design_weather, config, zone_index=0
        )
        sigma = (0.0,) * (model.n_sigma - 1) + (1.0,)
        peak = 0.0
        for t in range(n):
            result = model.solve_timestep(t, False, True, sigma, sigma)
            if t >= n - steps_day:  # last day only (regime reached)
                cooling = (
                    min(result.sensible_load, 0.0)
                    + min(result.latent_load, 0.0)
                    + min(result.ahu_sensible_load, 0.0)
                    + min(result.ahu_latent_load, 0.0)
                )
                peak = max(peak, -cooling)
        total_peak += peak
    return max(total_peak * DESIGN_SAFETY_FACTOR, 1000.0)
