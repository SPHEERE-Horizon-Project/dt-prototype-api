"""5R1C parameters and solar gains needed by the monthly ISO 13790 method."""

from __future__ import annotations

import numpy as np

from dt_prototype.common.preprocessing.building_input import BuildingInput
from dt_prototype.common.preprocessing.weather import WeatherData
from dt_prototype.monthly.simulation.config import SimulationConfig
from dt_prototype.monthly.simulation.wall_params import iso13790_kappa
from dt_prototype.monthly.simulation.zone import build_zone

_H_TR_MS = 9.1


class Model5R1C:
    """Static 5R1C parametrisation; it intentionally has no hourly solver."""

    def __init__(
        self,
        building: BuildingInput,
        weather: WeatherData,
        config: SimulationConfig,
        zone_index: int = 0,
    ) -> None:
        self.zone = build_zone(building, weather, zone_index)
        self.weather = weather
        self.config = config
        self._compute_parameters()
        self._compute_solar_gains()

    def _compute_parameters(self) -> None:
        cm = den_am = atot = htr_op = htr_w = 0.0
        for surface in self.zone.surfaces:
            k_int, k_ext = iso13790_kappa(surface.construction)
            kappa = k_ext if surface.surface_type == "IntFloor" else k_int
            cm += surface.opaque_area * kappa
            den_am += surface.opaque_area * kappa**2
            atot += surface.gross_area
            if surface.is_external:
                htr_op += surface.opaque_area * surface.construction.u_value
                if surface.glazed_area > 0.0 and surface.window is not None:
                    htr_w += surface.glazed_area * surface.window.u_value
        self.Cm = cm
        self.Am = cm**2 / den_am
        self.Atot = atot
        self.Htr_op = htr_op
        self.Htr_w = htr_w
        self.Htr_ms = self.Am * _H_TR_MS
        self.UA_tot = htr_op + htr_w

    def _compute_solar_gains(self) -> None:
        phi_sol = np.zeros(self.weather.n_steps)
        for surface in self.zone.surfaces:
            if surface.surface_type not in ("ExtWall", "Roof"):
                continue
            direct = surface.poa_direct
            diffuse = surface.poa_global - direct
            if surface.glazed_area > 0.0 and surface.window is not None:
                window = surface.window
                effective_area = (1.0 - window.frame_factor) * surface.glazed_area * window.shading_coef
                phi_sol += window.shgc * effective_area * (
                    direct + self.zone.shgc_diffuse_factor * diffuse
                )
            construction = surface.construction
            phi_sol += (
                surface.poa_global * construction.solar_absorptance * construction.r_se
                * construction.u_value_net * surface.opaque_area
                - surface.sky_view_factor * construction.r_se * construction.u_value_net
                * surface.opaque_area * self.zone.h_r_ext * self.weather.average_dt_air_sky
            )
        self.phi_sol = phi_sol
