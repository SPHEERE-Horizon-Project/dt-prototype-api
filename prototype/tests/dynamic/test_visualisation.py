"""Tests for the visualisation layer (FR-17, FR-18) — headless rendering."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pytest
from matplotlib.figure import Figure

from dt_prototype.dynamic.postprocessing.aggregation import to_monthly
from dt_prototype.dynamic.simulation.config import SimulationConfig
from dt_prototype.dynamic.simulation.runner import run_building, run_portfolio
from dt_prototype.dynamic.visualisation.plots import plot_loads, plot_monthly_energy, plot_temperatures
from dt_prototype.dynamic.visualisation.report import building_report, portfolio_report


@pytest.fixture(scope="module")
def results(district):
    """Ideal-load 7R2C run of one example building (module-cached)."""
    building = district.buildings[1]
    df = run_building(building, district.weather, SimulationConfig(model="7R2C"))
    return building, df


def test_plot_loads_returns_figure(results):
    """Time-series load plot renders and carries a legend (FR-17)."""
    _, df = results
    fig = plot_loads(df.iloc[: 24 * 7])
    assert isinstance(fig, Figure)
    assert fig.axes[0].get_legend() is not None
    plt.close(fig)


def test_plot_temperatures(district, results):
    """Temperature plot renders with outdoor context (FR-17)."""
    _, df = results
    fig = plot_temperatures(df.iloc[:168], district.weather.df["temp_air"].iloc[:168])
    assert isinstance(fig, Figure)
    plt.close(fig)


def test_plot_monthly_energy(results):
    """Monthly bar chart renders 12 groups from the aggregation table."""
    _, df = results
    fig = plot_monthly_energy(to_monthly(df))
    assert isinstance(fig, Figure)
    assert len(fig.axes[0].get_xticklabels()) == 12
    plt.close(fig)


def test_building_report(results):
    """The single-building report composes four panels (FR-18)."""
    building, df = results
    fig = building_report(df, building.name, building.geometry.net_floor_area)
    assert isinstance(fig, Figure)
    assert len(fig.axes) == 4
    plt.close(fig)


def test_portfolio_report(district):
    """The portfolio report renders for the whole district (FR-18)."""
    results = run_portfolio(district, SimulationConfig(model="5R1C", latent=False))
    areas = {b.name: b.geometry.net_floor_area for b in district.buildings}
    fig = portfolio_report(results, areas)
    assert isinstance(fig, Figure)
    assert len(fig.axes) == 2
    plt.close(fig)
