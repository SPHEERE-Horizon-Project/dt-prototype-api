"""Roof-mounted solar thermal collectors for DHW (EXTENDED).

Port of ``reference_building.solar_thermal_system.SolarThermal_Collector``:
flat-plate collectors sized per the BOSCH manual rule (scaled by the site's
annual irradiation relative to Albany, NY), with the same linear efficiency
curve corrected for the operating temperature lift. The produced heat
offsets the domestic hot water demand; surplus is discarded (no seasonal
storage — extension point).
"""

from __future__ import annotations

import numpy as np

from dt_prototype.common.preprocessing.weather import WeatherData
from dt_prototype.dynamic.simulation.zone import Zone

# Collector efficiency curve (the retained reference defaults)
_EFFICIENCY_INTERCEPT = 0.8  # optical efficiency [-]
_EFFICIENCY_SLOPE = -0.013  # [1/K] (per W/m2 of irradiance)
# BOSCH-manual sizing rule: m2 of collector per litre/day of DHW at Albany, NY
_SIZING_SLOPE = 0.0104
_ALBANY_ANNUAL_IRRADIATION = 1569.0  # [kWh/m2 year]
# nominal temperature lift used to convert DHW energy to draw volume [K]
_DHW_NOMINAL_LIFT = 33.0  # 45 °C delivery - 12 °C aqueduct
_WATER_SPECIFIC_HEAT = 4186.0  # [J/(kg K)]


class SolarThermalCollector:
    """Flat-plate solar thermal field on the roof surfaces of a zone.

    Parameters
    ----------
    zone : Zone
        Assembled zone (roof surfaces provide area and irradiance).
    weather : WeatherData
        Processed weather (annual irradiation drives the sizing).
    daily_dhw_kwh : float
        Average daily DHW energy demand [kWh/day] (sizing input).
    fluid_inlet_temperature : float
        Collector inlet (aqueduct) temperature [°C].
    fluid_max_outlet_temperature : float
        Design maximum outlet temperature [°C].
    max_coverage_factor : float
        Upper bound on the roof fraction covered by collectors (the retained reference
        default 5%).
    """

    def __init__(
        self,
        zone: Zone,
        weather: WeatherData,
        daily_dhw_kwh: float,
        fluid_inlet_temperature: float = 12.0,
        fluid_max_outlet_temperature: float = 90.0,
        max_coverage_factor: float = 0.05,
    ) -> None:
        self.t_in = fluid_inlet_temperature
        self.t_out_max = fluid_max_outlet_temperature
        self._roofs = [
            s for s in zone.surfaces if s.surface_type == "Roof" and s.poa_global is not None
        ]
        total_roof = sum(r.gross_area for r in self._roofs)

        # BOSCH sizing rule (per litre/day) scaled by the site / Albany
        # irradiation ratio; DHW energy converted to draw volume at the
        # nominal temperature lift
        dt_hours = weather.timestep_seconds / 3600.0
        annual_irradiation = float(weather.df["ghi"].sum()) * dt_hours / 1000.0  # [kWh/m2]
        daily_litres = daily_dhw_kwh * 3.6e6 / (_WATER_SPECIFIC_HEAT * _DHW_NOMINAL_LIFT)
        sized_area = (
            _SIZING_SLOPE * (_ALBANY_ANNUAL_IRRADIATION / max(annual_irradiation, 1.0))
            * daily_litres
        )
        self.coverage_factor = (
            min(sized_area / total_roof, max_coverage_factor) if total_roof > 0 else 0.0
        )
        self.collector_area = self.coverage_factor * total_roof

    def production(self, t_ext: np.ndarray) -> np.ndarray:
        """Collected heat series [W] (the retained reference efficiency formulation).

        Parameters
        ----------
        t_ext : numpy.ndarray
            Outdoor air temperature [°C].

        Returns
        -------
        numpy.ndarray
            Useful collected heat [W], clipped at zero.
        """
        a, b = _EFFICIENCY_INTERCEPT, _EFFICIENCY_SLOPE
        total = np.zeros_like(t_ext, dtype=float)
        for roof in self._roofs:
            poa = roof.poa_global
            positive = poa[poa > 0.0]
            if positive.size == 0:
                continue
            g_design = float(np.quantile(positive, 0.9))
            eff_design = a + b * (0.5 * (self.t_in + self.t_out_max) - t_ext)
            numerator = a + b * (self.t_in - t_ext)
            denominator = 1.0 - 0.5 * b * poa / (g_design * eff_design) * (
                self.t_out_max - self.t_in
            )
            efficiency = numerator / denominator
            area = roof.gross_area * self.coverage_factor
            total += area * poa * efficiency
        return np.clip(total, 0.0, None)
