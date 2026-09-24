"""Integration tests: runner (FR-01..FR-04) and postprocessing (FR-13..FR-16)
on the the retained reference example district."""

from __future__ import annotations

import numpy as np
import pytest

from tests.dynamic.conftest import make_box_building, make_constant_weather, make_two_zone_box_building
from dt_prototype.dynamic.postprocessing.aggregation import portfolio_time_series, to_daily, to_monthly
from dt_prototype.dynamic.postprocessing.kpi import building_kpis, portfolio_kpis
from dt_prototype.dynamic.simulation.config import SimulationConfig
from dt_prototype.dynamic.simulation.runner import run_batch, run_building, run_portfolio


@pytest.fixture(scope="module")
def building_2(district):
    """The residential Test building 2 building input from the example district."""
    return next(b for b in district.buildings if b.name == "Test building 2")


@pytest.fixture(scope="module")
def building_2_results(district, building_2):
    """Full-year 7R2C plant run of Test building 2 (module-cached).

    ``system_templates`` must be passed explicitly: ``run_building`` (unlike
    ``run_portfolio``) does not reach into the district for them, and without
    them every system code falls back to IdealLoad — which silently zeroes
    the whole fuel/electricity side of the run.
    """
    return run_building(
        building_2, district.weather, SimulationConfig(model="7R2C", plants=True),
        system_templates=district.system_templates,
    )


def test_plant_run_actually_consumes_fuel(building_2_results):
    """A plants=True run must produce real fuel/electricity, not the all-zero
    columns an unnoticed IdealLoad fallback would leave behind (regression
    test: asserting only that the columns *exist* would not catch that)."""
    assert not building_2_results.attrs.get("warnings"), building_2_results.attrs.get("warnings")
    assert building_2_results["gas"].sum() > 0.0
    assert building_2_results["electric_plant"].sum() > 0.0


def test_run_building_columns(building_2_results, building_2):
    """The runner output carries all documented result columns (FR-01), plus
    per-zone zone_upper_*/zone_lower_* columns since Test building 2 is a two-zone
    building (Upper End Use "residential" / Lower End Use "food")."""
    for col in (
        "air_temperature",
        "operative_temperature",
        "relative_humidity",
        "sensible_load",
        "latent_load",
        "heating_load",
        "cooling_load",
        "dhw_demand",
        "ahu_sensible_load",
        "electric_appliances",
        "electric_plant",
        "gas",
        "pv_production",
    ):
        assert col in building_2_results.columns
    assert len(building_2_results) == 8760
    assert len(building_2.zones) == 2
    for label in ("upper", "lower"):
        for base in ("air_temperature", "heating_load", "cooling_load", "dhw_demand"):
            assert f"zone_{label}_{base}" in building_2_results.columns


def test_single_zone_run_has_no_zone_columns(district):
    """A genuinely single-zone building (Test building 5: empty Lower End Use) gets no
    zone_* columns — the two-zone output shape is additive, not a change to
    the single-zone case."""
    building_5 = next(b for b in district.buildings if b.name == "Test building 5")
    assert len(building_5.zones) == 1
    df = run_building(building_5, district.weather, SimulationConfig(model="5R1C", plants=False))
    assert not any(c.startswith("zone_") for c in df.columns)


def test_setpoints_respected(building_2, building_2_results):
    """Whenever a zone's heating load is active, that zone's own air
    temperature is at (or above) that zone's own heating set point — each
    of Test building 2's two zones (Upper End Use "residential", Lower End Use "food")
    is checked against its own schedule, not a cross-zone average."""
    for zone_input in building_2.zones:
        label = zone_input.geometry.zone_label
        heat_on = building_2_results[f"zone_{label}_heating_load"] > 1.0
        setpoint = zone_input.schedule.heating_setpoint[heat_on.to_numpy()]
        np.testing.assert_allclose(
            building_2_results.loc[heat_on, f"zone_{label}_air_temperature"].to_numpy(),
            setpoint,
            atol=1e-6,
        )


def test_ideal_mode_has_no_plant_columns(district, building_2):
    """plants=False produces demand-only output (ideal load workflow)."""
    df = run_building(building_2, district.weather, SimulationConfig(model="5R1C", plants=False))
    assert "gas" not in df.columns and "electric_plant" not in df.columns
    assert df["heating_load"].sum() > 0


def test_latent_switch(district, building_2):
    """latent=False zeroes the latent HVAC load (sensible-only workflow)."""
    df = run_building(
        building_2, district.weather, SimulationConfig(model="7R2C", latent=False, plants=False)
    )
    assert (df["latent_load"] == 0.0).all()


