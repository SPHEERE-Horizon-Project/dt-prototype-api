"""Tests for the second wave of EXTENDED features: solar thermal, natural
ventilation / free cooling, PVGIS fetching, quasi-steady-state monthly
method, stochastic DHW draw-offs, EN 16798-1 comfort KPIs."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.dynamic.conftest import make_box_building, make_constant_weather
from dt_prototype.dynamic.postprocessing.comfort import (
    comfort_kpis,
    en16798_category_series,
    running_mean_outdoor_temperature,
)
from dt_prototype.common.preprocessing.building_input import (
    assemble_building_input,
    preprocess_district,
)
from dt_prototype.common.preprocessing.dhw_stochastic import stochastic_dhw_profile
from dt_prototype.common.preprocessing.geometry import load_district_geojson
from dt_prototype.common.preprocessing.weather import process_pvgis, read_epw_text
from dt_prototype.dynamic.simulation.config import SimulationConfig
from dt_prototype.monthly.simulation.quasi_steady_state import run_quasi_steady_state
from dt_prototype.dynamic.simulation.runner import run_building, run_portfolio
from dt_prototype.dynamic.simulation.solar_thermal import SolarThermalCollector
from dt_prototype.dynamic.simulation.zone import build_zone


@pytest.fixture(scope="module")
def building_2(district):
    """Residential example building (has PV,ST tags and natural ventilation)."""
    return next(b for b in district.buildings if b.name == "Test building 2")


@pytest.fixture(scope="module")
def reference_district():
    """Five-building district with the restored the retained reference-derived databases."""
    data = Path(__file__).resolve().parents[2] / "data" / "examples"
    return preprocess_district(
        geojson_path=data / "example_district.geojson",
        epw_path=data / "ITA_Venezia-Tessera.161050_IGDG.epw",
        archetypes_path=data / "archetypes.json",
        schedules_path=data / "schedules.json",
        systems_path=data / "systems_templates.json",
    )


# --------------------------------------------------------------------- #
# Solar thermal collectors
# --------------------------------------------------------------------- #
def test_solar_thermal_sizing_and_production(district, building_2):
    """The collector field is sized within the coverage cap and produces
    heat only with sun, with plausible annual specific yield."""
    zone = build_zone(building_2, district.weather)
    collector = SolarThermalCollector(zone, district.weather, daily_dhw_kwh=50.0)
    assert 0.0 < collector.coverage_factor <= 0.05
    t_ext = district.weather.df["temp_air"].to_numpy()
    production = collector.production(t_ext)
    # no production without irradiance; night energy (twilight diffuse in
    # the EPW) is a negligible share of the annual yield
    ghi = district.weather.df["ghi"].to_numpy()
    assert production[ghi == 0.0].max() == 0.0
    night = district.weather.df["sun_elevation"].to_numpy() < 0.0
    assert production[night].sum() < 0.01 * production.sum()
    annual_kwh_m2 = production.sum() / 1000.0 / collector.collector_area
    assert 200.0 < annual_kwh_m2 < 900.0  # plausible for Venice flat plates


def test_solar_thermal_offsets_dhw_in_runner(district, building_2):
    """Test building 2 ('PV,ST') gets a solar_thermal_production column bounded by the
    DHW demand, and the plant sees a reduced DHW load."""
    df = run_building(building_2, district.weather, SimulationConfig(model="7R2C", plants=True))
    st = df["solar_thermal_production"]
    assert st.sum() > 0.0
    assert (st <= df["dhw_demand"] + 1e-9).all()


# --------------------------------------------------------------------- #
# Natural ventilation / free cooling
# --------------------------------------------------------------------- #
def test_natural_ventilation_reduces_cooling(district, building_2):
    """Window-opening free cooling engages (ACH > 0 in summer) and reduces
    the annual cooling demand vs the same building without it. Test building 2 is a
    two-zone building, so every zone's schedule needs the override."""
    cfg = SimulationConfig(model="7R2C", latent=False)
    with_nv = run_building(building_2, district.weather, cfg)
    no_nv_building = dataclasses.replace(
        building_2,
        zones=[
            dataclasses.replace(
                z, schedule=dataclasses.replace(z.schedule, natural_ventilation=None)
            )
            for z in building_2.zones
        ],
    )
    without_nv = run_building(no_nv_building, district.weather, cfg)

    assert with_nv["natural_ventilation_ach"].max() > 0.0
    assert (without_nv["natural_ventilation_ach"] == 0.0).all()
    cooling_with = -with_nv["cooling_load"].sum()
    cooling_without = -without_nv["cooling_load"].sum()
    assert cooling_with < cooling_without


