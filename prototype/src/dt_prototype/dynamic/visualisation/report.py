"""Summary reports for single buildings and portfolios (FR-18).

Composed from the postprocessing layer's aggregations and KPIs; figures are
returned, never shown or saved (NFR-04).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from dt_prototype.dynamic.postprocessing.aggregation import to_daily, to_monthly
from dt_prototype.dynamic.postprocessing.kpi import building_kpis, portfolio_kpis
from dt_prototype.dynamic.visualisation.plots import _label_color
from dt_prototype.dynamic.visualisation.style import INK_PRIMARY, INK_SECONDARY, SERIES_COLORS, style_axes


def building_report(
    results: pd.DataFrame, name: str, net_floor_area: float
) -> Figure:
    """One-page summary of a single-building run (FR-18).

    Panels: monthly heating/cooling/DHW energy; daily thermal load profile;
    monthly mean zone temperature and relative humidity band; headline KPIs.

    Parameters
    ----------
    results : pandas.DataFrame
        Runner output.
    name : str
        Building name (title).
    net_floor_area : float
        Net floor area [m2] for specific KPIs.

    Returns
    -------
    matplotlib.figure.Figure
    """
    monthly = to_monthly(results)
    daily = to_daily(results)
    kpis = building_kpis(results, net_floor_area)

    fig, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
    fig.suptitle(f"Building report — {name}", color=INK_PRIMARY, fontsize=13)

    # (0,0) monthly energy bars
    ax = axes[0, 0]
    months = [ts.strftime("%b") for ts in monthly.index]
    x = range(len(monthly))
    bars = [c for c in ("heating_load_kWh", "cooling_load_kWh", "dhw_demand_kWh") if c in monthly]
    width = 0.8 / len(bars)
    for i, col in enumerate(bars):
        label, color = _label_color(col.replace("_kWh", ""))
        ax.bar(
            [xi + (i - (len(bars) - 1) / 2) * width for xi in x],
            monthly[col].abs(), width=width * 0.92, label=label, color=color,
        )
    ax.set_xticks(list(x))
    ax.set_xticklabels(months)
    ax.set_ylabel("Energy [kWh]")
    ax.set_title("Monthly energy")
    style_axes(ax)
    ax.legend(frameon=False, fontsize=8)

    # (0,1) daily load profile
    ax = axes[0, 1]
    ax.plot(
        daily.index, daily["heating_load_kWh"], color=SERIES_COLORS["heating"],
        linewidth=1.0, label="Heating",
    )
    ax.plot(
        daily.index, -daily["cooling_load_kWh"], color=SERIES_COLORS["cooling"],
        linewidth=1.0, label="Cooling",
    )
    ax.set_ylabel("Daily energy [kWh/day]")
    ax.set_title("Daily thermal loads")
    style_axes(ax)
    ax.legend(frameon=False, fontsize=8)

    # (1,0) monthly indoor climate
    ax = axes[1, 0]
    ax.plot(
        monthly.index, monthly["air_temperature_mean"],
        color=SERIES_COLORS["temperature"], linewidth=1.5, label="Air temperature",
    )
    ax.set_ylabel("Temperature [°C]")
    ax.set_title("Monthly mean indoor air temperature")
    style_axes(ax)
    # relative humidity has a different scale (dual axes avoided by design):
    # it is reported in the KPI panel instead

    # (1,1) headline KPIs as text panel
    ax = axes[1, 1]
    ax.axis("off")
    lines = [
        f"Net floor area:        {net_floor_area:,.0f} m²",
        f"Heating demand:        {kpis['heating_demand_kwh_m2']:.1f} kWh/m²",
        f"Cooling demand:        {kpis['cooling_demand_kwh_m2']:.1f} kWh/m²",
        f"DHW demand:            {kpis['dhw_demand_kwh_m2']:.1f} kWh/m²",
        f"Peak heating:          {kpis['peak_heating_kw']:.1f} kW",
        f"Peak cooling:          {kpis['peak_cooling_kw']:.1f} kW",
        f"Mean air temperature:  {kpis['mean_air_temperature_c']:.1f} °C",
        f"Mean rel. humidity:    {kpis['mean_relative_humidity'] * 100:.0f} %",
    ]
    if "gas_use_kwh" in kpis:
        lines.append(f"Gas use:               {kpis['gas_use_kwh']:,.0f} kWh")
    if "plant_electricity_kwh" in kpis:
        lines.append(f"Plant electricity:     {kpis['plant_electricity_kwh']:,.0f} kWh")
    if kpis.get("pv_production_kwh"):
        lines.append(f"PV production:         {kpis['pv_production_kwh']:,.0f} kWh")
    ax.text(
        0.02, 0.95, "\n".join(lines), transform=ax.transAxes, va="top",
        family="monospace", fontsize=10, color=INK_SECONDARY,
    )
    ax.set_title("Annual KPIs")
    return fig


def portfolio_report(
    results: dict[str, pd.DataFrame], net_floor_areas: dict[str, float]
) -> Figure:
    """Portfolio summary: specific demands per building and the district
    daily load profile (FR-18).

    Parameters
    ----------
    results : dict
        Building name → runner output.
    net_floor_areas : dict
        Building name → net floor area [m2].

    Returns
    -------
    matplotlib.figure.Figure
    """
    table = portfolio_kpis(results, net_floor_areas).drop(index="TOTAL")

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(12, 4.5), constrained_layout=True, width_ratios=[1, 1.4]
    )
    fig.suptitle("Portfolio report", color=INK_PRIMARY, fontsize=13)

    # left: specific demands per building (horizontal grouped bars)
    names = list(table.index)
    y = range(len(names))
    height = 0.38
    ax1.barh(
        [yi + height / 2 for yi in y], table["heating_demand_kwh_m2"],
        height=height * 0.92, color=SERIES_COLORS["heating"], label="Heating",
    )
    ax1.barh(
        [yi - height / 2 for yi in y], table["cooling_demand_kwh_m2"],
        height=height * 0.92, color=SERIES_COLORS["cooling"], label="Cooling",
    )
    ax1.set_yticks(list(y))
    ax1.set_yticklabels(names, fontsize=9)
    ax1.invert_yaxis()
    ax1.set_xlabel("Specific demand [kWh/m²]")
    ax1.set_title("Annual demand by building")
    style_axes(ax1)
    ax1.grid(axis="x", visible=True)
    ax1.grid(axis="y", visible=False)
    ax1.legend(frameon=False, fontsize=8)

    # right: district daily thermal load profile
    district_daily = None
    for df in results.values():
        daily = to_daily(df)[["heating_load_kWh", "cooling_load_kWh"]]
        district_daily = daily if district_daily is None else district_daily + daily
    ax2.plot(
        district_daily.index, district_daily["heating_load_kWh"] / 1000.0,
        color=SERIES_COLORS["heating"], linewidth=1.0, label="Heating",
    )
    ax2.plot(
        district_daily.index, -district_daily["cooling_load_kWh"] / 1000.0,
        color=SERIES_COLORS["cooling"], linewidth=1.0, label="Cooling",
    )
    ax2.set_ylabel("District daily energy [MWh/day]")
    ax2.set_title("District thermal load profile")
    style_axes(ax2)
    ax2.legend(frameon=False, fontsize=8)
    return fig
