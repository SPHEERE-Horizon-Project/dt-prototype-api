"""Lean monthly building-energy model and calibration engine for Model 3.

The module uses only the Python standard library.  Its input schema is shared
with the companion workbook and the CSV files in ``example_data``.

Scientific boundary
-------------------
* Monthly, single-zone sensible heat balance.
* ISO 13790-style gain utilisation and thermal-mass time constant.
* Ground heat transfer is a user-supplied steady monthly coefficient.  The
  detailed ISO 13370 periodic model is deliberately deferred.
* Four technical-system configurations, optional PV and solar thermal.
* Five-parameter heating/cooling change-point calibration in Python only.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path


ORIENTATIONS = ("N", "E", "S", "W", "HOR")
CARRIERS = ("electricity", "natural_gas", "district_heat")
SERVICES = ("H_pri", "H_sec", "W_pri", "W_sec", "C")
MASS_CAPACITY = {
    "very_light": 80_000.0,
    "light": 110_000.0,
    "medium": 165_000.0,
    "heavy": 260_000.0,
    "very_heavy": 370_000.0,
}
DEFAULTS = {
    "rho_air": 1.2,
    "cp_air": 1005.0,
    "a0": 1.0,
    "tau0_h": 15.0,
    "occupant_gain_W": 70.0,
    "dhw_kWh_person_day": 0.55,
    "sfp_W_per_m3_s": 1500.0,
    "aux_W_m2": 0.5,
    "nmbe_limit_pct": 5.0,
    "cvrmse_limit_pct": 15.0,
}


def _float(value, default=0.0):
    if value in (None, ""):
        return default
    return float(value)


def _int(value, default=0):
    if value in (None, ""):
        return default
    return int(float(value))


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def ventilation_htc(q_ve_m3_h, q_inf_m3_h, heat_recovery_efficiency):
    """Ventilation and infiltration heat-transfer coefficient [W/K]."""
    return (
        DEFAULTS["rho_air"]
        * DEFAULTS["cp_air"]
        * (q_ve_m3_h * (1.0 - heat_recovery_efficiency) + q_inf_m3_h)
        / 3600.0
    )


def utilisation_factor_heating(gamma, exponent):
    if gamma is None:
        return 0.0
    if gamma < 0:
        return 1.0 / gamma
    if abs(gamma - 1.0) < 1e-9:
        return exponent / (exponent + 1.0)
    return (1.0 - gamma**exponent) / (1.0 - gamma ** (exponent + 1.0))


def utilisation_factor_cooling(gamma, exponent):
    if gamma is None:
        return 0.0
    if gamma < 0:
        return 1.0
    if abs(gamma - 1.0) < 1e-9:
        return exponent / (exponent + 1.0)
    return (1.0 - gamma ** (-exponent)) / (1.0 - gamma ** (-(exponent + 1.0)))


def system_efficiency(system, outdoor_temp_C):
    form = system["form"]
    c0 = _float(system["c0"])
    c1 = _float(system["c1"])
    c2 = _float(system["c2"])
    if form == "const":
        value = c0
    elif form == "linear":
        value = c0 + c1 * outdoor_temp_C
    elif form == "quadratic":
        value = c0 + c1 * outdoor_temp_C + c2 * outdoor_temp_C**2
    elif form == "piecewise":
        breakpoint = _float(system["breakpoint_C"])
        if outdoor_temp_C < breakpoint:
            value = c0 + c1 * outdoor_temp_C
        else:
            value = _float(system["c0_high"]) + _float(system["c1_high"]) * outdoor_temp_C
    else:
        raise ValueError(f"Unsupported efficiency form: {form}")
    return max(0.1, value)


def _orientation_irradiation(row, orientation):
    return _float(row[f"solar_{orientation}_kWh_m2"])


def _scenario_value(scenario, key, default=1.0):
    return _float(scenario.get(key), default)


def _fraction(row, key, default=1.0):
    """Read an optional monthly operating fraction and enforce its bounds."""
    value = _float(row.get(key), default)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{key} must be between 0 and 1, got {value}")
    return value


def building_coefficients(building, scenario):
    htc_mult = _scenario_value(scenario, "envelope_htc_multiplier")
    ground_mult = _scenario_value(scenario, "ground_htc_multiplier")
    q_ve = _float(building["mechanical_ventilation_m3_h"]) * _scenario_value(
        scenario, "ventilation_multiplier"
    )
    q_inf = _float(building["infiltration_m3_h"]) * _scenario_value(
        scenario, "infiltration_multiplier"
    )
    h_tr = (
        _float(building["H_transmission_opaque_W_K"])
        + _float(building["H_transmission_windows_W_K"])
    ) * htc_mult
    h_ground = _float(building["H_ground_W_K"]) * ground_mult
    h_ve = ventilation_htc(q_ve, q_inf, _float(building["heat_recovery_efficiency"]))
    h_total = h_tr + h_ground + h_ve
    if h_total <= 0:
        raise ValueError(f"Non-positive total heat-transfer coefficient for {building['building_id']}")
    mass = MASS_CAPACITY[building["mass_class"]] * _float(building["conditioned_floor_area_m2"])
    tau_h = mass / (3600.0 * h_total)
    exponent = DEFAULTS["a0"] + tau_h / DEFAULTS["tau0_h"]
    result = {
        "H_transmission_W_K": h_tr,
        "H_ground_W_K": h_ground,
        "H_ventilation_W_K": h_ve,
        "H_total_W_K": h_total,
        "thermal_capacity_J_K": mass,
        "tau_h": tau_h,
        "utilisation_exponent": exponent,
        "q_ve_m3_h": q_ve,
    }
    if _int(building.get("seasonal_ahu_comparison_enabled")):
        # These terms retain the zone/AHU split needed by the opt-in comparison.
        # H_ventilation_W_K above remains the effective external-air coefficient.
        result.update(
            {
                "H_infiltration_W_K": ventilation_htc(0.0, q_inf, 0.0),
                "H_ventilation_raw_W_K": ventilation_htc(q_ve, 0.0, 0.0),
            }
        )
    return result


def _ahu_sensible_demand(building, timeseries, heat_setpoint, cool_setpoint, hours):
    """Return independent monthly sensible AHU heating and cooling [kWh].

    The calculation uses the mapped outdoor-air ratio, sensible recovery and
    supply temperatures. It is deliberately separate from the zone balance so
    the comparison exposes the same zone-plus-coil boundary as the reference.
    """
    if not _int(building.get("ahu_enabled")):
        return 0.0, 0.0

    heating_fraction = _fraction(timeseries, "heating_operation_fraction")
    cooling_fraction = _fraction(timeseries, "cooling_operation_fraction")
    if heating_fraction + cooling_fraction > 1.0 + 1e-12:
        raise ValueError("heating and cooling operation fractions overlap")

    h_vent_raw = (
        DEFAULTS["rho_air"]
        * DEFAULTS["cp_air"]
        * _float(building["mechanical_ventilation_m3_h"])
        / 3600.0
    )
    outdoor = _float(timeseries["outdoor_temp_C"])
    recovery = _float(building.get("ahu_sensible_recovery_efficiency"))
    outdoor_ratio = _float(building.get("ahu_outdoor_air_ratio"), 1.0)
    if not 0.0 <= recovery <= 1.0:
        raise ValueError("ahu_sensible_recovery_efficiency must be between 0 and 1")
    if not 0.0 < outdoor_ratio <= 1.0:
        raise ValueError("ahu_outdoor_air_ratio must be in (0, 1]")

    def coil_load(return_temp, supply_temp, fraction):
        recovered_outdoor = outdoor + recovery * (return_temp - outdoor)
        mixed = outdoor_ratio * recovered_outdoor + (1.0 - outdoor_ratio) * return_temp
        return h_vent_raw * (supply_temp - mixed) * hours * fraction / 1000.0

    neutral_fraction = max(0.0, 1.0 - heating_fraction - cooling_fraction)
    neutral_return = 0.5 * (heat_setpoint + cool_setpoint)
    signed_loads = (
        coil_load(
            heat_setpoint,
            _float(building.get("ahu_supply_heating_C"), heat_setpoint),
            heating_fraction,
        ),
        coil_load(
            cool_setpoint,
            _float(building.get("ahu_supply_cooling_C"), cool_setpoint),
            cooling_fraction,
        ),
        coil_load(
            neutral_return,
            _float(building.get("ahu_supply_cooling_C"), cool_setpoint),
            neutral_fraction,
        ),
    )
    return sum(max(0.0, load) for load in signed_loads), sum(
        max(0.0, -load) for load in signed_loads
    )


def monthly_demand(building, scenario, timeseries, coef):
    days = _float(timeseries["days"])
    hours = days * 24.0
    outdoor = _float(timeseries["outdoor_temp_C"])
    occupancy = _float(timeseries["occupancy_fraction"], 1.0)
    occ_mult = _scenario_value(scenario, "occupancy_multiplier")
    operation_mult = _scenario_value(scenario, "operation_multiplier")
    solar_mult = _scenario_value(scenario, "solar_gain_multiplier")
    n_occ = _float(building["occupant_count"]) * occ_mult
    electric_power = _float(timeseries["lighting_appliance_power_W"]) * operation_mult

    g_value = _float(building["glazing_g_value"])
    shading = _float(building["shading_factor"])
    frame = _float(building["frame_fraction"])
    solar_gain = 0.0
    for orientation in ORIENTATIONS:
        area = _float(building[f"window_{orientation}_area_m2"])
        aperture = area * g_value * shading * (1.0 - frame)
        solar_gain += aperture * _orientation_irradiation(timeseries, orientation)
    solar_gain *= solar_mult

    occupant_gain_W = n_occ * DEFAULTS["occupant_gain_W"] * occupancy
    internal_gain = (
        occupant_gain_W + _float(building["electricity_to_heat_fraction"]) * electric_power
    ) * hours / 1000.0
    lighting_appliance_energy = electric_power * hours / 1000.0
    total_gains = solar_gain + internal_gain

    heat_setpoint = _float(building["heating_setpoint_C"]) + _float(
        scenario.get("heating_setpoint_delta_K")
    )
    cool_setpoint = _float(building["cooling_setpoint_C"]) + _float(
        scenario.get("cooling_setpoint_delta_K")
    )
    enhanced = _int(building.get("seasonal_ahu_comparison_enabled"))
    heating_fraction = _fraction(timeseries, "heating_operation_fraction") if enhanced else 1.0
    cooling_fraction = _fraction(timeseries, "cooling_operation_fraction") if enhanced else 1.0
    if enhanced:
        # The zone sees AHU supply air, while the coil is calculated separately.
        # Direct ventilation/infiltration and transmission retain outdoor air as
        # their boundary. This avoids counting the AHU's external-air load twice.
        h_direct = (
            coef["H_transmission_W_K"]
            + coef["H_ground_W_K"]
            + coef["H_infiltration_W_K"]
        )
        h_vent_raw = coef["H_ventilation_raw_W_K"]
        q_heat_transfer = (
            h_direct * (heat_setpoint - outdoor)
            + h_vent_raw
            * (heat_setpoint - _float(building.get("ahu_supply_heating_C"), outdoor))
        ) * hours * heating_fraction / 1000.0
    else:
        q_heat_transfer = coef["H_total_W_K"] * (heat_setpoint - outdoor) * hours / 1000.0
    if q_heat_transfer <= 0:
        gamma_h = None
        eta_h = 0.0
        useful_heating = 0.0
    else:
        gamma_h = total_gains / q_heat_transfer
        eta_h = utilisation_factor_heating(gamma_h, coef["utilisation_exponent"])
        useful_heating = max(0.0, q_heat_transfer - eta_h * total_gains)

    if enhanced:
        q_cool_transfer = (
            h_direct * (cool_setpoint - outdoor)
            + h_vent_raw
            * (cool_setpoint - _float(building.get("ahu_supply_cooling_C"), outdoor))
        ) * hours * cooling_fraction / 1000.0
    else:
        q_cool_transfer = coef["H_total_W_K"] * (cool_setpoint - outdoor) * hours / 1000.0
    if enhanced and cooling_fraction <= 0.0:
        gamma_c = None
        eta_c = 0.0
        zone_cooling = 0.0
    else:
        if enhanced:
            q_cool_transfer = max(1e-12, q_cool_transfer)
        # The validated monthly method defines the cooling ratio as gains over
        # heat transfer. The reciprocal below is retained only by legacy mode
        # so its protected reference outputs remain byte-for-byte unchanged.
        gamma_c = (
            total_gains / q_cool_transfer
            if enhanced and q_cool_transfer != 0
            else q_cool_transfer / total_gains
            if total_gains != 0
            else None
        )
        eta_c = utilisation_factor_cooling(gamma_c, coef["utilisation_exponent"])
        zone_cooling = _int(building["cooling_enabled"]) * max(
            0.0, total_gains - eta_c * q_cool_transfer
        )
    zone_heating = useful_heating
    ahu_heating, ahu_cooling = (
        _ahu_sensible_demand(building, timeseries, heat_setpoint, cool_setpoint, hours)
        if enhanced
        else (0.0, 0.0)
    )
    useful_heating = zone_heating + ahu_heating
    useful_cooling = zone_cooling + ahu_cooling
    useful_dhw = (
        DEFAULTS["dhw_kWh_person_day"]
        * n_occ
        * occupancy
        * days
        * _scenario_value(scenario, "dhw_multiplier")
    )

    result = {
        "days": days,
        "hours": hours,
        "outdoor_temp_C": outdoor,
        "solar_gain_kWh": solar_gain,
        "internal_gain_kWh": internal_gain,
        "total_gain_kWh": total_gains,
        "lighting_appliance_kWh": lighting_appliance_energy,
        "heat_transfer_kWh": q_heat_transfer,
        "gamma_heating": gamma_h,
        "eta_heating": eta_h,
        "useful_heating_kWh": useful_heating,
        "cool_transfer_kWh": q_cool_transfer,
        "gamma_cooling": gamma_c,
        "eta_cooling": eta_c,
        "useful_cooling_kWh": useful_cooling,
        "useful_dhw_kWh": useful_dhw,
    }
    if enhanced:
        result.update(
            {
                "heating_operation_fraction": heating_fraction,
                "cooling_operation_fraction": cooling_fraction,
                "zone_sensible_heating_kWh": zone_heating,
                "zone_sensible_cooling_kWh": zone_cooling,
                "ahu_sensible_heating_kWh": ahu_heating,
                "ahu_sensible_cooling_kWh": ahu_cooling,
            }
        )
    return result


def system_conversion(building, scenario, timeseries, demand, systems, factors, coef):
    config = _int(building["configuration_id"])
    outdoor = demand["outdoor_temp_C"]
    sys_eff_mult = _scenario_value(scenario, "system_efficiency_multiplier")
    system = {service: systems[(config, service)] for service in SERVICES}
    efficiency = {
        service: system_efficiency(system[service], outdoor) * sys_eff_mult
        for service in SERVICES
    }

    if config == 3:
        primary_share = 1.0 if outdoor >= _float(building["bivalent_temp_C"]) else 0.0
    else:
        primary_share = 1.0
    secondary_share = 1.0 - primary_share

    st_irradiation = _orientation_irradiation(timeseries, building["solar_thermal_orientation"])
    solar_thermal = min(
        demand["useful_dhw_kWh"],
        _int(building["solar_thermal_enabled"])
        * _float(building["solar_thermal_area_m2"])
        * _float(building["solar_thermal_efficiency"])
        * st_irradiation,
    )
    net_dhw = max(0.0, demand["useful_dhw_kWh"] - solar_thermal)

    service_energy = {
        "H_pri": demand["useful_heating_kWh"] * primary_share / efficiency["H_pri"],
        "H_sec": demand["useful_heating_kWh"] * secondary_share / efficiency["H_sec"],
        "W_pri": net_dhw * primary_share / efficiency["W_pri"],
        "W_sec": net_dhw * secondary_share / efficiency["W_sec"],
        "C": demand["useful_cooling_kWh"] / efficiency["C"],
    }
    delivered = {carrier: 0.0 for carrier in CARRIERS}
    for service, energy in service_energy.items():
        carrier = system[service]["carrier"]
        if carrier in delivered:
            delivered[carrier] += energy

    auxiliary = (
        DEFAULTS["sfp_W_per_m3_s"] * coef["q_ve_m3_h"] / 3600.0
        + DEFAULTS["aux_W_m2"] * _float(building["conditioned_floor_area_m2"])
    ) * demand["hours"] / 1000.0
    gross_electricity = delivered["electricity"] + auxiliary + demand["lighting_appliance_kWh"]
    pv_irradiation = _orientation_irradiation(timeseries, building["pv_orientation"])
    pv_generation = (
        _int(building["pv_enabled"])
        * _float(building["pv_peak_kWp"])
        * _float(building["pv_performance_ratio"])
        * pv_irradiation
        * _scenario_value(scenario, "pv_multiplier")
    )
    pv_self_used = min(gross_electricity, pv_generation)
    pv_exported = max(0.0, pv_generation - gross_electricity)
    delivered["electricity"] = gross_electricity - pv_self_used

    primary_energy = sum(
        delivered[carrier] * factors[carrier]["primary_energy_factor"] for carrier in CARRIERS
    )
    carbon = sum(
        delivered[carrier] * factors[carrier]["carbon_factor_kgCO2e_kWh"]
        for carrier in CARRIERS
    )
    service_sum = sum(service_energy.values()) + auxiliary + demand["lighting_appliance_kWh"]
    carrier_balance = sum(delivered.values()) + pv_self_used - service_sum

    return {
        **{f"eff_{key}": value for key, value in efficiency.items()},
        **{f"energy_{key}_kWh": value for key, value in service_energy.items()},
        "primary_share": primary_share,
        "solar_thermal_kWh": solar_thermal,
        "auxiliary_kWh": auxiliary,
        "pv_generation_kWh": pv_generation,
        "pv_self_used_kWh": pv_self_used,
        "pv_exported_kWh": pv_exported,
        "delivered_electricity_kWh": delivered["electricity"],
        "delivered_natural_gas_kWh": delivered["natural_gas"],
        "delivered_district_heat_kWh": delivered["district_heat"],
        "delivered_total_kWh": sum(delivered.values()),
        "primary_energy_kWh": primary_energy,
        "operational_carbon_kgCO2e": carbon,
        "carrier_balance_residual_kWh": carrier_balance,
    }


def load_inputs(data_dir):
    data_dir = Path(data_dir)
    buildings = read_csv(data_dir / "buildings.csv")
    scenarios = read_csv(data_dir / "scenarios.csv")
    timeseries = read_csv(data_dir / "timeseries.csv")
    systems_rows = read_csv(data_dir / "systems.csv")
    factor_rows = read_csv(data_dir / "factors.csv")
    metered = read_csv(data_dir / "metered.csv")
    systems = {(_int(row["configuration_id"]), row["service"]): row for row in systems_rows}
    factors_by_scenario = defaultdict(dict)
    for row in factor_rows:
        factors_by_scenario[row["scenario_id"]][row["carrier"]] = {
            "primary_energy_factor": _float(row["primary_energy_factor"]),
            "carbon_factor_kgCO2e_kWh": _float(row["carbon_factor_kgCO2e_kWh"]),
        }
    return buildings, scenarios, timeseries, systems, factors_by_scenario, metered


def run_forward(data_dir):
    buildings, scenarios, timeseries, systems, factors_by_scenario, metered = load_inputs(data_dir)
    building_map = {row["building_id"]: row for row in buildings}
    scenario_map = {(row["building_id"], row["scenario_id"]): row for row in scenarios}
    rows = []
    for ts in timeseries:
        key = (ts["building_id"], ts["scenario_id"])
        building = building_map[ts["building_id"]]
        scenario = scenario_map[key]
        coef = building_coefficients(building, scenario)
        demand = monthly_demand(building, scenario, ts, coef)
        system = system_conversion(
            building, scenario, ts, demand, systems, factors_by_scenario[ts["scenario_id"]], coef
        )
        rows.append(
            {
                "building_id": ts["building_id"],
                "scenario_id": ts["scenario_id"],
                "period_id": ts["period_id"],
                **coef,
                **demand,
                **system,
            }
        )
    return rows, metered


def changepoint_grid(h_min=8.0, h_max=20.0, c_min=14.0, c_max=26.0, step=0.5):
    heating = [h_min + i * step for i in range(round((h_max - h_min) / step) + 1)]
    cooling = [c_min + i * step for i in range(round((c_max - c_min) / step) + 1)]
    return [(h, c) for h in heating for c in cooling if c >= h]


def _ols3(y, x1, x2, tolerance=1e-10):
    n = len(y)
    s1, s2 = sum(x1), sum(x2)
    s11, s22 = sum(v * v for v in x1), sum(v * v for v in x2)
    s12 = sum(a * b for a, b in zip(x1, x2))
    sy = sum(y)
    s1y = sum(a * b for a, b in zip(x1, y))
    s2y = sum(a * b for a, b in zip(x2, y))
    determinant = (
        n * (s11 * s22 - s12**2)
        - s1 * (s1 * s22 - s12 * s2)
        + s2 * (s1 * s12 - s11 * s2)
    )
    if abs(determinant) < tolerance:
        return None
    beta0 = (
        sy * (s11 * s22 - s12**2)
        - s1 * (s1y * s22 - s12 * s2y)
        + s2 * (s1y * s12 - s11 * s2y)
    ) / determinant
    beta_h = (
        n * (s1y * s22 - s12 * s2y)
        - sy * (s1 * s22 - s12 * s2)
        + s2 * (s1 * s2y - s1y * s2)
    ) / determinant
    beta_c = (
        n * (s11 * s2y - s1y * s12)
        - s1 * (s1 * s2y - s1y * s2)
        + sy * (s1 * s12 - s11 * s2)
    ) / determinant
    sse = sum((yy - beta0 - beta_h * a - beta_c * b) ** 2 for yy, a, b in zip(y, x1, x2))
    return beta0, beta_h, beta_c, sse


def fit_change_point(theta_e, days, energy):
    """Fit a five-parameter monthly change-point model without an Excel grid."""
    if len(energy) < 6 or any(value is None for value in energy):
        return None
    daily = [energy_value / day for energy_value, day in zip(energy, days)]
    best = None
    for heating_cp, cooling_cp in changepoint_grid():
        x_heat = [max(0.0, heating_cp - temp) for temp in theta_e]
        x_cool = [max(0.0, temp - cooling_cp) for temp in theta_e]
        result = _ols3(daily, x_heat, x_cool)
        if result is not None and (best is None or result[3] < best[0][3]):
            best = (result, heating_cp, cooling_cp)
    if best is None:
        return None
    (beta0, beta_h, beta_c, sse), heating_cp, cooling_cp = best
    mean = sum(daily) / len(daily)
    centered = sum((value - mean) ** 2 for value in daily)
    return {
        "beta_base_kWh_day": beta0,
        "beta_heating_kWh_day_K": beta_h,
        "heating_change_point_C": heating_cp,
        "beta_cooling_kWh_day_K": beta_c,
        "cooling_change_point_C": cooling_cp,
        "SSE_daily": sse,
        "R2": 1.0 - sse / centered if centered else None,
        "observations": len(energy),
        "degrees_of_freedom": len(energy) - 5,
    }


def predict_change_point(parameters, theta_e, days):
    return [
        day
        * (
            parameters["beta_base_kWh_day"]
            + parameters["beta_heating_kWh_day_K"]
            * max(0.0, parameters["heating_change_point_C"] - temp)
            + parameters["beta_cooling_kWh_day_K"]
            * max(0.0, temp - parameters["cooling_change_point_C"])
        )
        for temp, day in zip(theta_e, days)
    ]


def nmbe(simulated, reference):
    mean = sum(reference) / len(reference)
    return None if mean == 0 else (sum(simulated) - sum(reference)) / (len(reference) * mean) * 100.0


def cvrmse(simulated, reference):
    mean = sum(reference) / len(reference)
    if mean == 0:
        return None
    return math.sqrt(
        sum((sim - ref) ** 2 for sim, ref in zip(simulated, reference)) / len(reference)
    ) / mean * 100.0


def r_squared(observed, predicted):
    mean = sum(observed) / len(observed)
    total = sum((value - mean) ** 2 for value in observed)
    return None if total == 0 else 1.0 - sum(
        (obs - pred) ** 2 for obs, pred in zip(observed, predicted)
    ) / total


def metric_record(simulated, reference):
    bias = nmbe(simulated, reference)
    variation = cvrmse(simulated, reference)
    return {
        "NMBE_pct": bias,
        "CVRMSE_pct": variation,
        "passed_monthly_threshold": (
            bias is not None
            and variation is not None
            and abs(bias) <= DEFAULTS["nmbe_limit_pct"]
            and variation <= DEFAULTS["cvrmse_limit_pct"]
        ),
    }


def calibrate(forward_rows, metered_rows):
    forward_by_key = {
        (row["building_id"], row["scenario_id"], row["period_id"]): row for row in forward_rows
    }
    groups = defaultdict(list)
    for row in metered_rows:
        groups[(row["building_id"], row["scenario_id"], row["carrier"])].append(row)

    parameters_rows = []
    fitted_rows = []
    metric_rows = []
    for (building_id, scenario_id, carrier), rows in groups.items():
        rows.sort(key=lambda item: item["period_id"])
        forward = [forward_by_key[(building_id, scenario_id, row["period_id"])] for row in rows]
        temperature = [item["outdoor_temp_C"] for item in forward]
        days = [item["days"] for item in forward]
        measured = [_float(row["measured_energy_kWh"]) for row in rows]
        fit = fit_change_point(temperature, days, measured)
        if fit is None:
            continue
        predicted = predict_change_point(fit, temperature, days)
        simulated = [item[f"delivered_{carrier}_kWh"] for item in forward]
        parameter_row = {
            "building_id": building_id,
            "scenario_id": scenario_id,
            "carrier": carrier,
            **fit,
        }
        parameters_rows.append(parameter_row)
        for source, fit_value, sim_value, measured_row in zip(rows, predicted, simulated, measured):
            fitted_rows.append(
                {
                    "building_id": building_id,
                    "scenario_id": scenario_id,
                    "period_id": source["period_id"],
                    "carrier": carrier,
                    "measured_energy_kWh": measured_row,
                    "inverse_fitted_kWh": fit_value,
                    "forward_simulated_kWh": sim_value,
                    "inverse_residual_kWh": measured_row - fit_value,
                    "forward_residual_kWh": measured_row - sim_value,
                }
            )
        forward_metric = metric_record(simulated, measured)
        inverse_metric = metric_record(predicted, measured)
        metric_rows.append(
            {
                "building_id": building_id,
                "scenario_id": scenario_id,
                "carrier": carrier,
                "forward_NMBE_pct": forward_metric["NMBE_pct"],
                "forward_CVRMSE_pct": forward_metric["CVRMSE_pct"],
                "forward_passed": forward_metric["passed_monthly_threshold"],
                "inverse_NMBE_pct": inverse_metric["NMBE_pct"],
                "inverse_CVRMSE_pct": inverse_metric["CVRMSE_pct"],
                "inverse_R2": r_squared(measured, predicted),
                "inverse_passed": inverse_metric["passed_monthly_threshold"],
                "max_carrier_balance_residual_kWh": max(
                    abs(item["carrier_balance_residual_kWh"]) for item in forward
                ),
            }
        )
    return parameters_rows, fitted_rows, metric_rows


def annual_summary(forward_rows):
    grouped = defaultdict(list)
    for row in forward_rows:
        grouped[(row["building_id"], row["scenario_id"])].append(row)
    fields = [
        "useful_heating_kWh",
        "useful_cooling_kWh",
        "useful_dhw_kWh",
        "solar_thermal_kWh",
        "pv_generation_kWh",
        "pv_self_used_kWh",
        "pv_exported_kWh",
        "delivered_electricity_kWh",
        "delivered_natural_gas_kWh",
        "delivered_district_heat_kWh",
        "delivered_total_kWh",
        "primary_energy_kWh",
        "operational_carbon_kgCO2e",
    ]
    output = []
    for (building_id, scenario_id), rows in grouped.items():
        output.append(
            {
                "building_id": building_id,
                "scenario_id": scenario_id,
                **{field: sum(row[field] for row in rows) for field in fields},
            }
        )
    return output


def run(data_dir, output_dir):
    output_dir = Path(output_dir)
    forward_rows, metered = run_forward(data_dir)
    parameters, fitted, metrics = calibrate(forward_rows, metered)
    write_csv(output_dir / "forward_monthly.csv", forward_rows)
    write_csv(output_dir / "forward_annual.csv", annual_summary(forward_rows))
    write_csv(output_dir / "calibration_parameters.csv", parameters)
    write_csv(output_dir / "calibration_monthly.csv", fitted)
    write_csv(output_dir / "validation_metrics.csv", metrics)
    return forward_rows, parameters, fitted, metrics
