"""Quasi-steady-state monthly method, ISO 13790 (EXTENDED).

Port of ``reference_building.thermal_zone.ThermalZone.
solve_quasisteadystate_method``: monthly heat-balance with gain/loss
utilisation factors — the fast screening companion to the dynamic models.
It reuses the 5R1C parametrisation (UA, Cm) and its solar gains, so both
methods see exactly the same building. Multi-zone buildings are evaluated as
independent, adiabatically separated zones and aggregated afterwards, matching
the uncoupled-zone convention of the dynamic runner.

Mechanical ventilation follows the same supply-air convention as the
dynamic models: its zone-side balance uses the AHU supply temperature, while
the sensible AHU coil is reported separately with heat recovery and
recirculation.  The latent monthly balance is not migrated (extension point).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dt_prototype.common.constants import AIR_SPECIFIC_HEAT
from dt_prototype.common.preprocessing.building_input import BuildingInput
from dt_prototype.common.preprocessing.weather import WeatherData
from dt_prototype.monthly.simulation.air_handling_unit import AirHandlingUnit
from dt_prototype.monthly.simulation.config import SimulationConfig, season_mask

# ISO 13790 utilisation-factor parameters
_A_0 = 1.0
_TAU_0 = 15.0  # [h]
# the retained reference thresholds telling "conditioning intended" from set-point schedules
_HEATING_SETPOINT_THRESHOLD = 17.0  # [°C]
_COOLING_SETPOINT_THRESHOLD = 27.0  # [°C]


def _monthly(series: np.ndarray, index: pd.DatetimeIndex, how: str) -> np.ndarray:
    """Monthly aggregation of an annual array (sum or mean)."""
    grouped = pd.Series(series, index=index).groupby(index.month)
    return (grouped.sum() if how == "sum" else grouped.mean()).to_numpy()


_ENERGY_COLUMNS = (
    "heating_demand_kWh",
    "cooling_demand_kWh",
    "ahu_heating_demand_kWh",
    "ahu_cooling_demand_kWh",
    "total_sensible_heating_demand_kWh",
    "total_sensible_cooling_demand_kWh",
    "heat_losses_kWh",
    "gains_kWh",
)
_FACTOR_COLUMNS = ("eta_gain_heating", "eta_loss_cooling")


def _ahu_sensible_balance(
    zone,
    t_ext: np.ndarray,
    heating_available: np.ndarray,
    cooling_available: np.ndarray,
    h_sp: float,
    c_sp: float,
    config: SimulationConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return supply temperature, hourly AHU coil load and external Hve.

    The monthly method has no evolving zone-air state for the exhaust/return
    stream.  It therefore uses the active heating or cooling set point as the
    return-air reference and their midpoint during the shoulder seasons.
    This retains the configured sensible recovery and recirculation physics
    without importing a hidden hourly zone simulation into the QSS method.

    Returns
    -------
    tuple of numpy.ndarray
        Supply temperature [degC], signed sensible AHU coil load [W]
        (positive heating, negative cooling), and the effective external-air
        heat-transfer coefficient [W/K] used in the utilisation time constant.
    """
    h_vent = zone.ventilation_mass_flow * AIR_SPECIFIC_HEAT
    if zone.ahu is None:
        return t_ext, np.zeros_like(t_ext), h_vent

    ahu = AirHandlingUnit.from_dict(zone.ahu, mode=config.ahu_mode)
    t_supply = np.where(
        heating_available,
        ahu.t_sup_heating,
        ahu.t_sup_cooling,
    )
    neutral_reference = 0.5 * (h_sp + c_sp)
    t_return = np.full_like(t_ext, neutral_reference, dtype=float)
    t_return[cooling_available] = c_sp
    t_return[heating_available] = h_sp

    # BASIC is always 100% outdoor air.  EXTENDED applies the configured
    # outdoor-air ratio after sensible heat recovery, as AirHandlingUnit does.
    outdoor_air_ratio = 1.0 if config.ahu_mode == "basic" else ahu.outdoor_air_ratio
    t_recovered_oa = t_ext + ahu.eta_sensible * (t_return - t_ext)
    t_mixed = (
        outdoor_air_ratio * t_recovered_oa
        + (1.0 - outdoor_air_ratio) * t_return
    )
    q_ahu_sensible = h_vent * (t_supply - t_mixed)
    h_ve_external = h_vent * outdoor_air_ratio * (1.0 - ahu.eta_sensible)
    return t_supply, q_ahu_sensible, h_ve_external


