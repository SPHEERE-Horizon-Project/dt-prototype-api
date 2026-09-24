"""Thermal model interface, registry and shared zone control logic.

Open/closed extension point (FR-11, NFR-06): a new thermal model is added by
creating ONE new module in ``dt_prototype.dynamic/simulation/models/`` containing a
:class:`ThermalModel` subclass decorated with :func:`register_model`. The
``models`` package auto-imports its modules, so no existing simulation code
is edited.

The base class also carries the model-independent parts migrated from
``reference_building.thermal_zone.ThermalZone``:

- the time-step control logic of ``solve_timestep`` (free-floating → heating
  set point → capacity clamp → cooling set point → capacity clamp);
- the latent (humidity) balance ``latent_balance`` on the air node;
- EXTENDED: the window-opening free-cooling control (extra outdoor-air flow
  when the zone is warm and outdoor air is cooler; behavioural
  simplification of the retained reference's wind/stack natural-ventilation network) and
  the AHU supply preconditioning with recirculation.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any

import numpy as np

from dt_prototype.common.constants import (
    AIR_DENSITY,
    AIR_SPECIFIC_HEAT,
    VAPOUR_LATENT_HEAT,
    VAPOUR_SPECIFIC_HEAT,
)
from dt_prototype.common.preprocessing.building_input import BuildingInput
from dt_prototype.common.preprocessing.weather import WeatherData
from dt_prototype.dynamic.simulation.air_handling_unit import AhuState, AirHandlingUnit
from dt_prototype.dynamic.simulation.config import SimulationConfig
from dt_prototype.dynamic.simulation.zone import Zone, build_zone

# Model registry: name -> ThermalModel subclass
MODEL_REGISTRY: dict[str, type["ThermalModel"]] = {}


def register_model(cls: type["ThermalModel"]) -> type["ThermalModel"]:
    """Class decorator adding a :class:`ThermalModel` subclass (and its
    aliases) to the registry. This is the FR-11 extension mechanism."""
    for name in (cls.name, *cls.aliases):
        if name in MODEL_REGISTRY:
            raise ValueError(f"Thermal model name '{name}' already registered")
        MODEL_REGISTRY[name] = cls
    return cls


def get_model_class(name: str) -> type["ThermalModel"]:
    """Look up a thermal model class by registry name (e.g. ``"5R1C"``).

    Importing :mod:`dt_prototype.dynamic.simulation.models` triggers auto-registration.
    """
    import dt_prototype.dynamic.simulation.models  # noqa: F401  (auto-import models)

    try:
        return MODEL_REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"Unknown thermal model '{name}'; registered models: {sorted(MODEL_REGISTRY)}"
        ) from None


def saturation_pressure(t_air: float | np.ndarray) -> float | np.ndarray:
    """Water vapour saturation pressure [Pa] at air temperature [°C]
    (correlations as in the retained reference)."""
    return np.where(
        np.asarray(t_air) > 0.0,
        610.5 * np.exp(17.269 * np.asarray(t_air) / (237.3 + np.asarray(t_air))),
        610.5 * np.exp(21.875 * np.asarray(t_air) / (265.5 + np.asarray(t_air))),
    )


@dataclass
class TimestepResult:
    """Zone solution of one time step (SI units)."""

    sensible_load: float  # HVAC sensible heat flow, >0 heating, <0 cooling [W]
    latent_load: float  # HVAC latent heat flow [W]
    air_temperature: float  # [°C]
    operative_temperature: float  # [°C]
    mean_radiant_temperature: float  # [°C]
    relative_humidity: float  # [0-1]
    specific_humidity: float  # [kg/kg]
    # air handling unit coil loads and fan consumption (0 without AHU)
    ahu_sensible_load: float = 0.0  # [W], net coil load (compatibility)
    ahu_latent_load: float = 0.0  # [W], >0 humidification
    ahu_electric: float = 0.0  # fan [W]
    # EXTENDED: explicit coil split (simultaneous cooling + reheat)
    ahu_heating_coil_load: float = 0.0  # [W], >= 0
    ahu_cooling_coil_load: float = 0.0  # [W], <= 0
    # EXTENDED: window-opening free cooling actually engaged [1/h]
    natural_ventilation_ach: float = 0.0


class ThermalModel(abc.ABC):
    """Abstract dynamic thermal model of one zone/building.

    Subclasses implement the RC-network specifics; the shared control loop
    (:meth:`solve_timestep`) and the latent balance live here.

    Parameters
    ----------
    building : BuildingInput
        Serialised preprocessing output (FR-08 artefact).
    weather : WeatherData
        Processed weather.
    config : SimulationConfig
        Run settings.
    zone_index : int
        Which of ``building.zones`` this model instance solves (see the
        two-zone convention in ``preprocessing.geometry``). Defaults to 0,
        the only zone of a single-zone building; a two-zone building needs
        two independent ``ThermalModel`` instances, one per zone index —
        the retained reference's zones are uncoupled RC networks, so this is exactly how it
        models them too (``simulation.runner.run_building`` builds both).
    """

    #: registry name, e.g. "5R1C" — override in subclasses
    name: str = ""
    #: optional alternative names (the retained reference used "1C"/"2C")
    aliases: tuple[str, ...] = ()
    #: number of components of the HVAC load split sigma (2 = rad/conv,
    #: 3 = rad IW / rad AW / conv) — override in subclasses
    n_sigma: int = 3

    def __init__(
        self,
        building: BuildingInput,
        weather: WeatherData,
        config: SimulationConfig,
        zone_index: int = 0,
    ) -> None:
        self.zone: Zone = build_zone(building, weather, zone_index)
        self.weather = weather
        self.config = config
        self.tau = weather.timestep_seconds  # [s]
        # state variables (mass temperatures [°C], air temperature [°C],
        # zone humidity ratio [kg/kg])
        self.Tm0 = np.array([config.initial_temperature, config.initial_temperature])
        self.Ta0 = config.initial_temperature
        self.xm0 = config.initial_specific_humidity
        # weather arrays cached for fast per-timestep access
        self._t_ext = weather.df["temp_air"].to_numpy()
        self._x_ext = weather.df["specific_humidity"].to_numpy()
        self._p_atm = weather.df["pressure"].to_numpy()
        # optional air handling unit on the mechanical ventilation stream
        self.ahu = (
            AirHandlingUnit.from_dict(self.zone.ahu, mode=config.ahu_mode)
            if self.zone.ahu
            else None
        )
        # supply conditions of the current time step (set by solve_timestep)
        self._t_sup = float(self._t_ext[0])
        # model-specific parameters and load distribution
        self._compute_parameters()
        self._compute_loads()

    # ------------------------------------------------------------------ #
    # Model-specific interface
    # ------------------------------------------------------------------ #
    @abc.abstractmethod
    def _compute_parameters(self) -> None:
        """Derive the RC network parameters from the zone description."""

    @abc.abstractmethod
    def _compute_loads(self) -> None:
        """Precompute solar/internal load distributions for every time step."""

    @abc.abstractmethod
    def sensible_balance(
        self,
        flag: str,
        t: int,
        hve: tuple[float, float],
        sigma: tuple[float, ...],
        t_set: float = 20.0,
        phi_hc_set: float = 0.0,
    ) -> tuple[float, float, float, float, Any]:
        """Solve the sensible RC network for time step ``t``.

        Parameters
        ----------
        flag : str
            ``"Tset"`` (find the load keeping the air at ``t_set``) or
            ``"phiset"`` (impose the load ``phi_hc_set``).
        t : int
            Time step index.
        hve : tuple of float
            ``(H_ve_vent, H_ve_inf)`` ventilation/infiltration heat transfer
            coefficients [W/K].
        sigma : tuple of float
            Radiative/convective split of the HVAC load (model-specific
            length; last element = convective fraction).
        t_set : float
            Air set point [°C] (``Tset`` mode).
        phi_hc_set : float
            Imposed HVAC load [W] (``phiset`` mode).

        Returns
        -------
        tuple
            ``(phi_hc, T_air, T_operative, T_mean_radiant, mass_state)``;
            ``mass_state`` is passed back to :meth:`commit_state`.
        """

    def commit_state(self, mass_state: Any, t_air: float, x_int: float) -> None:
        """Store the end-of-step state as the next step's initial condition."""
        self.Tm0 = np.asarray(mass_state, dtype=float)
        self.Ta0 = t_air
        self.xm0 = x_int

    # ------------------------------------------------------------------ #
    # Shared latent balance (port of ThermalZone.latent_balance)
    # ------------------------------------------------------------------ #
    def latent_balance(
        self,
        flag: str,
        g_ve: tuple[float, float],
        x_ext: float,
        x_sup: float,
        vapour_load: float,
        t_air: float,
        p_atm: float,
        rh_set: float = 0.5,
        phi_lat_set: float = 0.0,
    ) -> tuple[float, float, float]:
        """Solve the zone vapour balance for one time step.

        Parameters
        ----------
        flag : str
            ``"rhset"`` (find latent load keeping RH at ``rh_set``) or
            ``"phiset"`` (impose latent load, free-floating humidity).
        g_ve : tuple of float
            ``(G_vent, G_inf)`` dry-air mass flow rates [kg/s].
        x_ext, x_sup : float
            Outdoor and ventilation-supply humidity ratios [kg/kg].
        vapour_load : float
            Internal vapour generation [kg/s].
        t_air : float
            Zone air temperature [°C].
        p_atm : float
            Atmospheric pressure [Pa].
        rh_set : float
            Relative humidity set point [0-1] (``rhset`` mode).
        phi_lat_set : float
            Imposed latent load [W] (``phiset`` mode).

        Returns
        -------
        tuple of float
            ``(x_int, rh_int, phi_lat)``: zone humidity ratio, relative
            humidity, latent load (>0 humidification, <0 dehumidification).
        """
        p_sat = float(saturation_pressure(t_air))
        heat = VAPOUR_LATENT_HEAT + VAPOUR_SPECIFIC_HEAT * t_air
        g_vent, g_inf = g_ve
        rho_v = AIR_DENSITY * self.zone.volume / self.tau

        if flag == "rhset":
            x_set = 0.622 * rh_set * p_sat / (p_atm - rh_set * p_sat)
            phi_lat = -(
                (g_inf * (x_ext - x_set) + g_vent * (x_sup - x_set) - rho_v * (x_set - self.xm0))
                * heat
                + vapour_load * heat
            )
            x_int = x_set
        elif flag == "phiset":
            x_int = (
                g_inf * x_ext + g_vent * x_sup + phi_lat_set / heat + vapour_load + rho_v * self.xm0
            ) / (g_inf + g_vent + rho_v)
            phi_lat = phi_lat_set
        else:
            raise ValueError(f"latent_balance: flag must be 'phiset' or 'rhset', got {flag}")

        p_int = p_atm * x_int / (0.622 + x_int)
        return x_int, min(p_int / p_sat, 1.0), phi_lat

    # ------------------------------------------------------------------ #
    # Shared time-step control loop (port of ThermalZone.solve_timestep)
    # ------------------------------------------------------------------ #
    def solve_timestep(
        self,
        t: int,
        heating_on: bool,
        cooling_on: bool,
        sigma_heating: tuple[float, ...],
        sigma_cooling: tuple[float, ...],
    ) -> TimestepResult:
        """Solve one time step with set-point control and capacity limits.

        Sequence (as in the retained reference): free-floating solution; if below the heating
        set point solve at set point (clamped to ``heating_max_power``); if
        above the cooling set point solve at set point (clamped to
        ``cooling_max_power``); then the latent balance with the humidity
        band, if enabled.

        Parameters
        ----------
        t : int
            Time step index.
        heating_on, cooling_on : bool
            Seasonal availability of conditioning.
        sigma_heating, sigma_cooling : tuple of float
            Radiative/convective split of the HVAC load (from the systems).

        Returns
        -------
        TimestepResult
        """
        zone = self.zone
        t_ext = float(self._t_ext[t])
        x_ext = float(self._x_ext[t])
        p_atm = float(self._p_atm[t])

        g_vent = float(zone.ventilation_mass_flow[t])
        g_inf = float(zone.infiltration_mass_flow[t])

        # EXTENDED: window-opening free cooling. Behavioural model
        # (simplification of the retained reference's wind/stack pressure network): windows
        # open — ramping over 2 K — when the zone (previous step) is warm,
        # outdoor air is cooler than the zone and not uncomfortably cold.
        nat_ach = 0.0
        nv = zone.natural_ventilation
        if nv is not None:
            threshold = float(nv.get("zone_temperature_threshold", 24.0))
            t_min_out = float(nv.get("min_outdoor_temperature", 12.0))
            ach_max = float(nv.get("ach_max", 2.0))
            if self.Ta0 > threshold and t_min_out < t_ext < self.Ta0 - 0.5:
                opening = min((self.Ta0 - threshold) / 2.0, 1.0)
                nat_ach = opening * ach_max
        g_inf += nat_ach * zone.volume * AIR_DENSITY / 3600.0

        hve = (g_vent * AIR_SPECIFIC_HEAT, g_inf * AIR_SPECIFIC_HEAT)

        # Air handling unit: precondition the mechanical ventilation stream
        # (exhaust-side conditions taken from the previous time step)
        if self.ahu is not None:
            ahu_state = self.ahu.process(t_ext, x_ext, self.Ta0, self.xm0, g_vent, heating_on)
        else:  # no AHU: ventilation supplies outdoor air
            ahu_state = AhuState(t_ext, x_ext, 0.0, 0.0, 0.0, 0.0)
        self._t_sup = ahu_state.supply_temperature
        x_sup = ahu_state.supply_specific_humidity

        free_sigma = tuple([0.0] * (len(sigma_heating) - 1) + [1.0])
        phi, t_air, t_op, t_mr, state = self.sensible_balance(
            "phiset", t, hve, free_sigma, phi_hc_set=0.0
        )

        t_set_h = float(zone.heating_setpoint[t])
        t_set_c = float(zone.cooling_setpoint[t])
        p_max = self.config.heating_max_power
        p_min = self.config.cooling_max_power

        if heating_on and t_air < t_set_h:
            phi, t_air, t_op, t_mr, state = self.sensible_balance(
                "Tset", t, hve, sigma_heating, t_set=t_set_h
            )
            if p_max is not None and phi > p_max:
                phi, t_air, t_op, t_mr, state = self.sensible_balance(
                    "phiset", t, hve, sigma_heating, phi_hc_set=p_max
                )
        if cooling_on and t_air > t_set_c:
            phi, t_air, t_op, t_mr, state = self.sensible_balance(
                "Tset", t, hve, sigma_cooling, t_set=t_set_c
            )
            if p_min is not None and phi < p_min:
                phi, t_air, t_op, t_mr, state = self.sensible_balance(
                    "phiset", t, hve, sigma_cooling, phi_hc_set=p_min
                )

        # Latent balance (optional)
        vapour_load = float(zone.gains_latent[t]) / VAPOUR_LATENT_HEAT  # [kg/s]
        if self.config.latent:
            x_int, rh_int, phi_lat = self.latent_balance(
                "phiset", (g_vent, g_inf), x_ext, x_sup, vapour_load, t_air, p_atm
            )
            rh_low = float(zone.humidity_setpoint_low[t])
            rh_high = float(zone.humidity_setpoint_high[t])
            if heating_on and rh_int < rh_low:
                x_int, rh_int, phi_lat = self.latent_balance(
                    "rhset", (g_vent, g_inf), x_ext, x_sup, vapour_load, t_air, p_atm, rh_set=rh_low
                )
            elif cooling_on and rh_int > rh_high:
                x_int, rh_int, phi_lat = self.latent_balance(
                    "rhset", (g_vent, g_inf), x_ext, x_sup, vapour_load, t_air, p_atm, rh_set=rh_high
                )
        else:
            # humidity still tracked free-floating for reporting
            x_int, rh_int, phi_lat = self.latent_balance(
                "phiset", (g_vent, g_inf), x_ext, x_sup, vapour_load, t_air, p_atm
            )
            phi_lat = 0.0

        self.commit_state(state, t_air, x_int)
        return TimestepResult(
            sensible_load=phi,
            latent_load=phi_lat,
            air_temperature=t_air,
            operative_temperature=t_op,
            mean_radiant_temperature=t_mr,
            relative_humidity=rh_int,
            specific_humidity=x_int,
            ahu_sensible_load=ahu_state.sensible_load,
            ahu_latent_load=ahu_state.latent_load,
            ahu_electric=ahu_state.electric_fan,
            ahu_heating_coil_load=ahu_state.heating_coil_load,
            ahu_cooling_coil_load=ahu_state.cooling_coil_load,
            natural_ventilation_ach=nat_ach,
        )
