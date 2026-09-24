"""Roof-mounted photovoltaic production and battery storage (EXTENDED).

Simplified migration of ``reference_building.pv_system.PV_system``: the same
installed-capacity assumptions (400 W modules of 1.7 m2, default 45% roof
coverage) with the pvlib ADR efficiency model replaced by the standard
NOCT cell-temperature model with a linear temperature coefficient.

EXTENDED: the :class:`Battery` model is migrated from the retained reference
``PV_system.Battery`` / ``Battery_charge`` — same performance parameters,
same capacity-sizing rule (80th percentile of the rolling one-day deficit)
and the same charge/discharge state machine, vectorised where possible.
"""

from __future__ import annotations

import numpy as np

from dt_prototype.dynamic.simulation.zone import Zone

# Installed capacity assumptions (as in the retained reference)
_MODULE_POWER_STC = 400.0  # [W]
_MODULE_AREA = 1.7  # [m2]
_G_STC = 1000.0  # [W/m2]
# NOCT temperature model parameters
_NOCT = 45.0  # [°C]
_TEMP_COEFF = -0.004  # [1/K] relative power per K above 25 °C


class PVSystem:
    """PV array on the roof surfaces of a zone.

    Parameters
    ----------
    zone : Zone
        Assembled zone (roof surfaces provide area and irradiance).
    coverage_factor : float
        Fraction of the roof area covered by modules (the retained reference default 0.45).
    """

    def __init__(self, zone: Zone, coverage_factor: float = 0.45) -> None:
        self.coverage_factor = coverage_factor
        self._roofs = [
            s for s in zone.surfaces if s.surface_type == "Roof" and s.poa_global is not None
        ]

    def production(self, t_ext: np.ndarray) -> np.ndarray:
        """Electric production series [W].

        Parameters
        ----------
        t_ext : numpy.ndarray
            Outdoor air temperature [°C].

        Returns
        -------
        numpy.ndarray
            AC production [W] (inverter losses folded into the temperature
            derating; simplified).
        """
        total = np.zeros_like(t_ext, dtype=float)
        for roof in self._roofs:
            poa = roof.poa_global
            p_stc = roof.gross_area * self.coverage_factor / _MODULE_AREA * _MODULE_POWER_STC
            t_cell = t_ext + (_NOCT - 20.0) / 800.0 * poa
            eta_rel = 1.0 + _TEMP_COEFF * (t_cell - 25.0)
            total += p_stc * (poa / _G_STC) * np.clip(eta_rel, 0.0, None)
        return total


class Battery:
    """PV battery storage (port of the retained reference ``PV_system.Battery_charge``).

    Performance parameters are the retained reference's defaults; the usable capacity is
    sized from the 80th percentile of the rolling one-day electricity
    deficit (production minus load), as in the original.

    Parameters
    ----------
    charge_efficiency, discharge_efficiency : float
        Round-trip split efficiencies [-].
    max_charge, min_charge : float
        Usable state-of-charge window [0-1].
    initial_charge : float
        Initial state of charge [0-1].
    solar_save_days : int
        Length of the sizing window [days] (the retained reference ``days_of_solar_save``).
    """

    def __init__(
        self,
        charge_efficiency: float = 0.98,
        discharge_efficiency: float = 0.98,
        max_charge: float = 0.95,
        min_charge: float = 0.2,
        initial_charge: float = 0.6,
        solar_save_days: int = 1,
    ) -> None:
        self.charge_efficiency = charge_efficiency
        self.discharge_efficiency = discharge_efficiency
        self.max_charge = max_charge
        self.min_charge = min_charge
        self.initial_charge = initial_charge
        self.solar_save_days = solar_save_days
        self.capacity_wh: float = 0.0  # set by size()

    def size(self, pv: np.ndarray, load: np.ndarray, dt_hours: float) -> float:
        """Size the capacity [Wh] as the retained reference: 80th percentile of the rolling
        one-day minimum cumulative (load - production) energy balance.

        Parameters
        ----------
        pv, load : numpy.ndarray
            Production and electric load series [W].
        dt_hours : float
            Time step [h].

        Returns
        -------
        float
            Sized capacity [Wh] (0 when PV never exceeds the load).
        """
        window = max(1, int(round(self.solar_save_days * 24.0 / dt_hours)))
        deficit_wh = (load - pv) * dt_hours  # [Wh] per step
        n = len(deficit_wh)
        padded = np.concatenate([deficit_wh, np.zeros(window - 1)])
        cumsum = np.cumsum(np.concatenate([[0.0], padded]))
        # rolling window cumulative sums: shape (n, window)
        windows = np.lib.stride_tricks.sliding_window_view(cumsum, window + 1)[:n]
        rolling_min = (windows[:, 1:] - windows[:, [0]]).min(axis=1)
        rolling_min = np.clip(rolling_min, None, 0.0)
        self.capacity_wh = float(np.quantile(-rolling_min, 0.8))
        return self.capacity_wh

    def dispatch(
        self, pv: np.ndarray, load: np.ndarray, dt_hours: float
    ) -> dict[str, np.ndarray]:
        """Simulate the battery over the year (the retained reference state machine).

        Surplus production charges the battery (within the usable SOC
        window); deficits discharge it; the remainder is exchanged with the
        grid.

        Parameters
        ----------
        pv, load : numpy.ndarray
            Production and electric load series [W].
        dt_hours : float
            Time step [h].

        Returns
        -------
        dict of numpy.ndarray
            ``soc`` [0-1], and power series [W]: ``to_battery``,
            ``from_battery``, ``to_grid``, ``from_grid``,
            ``direct_solar`` (self-consumed production).
        """
        if self.capacity_wh == 0.0:
            self.size(pv, load, dt_hours)

        n = len(pv)
        balance_wh = (pv - load) * dt_hours  # surplus (+) / deficit (-) [Wh]
        # apply charge/discharge efficiencies (as the retained reference)
        flow = np.where(
            balance_wh > 0.0,
            balance_wh * self.charge_efficiency,
            balance_wh / self.discharge_efficiency,
        )
        max_wh = self.max_charge * self.capacity_wh
        min_wh = self.min_charge * self.capacity_wh

        state = np.zeros(n)
        change = np.zeros(n)
        level = self.initial_charge * self.capacity_wh
        for i in range(n):
            if i > 0:
                new = level + flow[i - 1]
                new = min(new, max_wh)
                if new < min_wh:
                    new = 0.0 if new < 0.0 else (min_wh if level >= min_wh else new)
                change[i] = new - level
                level = new
            state[i] = level

        charger = np.clip(flow, 0.0, None)
        discharger = np.clip(flow, None, 0.0)
        to_battery = np.clip(np.minimum(flow, change), 0.0, None)
        from_battery = np.abs(np.clip(np.maximum(flow, change), None, 0.0))
        to_grid = charger - to_battery
        from_grid = np.abs(discharger) - from_battery
        direct_solar = np.minimum(pv, load) * dt_hours

        soc = state / self.capacity_wh if self.capacity_wh > 0 else state
        return {
            "soc": soc,
            "to_battery": to_battery / dt_hours,
            "from_battery": from_battery / dt_hours,
            "to_grid": to_grid / dt_hours,
            "from_grid": from_grid / dt_hours,
            "direct_solar": direct_solar / dt_hours,
        }