def _run_zone_quasi_steady_state(
    building: BuildingInput,
    weather: WeatherData,
    config: SimulationConfig,
    zone_index: int,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Run the existing ISO 13790 monthly balance for one zone.

    Returns the public per-zone result plus the cooling heat-transfer term
    used to form a physically meaningful building-level cooling utilisation
    factor. The latter remains internal because it was not part of the public
    single-zone result schema.
    """
    from dt_prototype.monthly.simulation.models.model_5r1c import Model5R1C  # avoid cycle

    model = Model5R1C(building, weather, config, zone_index=zone_index)
    zone = model.zone
    index = weather.df.index
    dt = weather.timestep_seconds
    t_ext = weather.df["temp_air"].to_numpy()

    # Conditioning intention comes from the set-point schedule, while actual
    # availability follows the same explicit seasons as the dynamic runner.
    heating_available = season_mask(index, config.heating_season)
    cooling_available = season_mask(index, config.cooling_season)
    heating_ts = (
        zone.heating_setpoint > _HEATING_SETPOINT_THRESHOLD
    ) & heating_available
    cooling_ts = (
        zone.cooling_setpoint < _COOLING_SETPOINT_THRESHOLD
    ) & cooling_available
    n_heat = _monthly(heating_ts.astype(float), index, "sum")
    n_cool = _monthly(cooling_ts.astype(float), index, "sum")
    h_sp = float(zone.heating_setpoint[heating_ts].mean()) if heating_ts.any() else 20.0
    c_sp = float(zone.cooling_setpoint[cooling_ts].mean()) if cooling_ts.any() else 26.0

    # Transmission + zone-side air-exchange heat transfer [J/month].
    # Infiltration sees outdoor air and mechanical ventilation sees
    # the AHU supply state.  The monthly-mean transmission formulation is
    # intentionally retained; it is the documented ISO/QSS approximation.
    t_e_month = _monthly(t_ext, index, "mean")
    q_h_tr = model.UA_tot * (h_sp - t_e_month) * n_heat * dt
    q_c_tr = model.UA_tot * (c_sp - t_e_month) * n_cool * dt
    h_inf = zone.infiltration_mass_flow * AIR_SPECIFIC_HEAT
    h_vent = zone.ventilation_mass_flow * AIR_SPECIFIC_HEAT
    t_supply, q_ahu_sensible, h_vent_external = _ahu_sensible_balance(
        zone,
        t_ext,
        heating_available,
        cooling_available,
        h_sp,
        c_sp,
        config,
    )
    q_h_air = _monthly(
        (h_inf * (h_sp - t_ext) + h_vent * (h_sp - t_supply)) * heating_ts,
        index,
        "sum",
    ) * dt
    q_c_air = _monthly(
        (h_inf * (c_sp - t_ext) + h_vent * (c_sp - t_supply)) * cooling_ts,
        index,
        "sum",
    ) * dt
    q_h_ht = np.clip(q_h_tr + q_h_air, 1e-5, None)
    q_c_ht = np.clip(q_c_tr + q_c_air, 1e-5, None)

    # monthly gains: internal + solar (from the 5R1C load computation) [J]
    gains = zone.gains_convective + zone.gains_radiative + model.phi_sol
    q_gn = _monthly(gains, index, "sum") * dt

    # utilisation factors (ISO 13790, as the retained reference)
    h_ve_external = h_inf + h_vent_external
    tau = model.Cm / 3600.0 / (model.UA_tot + float(h_ve_external.max()))
    a = _A_0 + tau / _TAU_0

    gamma_h = np.clip(q_gn / q_h_ht, 1e-9, 1e5)
    eta_h = np.where(
        np.isclose(gamma_h, 1.0), a / (a + 1.0), (1.0 - gamma_h**a) / (1.0 - gamma_h ** (a + 1.0))
    )
    gamma_c = np.clip(q_gn / q_c_ht, 1e-9, 1e15)
    eta_c = np.where(
        np.isclose(gamma_c, 1.0),
        a / (a + 1.0),
        (1.0 - gamma_c ** (-a)) / (1.0 - gamma_c ** (-a - 1.0)),
    )

    # monthly demands [J] → [kWh]
    q_heat = np.clip(q_h_ht - eta_h * q_gn, 0.0, None) * (n_heat > 0)
    q_cool = np.clip(q_gn - eta_c * q_c_ht, 0.0, None) * (n_cool > 0)
    q_ahu_heat = _monthly(np.clip(q_ahu_sensible, 0.0, None), index, "sum") * dt
    q_ahu_cool = -_monthly(np.clip(q_ahu_sensible, None, 0.0), index, "sum") * dt

    month_index = pd.date_range(index[0].normalize(), periods=12, freq="MS")
    result = pd.DataFrame(
        {
            "heating_demand_kWh": q_heat / 3.6e6,
            "cooling_demand_kWh": q_cool / 3.6e6,
            "ahu_heating_demand_kWh": q_ahu_heat / 3.6e6,
            "ahu_cooling_demand_kWh": q_ahu_cool / 3.6e6,
            "total_sensible_heating_demand_kWh": (q_heat + q_ahu_heat) / 3.6e6,
            "total_sensible_cooling_demand_kWh": (q_cool + q_ahu_cool) / 3.6e6,
            "heat_losses_kWh": q_h_ht / 3.6e6,
            "gains_kWh": q_gn / 3.6e6,
            "eta_gain_heating": eta_h,
            "eta_loss_cooling": eta_c,
        },
        index=month_index,
    )
    return result, q_c_ht / 3.6e6


def _weighted_factor(
    factors: list[np.ndarray], weights: list[np.ndarray]
) -> np.ndarray:
    """Energy-weighted monthly factor with an unweighted zero-energy fallback."""
    factor_values = np.stack(factors)
    weight_values = np.stack(weights)
    denominator = weight_values.sum(axis=0)
    numerator = (factor_values * weight_values).sum(axis=0)
    fallback = factor_values.mean(axis=0)
    return np.clip(
        np.divide(numerator, denominator, out=fallback, where=denominator > 0.0),
        0.0,
        1.0,
    )


def run_quasi_steady_state(
    building: BuildingInput, weather: WeatherData, config: SimulationConfig | None = None
) -> pd.DataFrame:
    """Monthly heating/cooling demand via the ISO 13790 QSS method.

    Parameters
    ----------
    building : BuildingInput
        Serialised preprocessing output.
    weather : WeatherData
        Processed weather.
    config : SimulationConfig, optional
        Conditioning seasons and AHU mode are applied.  The 5R1C building
        parametrisation is always employed (as in the retained reference).

    Returns
    -------
    pandas.DataFrame
        12 rows (month start dates). ``heating_demand_kWh`` and
        ``cooling_demand_kWh`` are zone sensible demand; ``ahu_heating_*``
        and ``ahu_cooling_*`` are the separate sensible coil components;
        ``total_sensible_*`` is their sum. Heat-transfer/gain terms and
        utilisation factors are also reported. A two-zone building exposes
        the same quantities as ``zone_upper_*`` / ``zone_lower_*`` columns.

    Notes
    -----
    Zones are solved independently and then aggregated; no heat-transfer
    element is introduced at their interface, matching the dynamic models'
    adiabatic/uncoupled two-zone convention. Energy quantities are summed.
    Building-level utilisation factors are energy-weighted diagnostics:
    heating by monthly gains and cooling by monthly cooling heat transfer.
    A single-zone result contains only the unprefixed building/zone columns.
    """
    config = config or SimulationConfig()
    zone_runs = [
        _run_zone_quasi_steady_state(building, weather, config, zone_index)
        for zone_index in range(len(building.zones))
    ]
    zone_results = [run[0] for run in zone_runs]

    # Single-zone callers need no redundant zone_single_* aliases.
    if len(zone_results) == 1:
        return zone_results[0]

    result = pd.DataFrame(index=zone_results[0].index)
    for column in _ENERGY_COLUMNS:
        result[column] = sum(zone_result[column] for zone_result in zone_results)

    result["eta_gain_heating"] = _weighted_factor(
        [zone_result["eta_gain_heating"].to_numpy() for zone_result in zone_results],
        [zone_result["gains_kWh"].to_numpy() for zone_result in zone_results],
    )
    result["eta_loss_cooling"] = _weighted_factor(
        [zone_result["eta_loss_cooling"].to_numpy() for zone_result in zone_results],
        [run[1] for run in zone_runs],
    )

    for zone_input, zone_result in zip(building.zones, zone_results):
        label = zone_input.geometry.zone_label
        for column in (*_ENERGY_COLUMNS, *_FACTOR_COLUMNS):
            result[f"zone_{label}_{column}"] = zone_result[column].to_numpy()
    return result
