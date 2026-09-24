"""Convenience functions for monthly semi-stationary portfolio calculations."""

from __future__ import annotations

import pandas as pd

from dt_prototype.common.preprocessing.building_input import BuildingInput, DistrictInput
from dt_prototype.common.preprocessing.weather import WeatherData
from dt_prototype.monthly.simulation.config import SimulationConfig
from dt_prototype.monthly.simulation.quasi_steady_state import run_quasi_steady_state


def run_building(
    building: BuildingInput,
    weather: WeatherData,
    config: SimulationConfig | None = None,
) -> pd.DataFrame:
    """Return the twelve monthly sensible-demand rows for one building."""
    return run_quasi_steady_state(building, weather, config)


def run_portfolio(
    district: DistrictInput, config: SimulationConfig | None = None
) -> dict[str, pd.DataFrame]:
    """Run every building in a preprocessed district."""
    return {building.name: run_building(building, district.weather, config) for building in district.buildings}


def annual_summary(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Aggregate monthly energy columns into one kWh row per building."""
    energy_columns = [
        column
        for column in next(iter(results.values())).columns
        if column.endswith("_kWh") and not column.startswith("zone_")
    ]
    return pd.DataFrame({name: frame[energy_columns].sum() for name, frame in results.items()}).T.rename_axis("building")