def test_natural_ventilation_respects_outdoor_limit(district, building_2):
    """Windows never open when outdoor air is colder than the configured
    minimum outdoor temperature."""
    df = run_building(building_2, district.weather, SimulationConfig(model="7R2C", latent=False))
    open_steps = df["natural_ventilation_ach"] > 0.0
    t_min = building_2.schedule.natural_ventilation["min_outdoor_temperature"]
    t_out = district.weather.df["temp_air"]
    assert (t_out[open_steps.to_numpy()] > t_min).all()


# --------------------------------------------------------------------- #
# PVGIS weather fetching
# --------------------------------------------------------------------- #
def test_process_pvgis_from_cache(data_dir, tmp_path, monkeypatch):
    """process_pvgis parses EPW content identically to the file path route;
    the network layer is exercised through the cache file (no download)."""
    cache = data_dir / "ITA_Venezia-Tessera.161050_IGDG.epw"  # pre-seeded cache
    w = process_pvgis(45.5, 12.33, cache_path=cache)
    assert w.n_steps == 8760
    assert abs(w.latitude - 45.5) < 0.1


def test_fetch_pvgis_download_mocked(monkeypatch, data_dir, tmp_path):
    """The PVGIS download path decodes the response and writes the cache."""
    import io
    import urllib.request

    payload = (data_dir / "ITA_Venezia-Tessera.161050_IGDG.epw").read_bytes()

    class _FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda url, timeout=60: _FakeResponse(payload)
    )
    cache = tmp_path / "pvgis.epw"
    w = process_pvgis(45.5, 12.33, cache_path=cache)
    assert cache.exists()
    assert w.n_steps == 8760


# --------------------------------------------------------------------- #
# Quasi-steady-state monthly method
# --------------------------------------------------------------------- #
def test_qss_seasonal_pattern_and_magnitude(district, building_2):
    """QSS obeys the configured seasons and tracks dynamic 5R1C heating."""
    config = SimulationConfig(model="5R1C", latent=False)
    qss = run_quasi_steady_state(building_2, district.weather, config)
    assert len(qss) == 12
    assert qss["heating_demand_kWh"].iloc[0] > 0.0  # January heats
    assert qss["heating_demand_kWh"].iloc[6] == 0.0  # July does not
    assert qss["cooling_demand_kWh"].iloc[0] == 0.0  # no winter cooling
    assert qss["cooling_demand_kWh"].iloc[6] > 0.0

    dyn = run_building(building_2, district.weather, config)
    dyn_heat = dyn["heating_load"].sum() / 1000.0
    qss_heat = qss["heating_demand_kWh"].sum()
    assert qss_heat == pytest.approx(dyn_heat, rel=0.12)


def test_qss_utilisation_factors_bounded(district, building_2):
    """Gain/loss utilisation factors stay within (0, 1]."""
    qss = run_quasi_steady_state(building_2, district.weather)
    assert (qss["eta_gain_heating"] > 0.0).all() and (qss["eta_gain_heating"] <= 1.0).all()
    assert (qss["eta_loss_cooling"] > 0.0).all() and (qss["eta_loss_cooling"] <= 1.0).all()


def test_qss_two_zone_equals_independent_zone_runs(district, building_2):
    """Two-zone QSS is exactly the sum of two adiabatic/uncoupled zone runs,
    with each independent result exposed under its zone label."""
    combined = run_quasi_steady_state(building_2, district.weather)
    independent = {
        zone.geometry.zone_label: run_quasi_steady_state(
            dataclasses.replace(building_2, zones=[zone]), district.weather
        )
        for zone in building_2.zones
    }
    energy_columns = (
        "heating_demand_kWh",
        "cooling_demand_kWh",
        "ahu_heating_demand_kWh",
        "ahu_cooling_demand_kWh",
        "total_sensible_heating_demand_kWh",
        "total_sensible_cooling_demand_kWh",
        "heat_losses_kWh",
        "gains_kWh",
    )
    factor_columns = ("eta_gain_heating", "eta_loss_cooling")

    for column in energy_columns:
        expected = sum(zone_result[column] for zone_result in independent.values())
        np.testing.assert_allclose(combined[column], expected, rtol=1e-13, atol=1e-9)
    for label, zone_result in independent.items():
        for column in (*energy_columns, *factor_columns):
            np.testing.assert_array_equal(
                combined[f"zone_{label}_{column}"].to_numpy(),
                zone_result[column].to_numpy(),
            )