def test_pv_only_for_pv_buildings(district):
    """PV production appears only for buildings tagged with PV in the
    GeoJSON 'Solar technologies' attribute."""
    cfg = SimulationConfig(model="7R2C", plants=True)
    results = run_portfolio(district, cfg)
    assert results["Test building 2"]["pv_production"].sum() > 0  # tagged "PV,ST"
    assert results["Test building 1"]["pv_production"].sum() == 0  # tagged "ST"


def test_batch_runs_both_models(district):
    """run_batch executes several configurations over the district (FR-03)."""
    batch = run_batch(
        district,
        {
            "5R1C": SimulationConfig(model="5R1C", latent=False),
            "7R2C": SimulationConfig(model="7R2C", latent=False),
        },
    )
    assert set(batch) == {"5R1C", "7R2C"}
    for results in batch.values():
        assert len(results) == 5
    # both models produce district heating demands within 15% of each other
    h1 = sum(df["heating_load"].sum() for df in batch["5R1C"].values())
    h2 = sum(df["heating_load"].sum() for df in batch["7R2C"].values())
    assert abs(h1 - h2) / h2 < 0.15


def test_daily_and_monthly_aggregation(building_2_results):
    """Daily/monthly aggregations preserve total energy (FR-13, FR-14)."""
    daily = to_daily(building_2_results)
    monthly = to_monthly(building_2_results)
    assert len(daily) == 365 and len(monthly) == 12
    hourly_kwh = building_2_results["heating_load"].sum() / 1000.0
    assert abs(daily["heating_load_kWh"].sum() - hourly_kwh) < 1e-6
    assert abs(monthly["heating_load_kWh"].sum() - hourly_kwh) < 1e-6
    # state columns are averaged, not summed
    assert monthly["air_temperature_mean"].between(10, 35).all()


def test_portfolio_aggregation(district):
    """District time series and KPI table aggregate consistently (FR-16)."""
    results = run_portfolio(district, SimulationConfig(model="7R2C", latent=False))
    areas = {b.name: b.geometry.net_floor_area for b in district.buildings}

    series = portfolio_time_series(results)
    total_heat = sum(df["heating_load"].sum() for df in results.values())
    assert abs(series["heating_load"].sum() - total_heat) < 1e-3

    table = portfolio_kpis(results, areas)
    assert "TOTAL" in table.index
    assert abs(
        table.loc["TOTAL", "heating_demand_kwh"]
        - table.drop(index="TOTAL")["heating_demand_kwh"].sum()
    ) < 1e-6


def test_building_kpis_signs(building_2, building_2_results):
    """KPIs are non-negative and specific values scale with floor area."""
    kpis = building_kpis(building_2_results, building_2.geometry.net_floor_area)
    for key, value in kpis.items():
        if key.endswith(("_kwh", "_kw", "_kwh_m2")):
            assert value >= 0.0, key
    assert kpis["heating_demand_kwh_m2"] * building_2.geometry.net_floor_area == pytest.approx(
        kpis["heating_demand_kwh"]
    )


def test_two_zone_heating_and_cooling_can_be_simultaneous():
    """A building-level result must not net one zone's heating against
    another zone's simultaneous cooling: the upper zone here always wants
    heating (very high heating set point) and the lower zone always wants
    cooling (very low cooling set point) against a constant 10 degC
    outdoor temperature, so every time step should show both a positive
    heating_load and a negative cooling_load at once (regression test for
    per-zone bucket-then-sum, not sum-then-clip)."""
    n = 24 * 5
    building = make_two_zone_box_building(n_steps=n)
    weather = make_constant_weather(t_ext=10.0, n_steps=n)
    config = SimulationConfig(
        model="5R1C", plants=False, heating_season=(1, 365), cooling_season=(1, 365)
    )
    df = run_building(building, weather, config)
    assert (df["heating_load"] > 0.0).all()
    assert (df["cooling_load"] < 0.0).all()
    assert (df["zone_upper_heating_load"] > 0.0).all()
    assert (df["zone_lower_cooling_load"] < 0.0).all()


def test_single_zone_output_unaffected_by_two_zone_support():
    """A single-zone building's run_building output is exactly what it was
    before two-zone support existed: no zone_* columns, and heating_load/
    cooling_load equal the plain clip of sensible_load (the n=1 reduction
    of the new per-zone bucket-then-sum logic)."""
    n = 24 * 10
    building = make_box_building(n_steps=n)
    weather = make_constant_weather(t_ext=5.0, n_steps=n)
    df = run_building(building, weather, SimulationConfig(model="5R1C", plants=False))
    assert not any(c.startswith("zone_") for c in df.columns)
    np.testing.assert_array_equal(
        df["heating_load"].to_numpy(), df["sensible_load"].clip(lower=0.0).to_numpy()
    )
    np.testing.assert_array_equal(
        df["cooling_load"].to_numpy(), df["sensible_load"].clip(upper=0.0).to_numpy()
    )
