"""Thermal zone assembly: turns a serialised :class:`BuildingInput` into the
per-surface and per-timestep quantities shared by all thermal models.

Migrated from the data-preparation parts of ``reference_building.thermal_zone``
and ``reference_building.surface`` (each building is modelled as one thermal
zone, as in the retained reference's UBEM workflow).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from dt_prototype.common.constants import (
    AIR_DENSITY,
    AIR_SPECIFIC_HEAT,
    DHW_TARGET_TEMPERATURE,
    EXTERNAL_SURFACE_TYPES,
    WATER_DENSITY,
    WATER_SPECIFIC_HEAT,
)
from dt_prototype.common.preprocessing.archetypes import ConstructionSpec, WindowSpec
from dt_prototype.common.preprocessing.building_input import BuildingInput
from dt_prototype.common.preprocessing.weather import WeatherData

# Sky view factors (the retained reference surface._sky_view_factor): vertical walls see half
# of the sky vault, horizontal roofs see all of it.
_SKY_VIEW_FACTOR = {90.0: 0.5, 0.0: 1.0}
# External radiative heat transfer coefficient [W/(m2 K)]
_H_R_EXT = 5.0
# Fraction of the window SHGC entering as long-wave radiative / convective
# heat (simplified split of the retained reference's separate rad/conv SHGC profiles)
_SHGC_RADIATIVE_FRACTION = 0.9
# Diffuse-incidence correction on the SHGC (replaces angular SHGC splines)
_SHGC_DIFFUSE_FACTOR = 0.9


@dataclass
class ZoneSurface:
    """One surface of the zone with resolved construction and irradiance."""

    surface_type: str
    gross_area: float  # [m2]
    opaque_area: float  # [m2]
    glazed_area: float  # [m2]
    azimuth: float  # [deg] compass
    tilt: float  # [deg]
    construction: ConstructionSpec
    window: WindowSpec | None = None
    # plane-of-array irradiance series [W/m2] (external surfaces only)
    poa_global: np.ndarray | None = None
    poa_direct: np.ndarray | None = None

    @property
    def sky_view_factor(self) -> float:
        """View factor to the sky vault [-]."""
        return _SKY_VIEW_FACTOR.get(self.tilt, 0.5)

    @property
    def is_external(self) -> bool:
        """True for surfaces exchanging heat with the environment."""
        return self.surface_type in EXTERNAL_SURFACE_TYPES


@dataclass
class Zone:
    """Simulation-ready thermal zone: resolved surfaces + per-timestep arrays.

    All arrays have length ``weather.n_steps``. Gains are total zone values
    [W] (schedule intensities multiplied by the net floor area).
    """

    name: str
    net_floor_area: float  # [m2]
    volume: float  # [m3]
    surfaces: list[ZoneSurface]
    # internal gains [W]
    gains_convective: np.ndarray
    gains_radiative: np.ndarray
    gains_latent: np.ndarray
    electric_load: np.ndarray  # appliances + lighting [W]
    # setpoints
    heating_setpoint: np.ndarray  # [°C]
    cooling_setpoint: np.ndarray  # [°C]
    humidity_setpoint_low: np.ndarray  # RH [0-1]
    humidity_setpoint_high: np.ndarray  # RH [0-1]
    # air exchange
    ventilation_mass_flow: np.ndarray  # [kg/s]
    infiltration_mass_flow: np.ndarray  # [kg/s]
    # domestic hot water thermal demand [W] (FR: DHW reintroduced)
    dhw_demand: np.ndarray = field(default_factory=lambda: np.zeros(0))
    heating_system_name: str = "IdealLoad"
    cooling_system_name: str = "IdealLoad"
    solar_technologies: str = ""
    # AHU parameters (dict from the end-use schedule) or None
    ahu: dict | None = None
    # EXTENDED: window-opening free-cooling parameters or None
    natural_ventilation: dict | None = None

    @property
    def air_thermal_capacity(self) -> float:
        """Heat capacity of the zone air [J/K]."""
        return self.volume * AIR_DENSITY * AIR_SPECIFIC_HEAT

    @property
    def shgc_radiative(self) -> float:
        """Radiative share of the window solar gain [-]."""
        return _SHGC_RADIATIVE_FRACTION

    @property
    def h_r_ext(self) -> float:
        """External radiative film coefficient [W/(m2 K)]."""
        return _H_R_EXT

    @property
    def shgc_diffuse_factor(self) -> float:
        """SHGC correction applied to diffuse irradiance [-]."""
        return _SHGC_DIFFUSE_FACTOR


def build_zone(building: BuildingInput, weather: WeatherData, zone_index: int = 0) -> Zone:
    """Assemble one thermal zone of a building (FR-01).

    Applies the envelope archetype to the zone's geometry: splits external
    walls into opaque and glazed areas via the window-to-wall ratio, binds
    the element constructions, attaches plane-of-array irradiance series to
    external surfaces, and expands the zone's own schedule to total-zone
    gains. ``zone_index`` selects which of the building's one or two zones
    (see ``preprocessing.geometry``'s two-zone convention) to build; it
    defaults to 0, the only zone of a single-zone building.

    Parameters
    ----------
    building : BuildingInput
        Serialised preprocessing output.
    weather : WeatherData
        Processed weather with irradiance bins.
    zone_index : int
        Index into ``building.zones`` (0 = single/upper zone, 1 = lower
        zone of a two-zone building).

    Returns
    -------
    Zone
    """
    zone_input = building.zones[zone_index]
    geometry = zone_input.geometry
    envelope = zone_input.envelope
    schedule = zone_input.schedule

    surfaces: list[ZoneSurface] = []
    for spec in geometry.surfaces:
        construction = envelope.constructions[spec.surface_type]
        glazed = spec.area * envelope.wwr if spec.surface_type == "ExtWall" else 0.0
        surface = ZoneSurface(
            surface_type=spec.surface_type,
            gross_area=spec.area,
            opaque_area=spec.area - glazed,
            glazed_area=glazed,
            azimuth=spec.azimuth,
            tilt=spec.tilt,
            construction=construction,
            window=envelope.window if glazed > 0.0 else None,
        )
        if surface.is_external and spec.surface_type != "GroundFloor":
            col_glob, col_dir = weather.irradiance_columns(spec.azimuth, spec.tilt)
            surface.poa_global = weather.df[col_glob].to_numpy()
            surface.poa_direct = weather.df[col_dir].to_numpy()
        surfaces.append(surface)

    nfa = geometry.net_floor_area
    air_mass_per_ach = geometry.volume * AIR_DENSITY / 3600.0  # [kg/s per 1/h]
    # DHW thermal demand [W]: draw-off volume heated from the aqueduct inlet
    # (≈ annual mean outdoor temperature, as in the retained reference) to the target temp.
    inlet_temp = float(weather.df["temp_air"].mean())
    dhw_dt = max(DHW_TARGET_TEMPERATURE - inlet_temp, 0.0)
    dhw_demand = schedule.dhw_volume_flow * nfa * WATER_DENSITY * WATER_SPECIFIC_HEAT * dhw_dt
    return Zone(
        name=geometry.name,
        net_floor_area=nfa,
        volume=geometry.volume,
        surfaces=surfaces,
        gains_convective=schedule.internal_gain_convective * nfa,
        gains_radiative=schedule.internal_gain_radiative * nfa,
        gains_latent=schedule.internal_gain_latent * nfa,
        electric_load=schedule.electric_load * nfa,
        heating_setpoint=schedule.heating_setpoint,
        cooling_setpoint=schedule.cooling_setpoint,
        humidity_setpoint_low=schedule.humidity_setpoint_low,
        humidity_setpoint_high=schedule.humidity_setpoint_high,
        # the retained reference-native ventilation [m3/(s m2)] converts exactly here, where
        # the real floor area is known; otherwise the air-change form is used
        ventilation_mass_flow=(
            schedule.ventilation_flow_per_area * nfa * AIR_DENSITY
            if schedule.ventilation_flow_per_area is not None
            else schedule.ventilation_ach * air_mass_per_ach
        ),
        # an hourly infiltration schedule (the retained reference form) overrides the
        # envelope archetype's single airtightness value
        infiltration_mass_flow=(
            schedule.infiltration_ach * air_mass_per_ach
            if schedule.infiltration_ach is not None
            else np.full(weather.n_steps, envelope.infiltration_ach * air_mass_per_ach)
        ),
        dhw_demand=dhw_demand,
        # heating/cooling system and solar technologies are building-level
        # (shared by every zone), so they come from building.geometry, not
        # this zone's own ZoneGeometry.
        heating_system_name=building.geometry.heating_system,
        cooling_system_name=building.geometry.cooling_system,
        solar_technologies=building.geometry.solar_technologies,
        ahu=schedule.ahu,
        natural_ventilation=schedule.natural_ventilation,
    )