def test_qss_single_zone_schema_exposes_zone_ahu_and_totals(district):
    """A single zone exposes unprefixed zone, AHU and total sensible loads."""
    building_5 = next(building for building in district.buildings if building.name == "Test building 5")
    qss = run_quasi_steady_state(building_5, district.weather)
    assert list(qss.columns) == [
        "heating_demand_kWh",
        "cooling_demand_kWh",
        "ahu_heating_demand_kWh",
        "ahu_cooling_demand_kWh",
        "total_sensible_heating_demand_kWh",
        "total_sensible_cooling_demand_kWh",
        "heat_losses_kWh",
        "gains_kWh",
        "eta_gain_heating",
        "eta_loss_cooling",
    ]
    np.testing.assert_allclose(
        qss["total_sensible_heating_demand_kWh"],
        qss["heating_demand_kWh"] + qss["ahu_heating_demand_kWh"],
    )
    np.testing.assert_allclose(
        qss["total_sensible_cooling_demand_kWh"],
        qss["cooling_demand_kWh"] + qss["ahu_cooling_demand_kWh"],
    )


def test_qss_ahu_sensible_recovery_reduces_coil_load():
    """Configured sensible recovery is applied to the monthly AHU balance."""
    building = make_box_building(
        heating_setpoint=20.0,
        cooling_setpoint=35.0,
        ach=0.5,
    )
    weather = make_constant_weather(t_ext=0.0)
    zone_input = building.zones[0]

    def with_recovery(effectiveness: float):
        schedule = dataclasses.replace(
            zone_input.schedule,
            ahu={
                "sensible_recovery_eff": effectiveness,
                "supply_temperature_heating": 20.0,
                "supply_temperature_cooling": 20.0,
                "outdoor_air_ratio": 1.0,
            },
        )
        return dataclasses.replace(
            building,
            zones=[dataclasses.replace(zone_input, schedule=schedule)],
        )

    config = SimulationConfig(
        model="5R1C",
        latent=False,
        heating_season=(1, 365),
        cooling_season=(1, 365),
    )
    no_recovery = run_quasi_steady_state(with_recovery(0.0), weather, config)
    recovery = run_quasi_steady_state(with_recovery(0.6), weather, config)
    assert recovery["ahu_heating_demand_kWh"].sum() == pytest.approx(
        0.4 * no_recovery["ahu_heating_demand_kWh"].sum(), rel=1e-12
    )
    assert recovery["heating_demand_kWh"].sum() == pytest.approx(
        no_recovery["heating_demand_kWh"].sum(), rel=1e-12
    )


def test_qss_five_building_alignment(reference_district):
    """All reference buildings track dynamic zone/AHU sensible demand.

    Heating is the strongest QSS use case and is kept within 12%. Cooling
    permits 30% because a monthly method has no evolving return-air state or
    cooling-season pull-down transient.
    """
    config = SimulationConfig(model="5R1C", plants=False, latent=False)
    dynamic = run_portfolio(reference_district, config)
    for building in reference_district.buildings:
        hourly = dynamic[building.name]
        monthly = run_quasi_steady_state(building, reference_district.weather, config)
        comparisons = {
            "zone heating": (
                hourly["heating_load"].sum() / 1000.0,
                monthly["heating_demand_kWh"].sum(),
                0.12,
            ),
            "AHU heating": (
                hourly["ahu_sensible_load"].clip(lower=0.0).sum() / 1000.0,
                monthly["ahu_heating_demand_kWh"].sum(),
                0.12,
            ),
            "total heating": (
                (
                    hourly["heating_load"]
                    + hourly["ahu_sensible_load"].clip(lower=0.0)
                ).sum()
                / 1000.0,
                monthly["total_sensible_heating_demand_kWh"].sum(),
                0.12,
            ),
            "zone cooling": (
                -hourly["cooling_load"].sum() / 1000.0,
                monthly["cooling_demand_kWh"].sum(),
                0.30,
            ),
            "AHU cooling": (
                -hourly["ahu_sensible_load"].clip(upper=0.0).sum() / 1000.0,
                monthly["ahu_cooling_demand_kWh"].sum(),
                0.30,
            ),
            "total cooling": (
                -(
                    hourly["cooling_load"]
                    + hourly["ahu_sensible_load"].clip(upper=0.0)
                ).sum()
                / 1000.0,
                monthly["total_sensible_cooling_demand_kWh"].sum(),
                0.30,
            ),
        }
        for quantity, (expected, actual, tolerance) in comparisons.items():
            assert actual == pytest.approx(expected, rel=tolerance), (
                f"{building.name} {quantity}: dynamic={expected:.3f} kWh, "
                f"QSS={actual:.3f} kWh"
            )


