"""Time-series plots of simulation results (FR-17).

All functions are side-effect free: they take runner/postprocessing
DataFrames, return a ``matplotlib.figure.Figure`` and never write files or
call ``plt.show()`` — the caller decides (FastAPI/notebook friendly, NFR-04).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from dt_prototype.dynamic.visualisation.style import SERIES_COLORS, style_axes

# result column → (display label, entity color key)
_COLUMN_STYLE = {
    "heating_load": ("Heating load", "heating"),
    "cooling_load": ("Cooling load", "cooling"),
    "sensible_load": ("Sensible load", "heating"),
    "latent_load": ("Latent load", "humidity"),
    "dhw_demand": ("DHW demand", "dhw"),
    "ahu_sensible_load": ("AHU sensible load", "gas"),
    "electric_appliances": ("Appliance electricity", "electricity"),
    "electric_plant": ("Plant electricity", "electricity"),
    "pv_production": ("PV production", "pv"),
    "gas": ("Gas use", "gas"),
    "air_temperature": ("Air temperature", "temperature"),
    "operative_temperature": ("Operative temperature", "heating"),
}


def _label_color(column: str) -> tuple[str, str]:
    """Display label and hex color for a result column."""
    label, key = _COLUMN_STYLE.get(column, (column.replace("_", " ").capitalize(), "electricity"))
    return label, SERIES_COLORS[key]


def plot_loads(
    results: pd.DataFrame,
    columns: tuple[str, ...] = ("heating_load", "cooling_load"),
    title: str = "Thermal loads",
) -> Figure:
    """Line plot of load/power columns [kW] over time (FR-17).

    Parameters
    ----------
    results : pandas.DataFrame
        Runner output (or any time-indexed power [W] DataFrame).
    columns : tuple of str
        Power columns to draw.
    title : str
        Figure title.

    Returns
    -------
    matplotlib.figure.Figure
    """
    fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
    for col in columns:
        if col not in results:
            continue
        label, color = _label_color(col)
        ax.plot(results.index, results[col] / 1000.0, label=label, color=color, linewidth=1.2)
    ax.set_ylabel("Power [kW]")
    ax.set_title(title)
    style_axes(ax)
    if len(columns) > 1:
        ax.legend(frameon=False, fontsize=9)
    return fig


def plot_temperatures(
    results: pd.DataFrame,
    weather_temp: pd.Series | None = None,
    title: str = "Zone temperatures",
) -> Figure:
    """Zone air/operative temperatures over time, optionally with the
    outdoor temperature for context (FR-17).

    Parameters
    ----------
    results : pandas.DataFrame
        Runner output with ``air_temperature``/``operative_temperature``.
    weather_temp : pandas.Series, optional
        Outdoor air temperature [°C] on the same index.
    title : str
        Figure title.

    Returns
    -------
    matplotlib.figure.Figure
    """
    fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
    if weather_temp is not None:
        ax.plot(
            weather_temp.index, weather_temp, label="Outdoor",
            color=SERIES_COLORS["outdoor"], linewidth=1.0,
        )
    ax.plot(
        results.index, results["air_temperature"], label="Zone air",
        color=SERIES_COLORS["temperature"], linewidth=1.2,
    )
    ax.plot(
        results.index, results["operative_temperature"], label="Operative",
        color=SERIES_COLORS["heating"], linewidth=1.2,
    )
    ax.set_ylabel("Temperature [°C]")
    ax.set_title(title)
    style_axes(ax)
    ax.legend(frameon=False, fontsize=9)
    return fig


def plot_monthly_energy(
    monthly: pd.DataFrame,
    columns: tuple[str, ...] = ("heating_load_kWh", "cooling_load_kWh", "dhw_demand_kWh"),
    title: str = "Monthly energy",
) -> Figure:
    """Grouped monthly energy bars [kWh] from a ``to_monthly`` table (FR-17).

    Cooling energy is shown with positive sign for readability.

    Parameters
    ----------
    monthly : pandas.DataFrame
        Output of :func:`dt_prototype.dynamic.postprocessing.aggregation.to_monthly`.
    columns : tuple of str
        Energy columns to draw as grouped bars.
    title : str
        Figure title.

    Returns
    -------
    matplotlib.figure.Figure
    """
    fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
    present = [c for c in columns if c in monthly.columns]
    n = len(present)
    width = 0.8 / max(n, 1)
    x = range(len(monthly))
    for i, col in enumerate(present):
        label, color = _label_color(col.replace("_kWh", ""))
        values = monthly[col].abs()  # cooling stored negative
        ax.bar(
            [xi + (i - (n - 1) / 2) * width for xi in x],
            values, width=width * 0.92, label=label, color=color,
        )
    ax.set_xticks(list(x))
    ax.set_xticklabels([ts.strftime("%b") for ts in monthly.index])
    ax.set_ylabel("Energy [kWh]")
    ax.set_title(title)
    style_axes(ax)
    if n > 1:
        ax.legend(frameon=False, fontsize=9)
    return fig
