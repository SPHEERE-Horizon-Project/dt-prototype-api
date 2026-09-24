"""Parity checks for GeoJSON and normalized tabular geometry routes."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dt_prototype.cli import main as cli_main
from dt_prototype.common.preprocessing.geometry import load_district_geojson
from dt_prototype.common.preprocessing.tabular_geometry import load_district_tables
from dt_prototype.common.project import ProjectInputs
from dt_prototype.dynamic.simulation.config import SimulationConfig as DynamicConfig
from dt_prototype.dynamic.simulation.runner import run_building as run_dynamic
from dt_prototype.monthly.run import run_building as run_monthly
from dt_prototype.monthly.simulation.config import SimulationConfig as MonthlyConfig


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "examples"
CONFIGS = ROOT / "configs"
ENERGY_COLUMNS = [
    "zone_heating_kWh",
    "zone_cooling_kWh",
    "ahu_heating_kWh",
    "ahu_cooling_kWh",
    "heating_kWh",
    "cooling_kWh",
]


@pytest.fixture(scope="module")
def equivalent_districts():
    geojson_project = ProjectInputs.load(CONFIGS / "example.json")
    tabular_project = ProjectInputs.load(CONFIGS / "example_tabular.json")
    return geojson_project.preprocess(), tabular_project.preprocess()


def test_tabular_geometry_exactly_reconstructs_all_five_geojson_cases():
    geojson = load_district_geojson(DATA / "example_district.geojson")
    tabular = load_district_tables(DATA / "tabular_geometry")
    assert [building.to_dict() for building in tabular] == [
        building.to_dict() for building in geojson
    ]


def test_monthly_engine_results_are_identical_for_both_input_routes(equivalent_districts):
    geojson, tabular = equivalent_districts
    config = MonthlyConfig()
    assert geojson.building_names == tabular.building_names
    for geojson_building, tabular_building in zip(geojson.buildings, tabular.buildings):
        expected = run_monthly(geojson_building, geojson.weather, config)
        actual = run_monthly(tabular_building, tabular.weather, config)
        pd.testing.assert_frame_equal(actual, expected, check_exact=True)


@pytest.mark.parametrize("building_index", [0, 4], ids=["two_zone", "single_zone"])
def test_dynamic_engine_results_are_identical_for_both_input_routes(
    equivalent_districts, building_index
):
    geojson, tabular = equivalent_districts
    config = DynamicConfig(model="5R1C", plants=False, latent=False)
    expected = run_dynamic(
        geojson.buildings[building_index],
        geojson.weather,
        config,
        system_templates=geojson.system_templates,
    )
    actual = run_dynamic(
        tabular.buildings[building_index],
        tabular.weather,
        config,
        system_templates=tabular.system_templates,
    )
    numeric = expected.select_dtypes(include="number").columns
    assert list(actual.columns) == list(expected.columns)
    assert np.array_equal(actual[numeric].to_numpy(), expected[numeric].to_numpy())


def test_simplified_cli_results_are_identical_for_both_input_routes(tmp_path):
    geojson_output = tmp_path / "simplified_geojson"
    tabular_output = tmp_path / "simplified_tabular"
    cli_main(
        [
            "simplified",
            "--config",
            str(CONFIGS / "example.json"),
            "--output",
            str(geojson_output),
            "--zone-mode",
            "sum",
        ]
    )
    cli_main(
        [
            "simplified",
            "--config",
            str(CONFIGS / "example_tabular.json"),
            "--output",
            str(tabular_output),
            "--zone-mode",
            "sum",
        ]
    )
    expected = pd.read_csv(geojson_output / "monthly.csv").sort_values(
        ["building_id", "period_id"]
    )
    actual = pd.read_csv(tabular_output / "monthly.csv").sort_values(
        ["building_id", "period_id"]
    )
    pd.testing.assert_frame_equal(
        actual[ENERGY_COLUMNS].reset_index(drop=True),
        expected[ENERGY_COLUMNS].reset_index(drop=True),
        check_exact=True,
    )
    assert actual[["building_id", "period_id", "representation"]].reset_index(
        drop=True
    ).equals(
        expected[["building_id", "period_id", "representation"]].reset_index(drop=True)
    )