# --------------------------------------------------------------------- #
# Stochastic DHW draw-offs
# --------------------------------------------------------------------- #
def test_stochastic_dhw_conserves_volume_and_reproducible():
    """The stochastic profile conserves the daily volume, is reproducible
    with a seed, and is peakier than the deterministic UNI-TS profile."""
    p1 = stochastic_dhw_profile(0.15, n_units=3, seed=42)
    p2 = stochastic_dhw_profile(0.15, n_units=3, seed=42)
    np.testing.assert_allclose(p1, p2)
    daily_m3 = p1.mean() * 86400.0
    assert daily_m3 == pytest.approx(0.15 * 3, rel=1e-6)
    assert (p1 >= 0.0).all()
    # peak-to-mean ratio far above the smooth deterministic profile's ~1.1
    assert p1.max() / p1.mean() > 3.0


def test_stochastic_method_resolved_per_building(data_dir, archetypes, schedules):
    """dhw method 'stochastic' replaces the shared profile with a
    building-specific one; different buildings get different draws."""
    geometries = load_district_geojson(data_dir / "example_district.geojson")
    residential = dataclasses.replace(
        schedules["residential"], dhw_method="stochastic", dhw_volume_per_m2_day=1.4
    )
    patched = {**schedules, "residential": residential}
    building_2_g = next(g for g in geometries if g.name == "Test building 2")
    building_3_g = next(g for g in geometries if g.name == "Test building 3")
    b3 = assemble_building_input(building_2_g, archetypes, patched)
    b4 = assemble_building_input(building_3_g, archetypes, patched)
    # per-m2 daily volume conserved for each building
    for b in (b3, b4):
        daily = b.schedule.dhw_volume_flow.mean() * 86400.0 * 1000.0  # l/(m2 day)
        assert daily == pytest.approx(1.4, rel=0.01)
    # different buildings, different stochastic draws
    assert not np.allclose(
        b3.schedule.dhw_volume_flow * b3.geometry.net_floor_area,
        b4.schedule.dhw_volume_flow * b4.geometry.net_floor_area,
    )


# --------------------------------------------------------------------- #
# EN 16798-1 comfort categories
# --------------------------------------------------------------------- #
def test_running_mean_smooths_daily_series():
    """The running mean lags and damps a step change in outdoor temperature."""
    daily = np.array([10.0] * 10 + [20.0] * 10)
    t_rm = running_mean_outdoor_temperature(daily)
    assert t_rm[10] < 15.0  # lags behind the step
    assert t_rm[-1] < 20.0 and t_rm[-1] > 17.0  # approaches asymptotically


def test_en16798_categories_synthetic():
    """Operative temperatures on the comfort line are category I; extreme
    deviations are category IV."""
    index = pd.date_range("2023-06-01", periods=24 * 30, freq="h")
    outdoor = pd.Series(22.0, index=index)  # T_rm=22 → T_comf=26.06
    on_comfort = pd.Series(26.0, index=index)
    too_hot = pd.Series(35.0, index=index)
    assert (en16798_category_series(on_comfort, outdoor) == 1).all()
    assert (en16798_category_series(too_hot, outdoor) == 4).all()


def test_comfort_kpis_on_simulated_building(district, building_2):
    """Comfort KPIs of a conditioned building: fractions sum to one and
    most hours fall inside category III."""
    df = run_building(building_2, district.weather, SimulationConfig(model="7R2C"))
    kpis = comfort_kpis(df, district.weather.df["temp_air"])
    total = sum(kpis[f"cat_{c}_fraction"] for c in ("i", "ii", "iii", "iv"))
    assert total == pytest.approx(1.0)
    assert kpis["cat_iv_fraction"] < 0.35
    assert 1.0 <= kpis["mean_category"] <= 4.0
    # occupancy mask restricts the evaluation
    occupied = building_2.schedule.internal_gain_convective > 0.0
    kpis_occ = comfort_kpis(df, district.weather.df["temp_air"], occupied=occupied)
    assert kpis_occ["hours_outside_cat_ii"] <= kpis["hours_outside_cat_ii"]
