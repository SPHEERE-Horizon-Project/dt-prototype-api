"""Air handling unit with recirculation and saturation checks (EXTENDED).

Extended migration of ``reference_building.air_handling_unit.AirHandlingUnit``.
Compared to the base version, this adds:

- **recirculation** (mixing chamber): only ``outdoor_air_ratio`` of the
  supply flow is outdoor air (heat-recovered against the exhaust); the rest
  is recirculated zone air;
- **saturation checks**: the supply humidity set point is clipped to the
  saturation curve at the supply temperature; cooling below the mixed-air
  dew point condenses moisture even without active humidity control;
- **explicit coil split**: dehumidification is modelled as cooling to the
  apparatus dew point plus reheat, so simultaneous cooling- and heating-coil
  loads are reported separately (as served by the real plant).

Fan power uses the the retained reference catalogue fit. Still assumed: steady-state coils,
no coil bypass factor (extension point). ``mode="basic"`` retains the
BASIC-version algorithm for regression-compatible runs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dt_prototype.common.constants import (
    AIR_DENSITY,
    AIR_SPECIFIC_HEAT,
    VAPOUR_LATENT_HEAT,
)

# Fan electric consumption per unit volume flow [W/(m3/h)] (the retained reference catalogue fit)
_FAN_POWER_PER_M3H = 0.4434
# Approach to saturation allowed at the supply (95% RH margin)
_SATURATION_MARGIN = 0.95
_P_ATM = 101_325.0  # [Pa] (AHU psychrometrics at standard pressure)


def saturation_humidity_ratio(t_air: float, p_atm: float = _P_ATM) -> float:
    """Humidity ratio at saturation [kg/kg] for air temperature [°C]."""
    if t_air > 0.0:
        p_sat = 610.5 * math.exp(17.269 * t_air / (237.3 + t_air))
    else:
        p_sat = 610.5 * math.exp(21.875 * t_air / (265.5 + t_air))
    return 0.622 * p_sat / (p_atm - p_sat)


def dew_point_of(x: float, p_atm: float = _P_ATM) -> float:
    """Dew point temperature [°C] of air with humidity ratio ``x`` [kg/kg]."""
    p_v = p_atm * x / (0.622 + x)
    ln_ratio = math.log(max(p_v, 1.0) / 610.5)
    if ln_ratio >= 0.0:  # dew point above 0 °C
        return 237.3 * ln_ratio / (17.269 - ln_ratio)
    return 265.5 * ln_ratio / (21.875 - ln_ratio)


@dataclass
class AhuState:
    """Supply conditions and loads of the AHU for one time step."""

    supply_temperature: float  # [°C]
    supply_specific_humidity: float  # [kg/kg]
    heating_coil_load: float  # [W], >= 0 (incl. reheat after dehumidification)
    cooling_coil_load: float  # [W], <= 0 (incl. cooling to apparatus dew point)
    latent_load: float  # [W], >0 humidification, <0 dehumidification
    electric_fan: float  # fan consumption [W]

    @property
    def sensible_load(self) -> float:
        """Net sensible coil load [W] (base-version compatibility)."""
        return self.heating_coil_load + self.cooling_coil_load


class AirHandlingUnit:
    """AHU with heat recovery, recirculation and (de)humidification.

    Parameters (typically from the end-use schedule JSON ``ahu`` block)
    ----------
    sensible_recovery_eff, latent_recovery_eff : float
        Heat recovery effectivenesses on the outdoor-air stream [-].
    supply_temperature_heating, supply_temperature_cooling : float
        Seasonal supply air temperature set points [°C].
    supply_specific_humidity : float
        Supply humidity set point [kg/kg] (used when ``humidity_control``).
    humidity_control : bool
        Enable active humidification/dehumidification at the AHU.
    outdoor_air_ratio : float
        Outdoor-air fraction of the supply flow [0-1]; 1 = all outdoor air
        (base-version behaviour), lower values recirculate zone air.
    mode : {"extended", "basic"}
        ``"extended"`` uses recirculation, saturation checks and an explicit
        cooling/reheat coil split. ``"basic"`` reproduces the BASIC-version
        100% outdoor-air algorithm and ignores ``outdoor_air_ratio``.
    """

    def __init__(
        self,
        sensible_recovery_eff: float = 0.5,
        latent_recovery_eff: float = 0.0,
        supply_temperature_heating: float = 20.0,
        supply_temperature_cooling: float = 16.0,
        supply_specific_humidity: float = 0.008,
        humidity_control: bool = False,
        outdoor_air_ratio: float = 1.0,
        mode: str = "extended",
    ) -> None:
        if not 0.0 < outdoor_air_ratio <= 1.0:
            raise ValueError(f"outdoor_air_ratio must be in (0, 1], got {outdoor_air_ratio}")
        if mode not in {"extended", "basic"}:
            raise ValueError(f"mode must be 'extended' or 'basic', got {mode!r}")
        self.eta_sensible = sensible_recovery_eff
        self.eta_latent = latent_recovery_eff
        self.t_sup_heating = supply_temperature_heating
        self.t_sup_cooling = supply_temperature_cooling
        self.x_sup_set = supply_specific_humidity
        self.humidity_control = humidity_control
        self.outdoor_air_ratio = outdoor_air_ratio
        self.mode = mode

    @classmethod
    def from_dict(cls, spec: dict, mode: str = "extended") -> "AirHandlingUnit":
        """Build from the ``ahu`` block of an end-use schedule JSON."""
        return cls(
            sensible_recovery_eff=float(spec.get("sensible_recovery_eff", 0.5)),
            latent_recovery_eff=float(spec.get("latent_recovery_eff", 0.0)),
            supply_temperature_heating=float(spec.get("supply_temperature_heating", 20.0)),
            supply_temperature_cooling=float(spec.get("supply_temperature_cooling", 16.0)),
            supply_specific_humidity=float(spec.get("supply_specific_humidity", 0.008)),
            humidity_control=bool(spec.get("humidity_control", False)),
            outdoor_air_ratio=float(spec.get("outdoor_air_ratio", 1.0)),
            mode=mode,
        )

    def process(
        self,
        t_ext: float,
        x_ext: float,
        t_zone: float,
        x_zone: float,
        mass_flow: float,
        heating_mode: bool,
    ) -> AhuState:
        """Precondition the supply air stream for one time step.

        The configured ``mode`` selects either the EXTENDED sequence below
        or the BASIC-version 100% outdoor-air/net-coil algorithm.

        Sequence: heat recovery on the outdoor-air fraction → mixing with
        recirculated zone air → cooling/dehumidification (to the apparatus
        dew point when the supply humidity requires it) → heating/reheat to
        the supply temperature → humidification. All states are checked
        against the saturation curve.

        Parameters
        ----------
        t_ext, x_ext : float
            Outdoor air state [°C, kg/kg].
        t_zone, x_zone : float
            Zone (return/exhaust) state from the previous time step.
        mass_flow : float
            Total supply air mass flow rate [kg/s].
        heating_mode : bool
            True during the heating season (selects supply set point and
            humidification direction).

        Returns
        -------
        AhuState
        """
        if mass_flow <= 0.0:
            return AhuState(t_ext, x_ext, 0.0, 0.0, 0.0, 0.0)

        if self.mode == "basic":
            return self._process_basic(
                t_ext=t_ext,
                x_ext=x_ext,
                t_zone=t_zone,
                x_zone=x_zone,
                mass_flow=mass_flow,
                heating_mode=heating_mode,
            )

        # 1. Heat recovery (outdoor-air stream only, against the exhaust)
        t_oa = t_ext + self.eta_sensible * (t_zone - t_ext)
        x_oa = x_ext + self.eta_latent * (x_zone - x_ext)

        # 2. Mixing chamber (recirculation)
        r = self.outdoor_air_ratio
        t_mix = r * t_oa + (1.0 - r) * t_zone
        x_mix = r * x_oa + (1.0 - r) * x_zone
        # the mixed state cannot be supersaturated
        x_mix = min(x_mix, saturation_humidity_ratio(t_mix))

        t_sup = self.t_sup_heating if heating_mode else self.t_sup_cooling
        x_sat_sup = _SATURATION_MARGIN * saturation_humidity_ratio(t_sup)

        heating_coil = 0.0
        cooling_coil = 0.0
        latent = 0.0
        cp = AIR_SPECIFIC_HEAT

        if self.humidity_control:
            # saturation check on the humidity set point
            x_target = min(self.x_sup_set, x_sat_sup)
            if x_mix > x_target:
                # Dehumidification: cool to the apparatus dew point of the
                # target humidity, then reheat to the supply temperature.
                t_adp = dew_point_of(x_target)
                cooling_coil = min(mass_flow * cp * (min(t_adp, t_sup) - t_mix), 0.0)
                latent = mass_flow * VAPOUR_LATENT_HEAT * (x_target - x_mix)  # < 0
                if t_sup > t_adp:
                    heating_coil = mass_flow * cp * (t_sup - t_adp)  # reheat
                x_sup = x_target
            else:
                # Humidification (steam) up to the target, plus sensible coil
                latent = mass_flow * VAPOUR_LATENT_HEAT * (x_target - x_mix)  # >= 0
                x_sup = x_target
                dt = t_sup - t_mix
                heating_coil = mass_flow * cp * max(dt, 0.0)
                cooling_coil = mass_flow * cp * min(dt, 0.0)
        else:
            # No active humidity control: sensible coil only, but cooling
            # below the mixed-air dew point condenses moisture (saturation
            # check) — implicit dehumidification on the cooling coil.
            dt = t_sup - t_mix
            heating_coil = mass_flow * cp * max(dt, 0.0)
            cooling_coil = mass_flow * cp * min(dt, 0.0)
            x_sup = x_mix
            x_sat_at_supply = saturation_humidity_ratio(t_sup)
            if x_mix > x_sat_at_supply:
                x_sup = x_sat_at_supply
                latent = mass_flow * VAPOUR_LATENT_HEAT * (x_sup - x_mix)  # < 0

        fan = _FAN_POWER_PER_M3H * (mass_flow / AIR_DENSITY * 3600.0)
        return AhuState(t_sup, x_sup, heating_coil, cooling_coil, latent, fan)

    def _process_basic(
        self,
        t_ext: float,
        x_ext: float,
        t_zone: float,
        x_zone: float,
        mass_flow: float,
        heating_mode: bool,
    ) -> AhuState:
        """Run the BASIC-version 100% outdoor-air AHU algorithm.

        Heat recovery acts directly on the outdoor stream, followed by one
        net sensible coil to the seasonal supply-temperature set point.
        Optional humidity control moves directly to the configured humidity
        set point. There is no mixing chamber, saturation clipping, implicit
        condensation or cooling-and-reheat split.
        """
        t_recovered = t_ext + self.eta_sensible * (t_zone - t_ext)
        x_recovered = x_ext + self.eta_latent * (x_zone - x_ext)
        t_supply = self.t_sup_heating if heating_mode else self.t_sup_cooling

        sensible = mass_flow * AIR_SPECIFIC_HEAT * (t_supply - t_recovered)
        if self.humidity_control:
            x_supply = self.x_sup_set
            latent = (
                mass_flow
                * VAPOUR_LATENT_HEAT
                * (x_supply - x_recovered)
            )
        else:
            x_supply = x_recovered
            latent = 0.0

        fan = _FAN_POWER_PER_M3H * (mass_flow / AIR_DENSITY * 3600.0)
        return AhuState(
            supply_temperature=t_supply,
            supply_specific_humidity=x_supply,
            heating_coil_load=max(sensible, 0.0),
            cooling_coil_load=min(sensible, 0.0),
            latent_load=latent,
            electric_fan=fan,
        )
