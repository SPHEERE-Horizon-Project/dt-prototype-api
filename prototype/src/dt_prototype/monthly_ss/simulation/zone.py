"""Build the QSS-relevant zone representation from preprocessed input."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dt_prototype.common.constants import AIR_DENSITY
from dt_prototype.common.preprocessing.archetypes import ConstructionSpec, WindowSpec
from dt_prototype.common.preprocessing.building_input import BuildingInput
from dt_prototype.common.preprocessing.weather import WeatherData
from dt_prototype.common.surface_boundaries import is_external_surface, validate_boundary_condition

_SKY_VIEW_FACTOR = {90.0: 0.5, 0.0: 1.0}


@dataclass
class ZoneSurface:
    surface_type: str
    gross_area: float
    opaque_area: float
    glazed_area: float
    azimuth: float
    tilt: float
    construction: ConstructionSpec
    window: WindowSpec | None = None
    poa_global: np.ndarray | None = None
    poa_direct: np.ndarray | None = None
    boundary_condition: str = "auto"

    def __post_init__(self) -> None:
        validate_boundary_condition(self.boundary_condition)

    @property
    def sky_view_factor(self) -> float:
        return _SKY_VIEW_FACTOR.get(self.tilt, 0.5)

    @property
    def is_external(self) -> bool:
        return is_external_surface(self.surface_type, self.boundary_condition)


@dataclass
class Zone:
    name: str
    net_floor_area: float
    volume: float
    surfaces: list[ZoneSurface]
    gains_convective: np.ndarray
    gains_radiative: np.ndarray
    heating_setpoint: np.ndarray
    cooling_setpoint: np.ndarray
    ventilation_mass_flow: np.ndarray
    infiltration_mass_flow: np.ndarray
    ahu: dict | None = None

    @property
    def h_r_ext(self) -> float:
        return 5.0

    @property
    def shgc_diffuse_factor(self) -> float:
        return 0.9


def build_zone(building: BuildingInput, weather: WeatherData, zone_index: int = 0) -> Zone:
    """Resolve envelope surfaces and hourly schedule arrays for a single zone."""
    input_zone = building.zones[zone_index]
    geometry, envelope, schedule = input_zone.geometry, input_zone.envelope, input_zone.schedule
    surfaces: list[ZoneSurface] = []
    for specification in geometry.surfaces:
        construction = envelope.constructions[specification.surface_type]
        glazed = specification.area * envelope.wwr if specification.surface_type == "ExtWall" else 0.0
        surface = ZoneSurface(
            specification.surface_type, specification.area, specification.area - glazed, glazed,
            specification.azimuth, specification.tilt, construction,
            envelope.window if glazed > 0.0 else None,
            boundary_condition=specification.boundary_condition,
        )
        # Retain physical roof irradiance independently of the thermal boundary.
        if (surface.is_external or specification.surface_type == "Roof") and specification.surface_type != "GroundFloor":
            global_column, direct_column = weather.irradiance_columns(specification.azimuth, specification.tilt)
            surface.poa_global = weather.df[global_column].to_numpy()
            surface.poa_direct = weather.df[direct_column].to_numpy()
        surfaces.append(surface)

    air_mass_per_ach = geometry.volume * AIR_DENSITY / 3600.0
    ventilation = (
        schedule.ventilation_flow_per_area * geometry.net_floor_area * AIR_DENSITY
        if schedule.ventilation_flow_per_area is not None
        else schedule.ventilation_ach * air_mass_per_ach
    )
    infiltration = (
        schedule.infiltration_ach * air_mass_per_ach
        if schedule.infiltration_ach is not None
        else np.full(weather.n_steps, envelope.infiltration_ach * air_mass_per_ach)
    )
    return Zone(
        geometry.name, geometry.net_floor_area, geometry.volume, surfaces,
        schedule.internal_gain_convective * geometry.net_floor_area,
        schedule.internal_gain_radiative * geometry.net_floor_area,
        schedule.heating_setpoint, schedule.cooling_setpoint, ventilation, infiltration, schedule.ahu,
    )
