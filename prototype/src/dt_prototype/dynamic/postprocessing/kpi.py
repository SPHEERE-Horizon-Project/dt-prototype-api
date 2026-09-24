"""Energy performance indicators (FR-15) and portfolio KPI tables (FR-16).

EXTENSION POINT (new KPIs, NFR-06): add a computation to
:func:`building_kpis` — downstream consumers (portfolio table, reports)
pick up new keys automatically.
"""

from __future__ import annotations

import pandas as pd

from dt_prototype.dynamic.postprocessing.aggregation import _timestep_hours


def building_kpis(results: pd.DataFrame, net_floor_area: float) -> dict[str, float]:
    """Standard KPIs of one building from the runner output.

    Parameters
    ----------
    results : pandas.DataFrame
        Time-indexed runner output (see ``run_building``).
    net_floor_area : float
        Net floor area [m2] for the specific (per-m2) indicators.

    Returns
    -------
    dict
        Annual energies [kWh], specific intensities [kWh/m2], peak loads
        [kW] and comfort statistics. Keys include ``heating_demand_kwh``,
        ``cooling_demand_kwh``, ``peak_heating_kw``, ``peak_cooling_kw``,
        ``dhw_demand_kwh``, latent/AHU terms when present, and carrier
        totals (gas, electricity, PV) when the run included plants.
    """
    if net_floor_area <= 0.0:
        raise ValueError("net_floor_area must be positive")
    dt_h = _timestep_hours(results)

    def energy(col: str, sign: float = 1.0) -> float:
        """Annual energy of a power column [kWh] (empty → 0)."""
        if col not in results:
            return 0.0
        series = results[col] * sign
        return float(series.clip(lower=0.0).sum() * dt_h / 1000.0)

    kpis: dict[str, float] = {
        "heating_demand_kwh": energy("heating_load"),
        "cooling_demand_kwh": energy("cooling_load", sign=-1.0),
        "dhw_demand_kwh": energy("dhw_demand"),
        "humidification_demand_kwh": energy("latent_load"),
        "dehumidification_demand_kwh": energy("latent_load", sign=-1.0),
        "ahu_heating_demand_kwh": energy("ahu_sensible_load"),
        "ahu_cooling_demand_kwh": energy("ahu_sensible_load", sign=-1.0),
        "appliance_electricity_kwh": energy("electric_appliances"),
        "peak_heating_kw": float(results["heating_load"].max() / 1000.0),
        "peak_cooling_kw": float(-results["cooling_load"].min() / 1000.0),
        "mean_air_temperature_c": float(results["air_temperature"].mean()),
        "mean_relative_humidity": float(results["relative_humidity"].mean()),
    }
    # carrier totals, present only for plant runs
    for col, key in (
        ("electric_plant", "plant_electricity_kwh"),
        ("gas", "gas_use_kwh"),
        ("district_heat", "district_heat_kwh"),
        ("other_fuel", "other_fuel_kwh"),
        ("pv_production", "pv_production_kwh"),
        ("solar_thermal_production", "solar_thermal_kwh"),
        ("pv_self_consumed", "pv_self_consumed_kwh"),
        ("grid_import", "grid_import_kwh"),
        ("grid_export", "grid_export_kwh"),
    ):
        if col in results:
            kpis[key] = energy(col)

    # specific intensities [kWh/m2]
    for key in (
        "heating_demand_kwh",
        "cooling_demand_kwh",
        "dhw_demand_kwh",
        "appliance_electricity_kwh",
    ):
        kpis[key.replace("_kwh", "_kwh_m2")] = kpis[key] / net_floor_area
    return kpis


def portfolio_kpis(
    results: dict[str, pd.DataFrame], net_floor_areas: dict[str, float]
) -> pd.DataFrame:
    """KPI table for a portfolio: one row per building plus a ``TOTAL`` row
    (FR-16).

    Parameters
    ----------
    results : dict
        Building name → runner output DataFrame.
    net_floor_areas : dict
        Building name → net floor area [m2].

    Returns
    -------
    pandas.DataFrame
        Indexed by building name; energy columns are summed in the TOTAL
        row, specific/mean columns are floor-area weighted.
    """
    rows = {
        name: building_kpis(df, net_floor_areas[name]) for name, df in results.items()
    }
    table = pd.DataFrame.from_dict(rows, orient="index")

    total_area = sum(net_floor_areas[name] for name in results)
    totals = {}
    for col in table.columns:
        if col.endswith("_kwh") or col.endswith("_kw"):
            totals[col] = table[col].sum()
        elif col.endswith("_kwh_m2"):
            totals[col] = table[col.replace("_kwh_m2", "_kwh")].sum() / total_area
        else:  # mean state values: floor-area weighted average
            weights = pd.Series({n: net_floor_areas[n] for n in table.index})
            totals[col] = float((table[col] * weights).sum() / weights.sum())
    table.loc["TOTAL"] = totals
    return table
