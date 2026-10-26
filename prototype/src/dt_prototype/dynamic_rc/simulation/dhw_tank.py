"""Domestic hot water storage tank (EXTENDED).

Migration of the DHW tank concept of the retained reference (``System.dhw_tank_solver`` /
``set_dhw_design_capacity_tank``): a fully mixed storage tank between the
heat generator and the draw-off. The generator charges the tank with a
thermostat dead band, so short draw-off peaks are served by storage and the
generator sees a smoothed, lower-peak load — which also permits smaller
design powers.

Energy balance of the fully mixed tank per time step:

    rho V c dT/dt = P_charge - P_draw - UA (T - T_ambient)
"""

from __future__ import annotations

import numpy as np

from dt_prototype.common.constants import WATER_DENSITY, WATER_SPECIFIC_HEAT


class DhwTank:
    """Fully mixed DHW storage tank with dead-band charge control.

    Parameters
    ----------
    volume : float
        Tank volume [m3].
    charge_power : float
        Generator charging power when active [W].
    timestep : float
        Simulation time step [s].
    set_temperature : float
        Storage set point [°C].
    deadband : float
        Thermostat dead band [K] (charge starts at set - deadband).
    ua : float
        Standing-loss coefficient [W/K].
    ambient_temperature : float
        Temperature of the room housing the tank [°C].
    """

    def __init__(
        self,
        volume: float,
        charge_power: float,
        timestep: float = 3600.0,
        set_temperature: float = 60.0,
        deadband: float = 5.0,
        ua: float = 1.5,
        ambient_temperature: float = 15.0,
    ) -> None:
        if volume <= 0.0 or charge_power <= 0.0:
            raise ValueError("DhwTank volume and charge_power must be positive")
        self.volume = volume
        self.charge_power = charge_power
        self.timestep = timestep
        self.set_temperature = set_temperature
        self.deadband = deadband
        self.ua = ua
        self.ambient_temperature = ambient_temperature
        self.temperature = set_temperature  # start charged
        self._charging = False
        self.capacity = WATER_DENSITY * WATER_SPECIFIC_HEAT * volume  # [J/K]

    @classmethod
    def autosize(cls, dhw_demand: np.ndarray, timestep: float) -> "DhwTank | None":
        """Size a tank from the annual DHW demand series [W].

        Storage covers ~50% of an average day's draw; the charging power is
        sized so a full day's energy is rechargeable in 8 hours. Returns
        None when there is no DHW demand.
        """
        steps_per_day = max(1, int(round(86400.0 / timestep)))
        daily_energy = float(dhw_demand.mean()) * 86400.0  # [J/day]
        if daily_energy <= 0.0:
            return None
        # store half a day's energy over a 45 K useful temperature swing
        volume = 0.5 * daily_energy / (WATER_DENSITY * WATER_SPECIFIC_HEAT * 45.0)
        volume = max(volume, 0.05)
        charge_power = max(daily_energy / (8.0 * 3600.0), 500.0)
        del steps_per_day
        return cls(volume=volume, charge_power=charge_power, timestep=timestep)

    def step(self, draw: float) -> float:
        """Advance the tank one time step.

        Parameters
        ----------
        draw : float
            DHW draw-off thermal power in this time step [W].

        Returns
        -------
        float
            Charging power requested from the generator [W] (0 when the
            thermostat is satisfied).
        """
        # dead-band thermostat on the storage temperature
        if self.temperature <= self.set_temperature - self.deadband:
            self._charging = True
        elif self.temperature >= self.set_temperature:
            self._charging = False
        charge = self.charge_power if self._charging else 0.0

        loss = self.ua * (self.temperature - self.ambient_temperature)
        self.temperature += (charge - draw - loss) * self.timestep / self.capacity
        return charge
