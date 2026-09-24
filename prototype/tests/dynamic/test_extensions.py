"""Tests for the EXTENDED features: AHU recirculation + saturation checks,
DHW storage tank, PV battery, design-day plant sizing."""

from __future__ import annotations

import numpy as np
import pytest

from tests.dynamic.conftest import make_box_building
from dt_prototype.common.constants import AIR_SPECIFIC_HEAT, VAPOUR_LATENT_HEAT
from dt_prototype.dynamic.simulation.air_handling_unit import (
    AirHandlingUnit,
    dew_point_of,
    saturation_humidity_ratio,
)
from dt_prototype.dynamic.simulation.config import SimulationConfig
from dt_prototype.dynamic.simulation.design import design_cooling_power, design_heating_power
from dt_prototype.dynamic.simulation.dhw_tank import DhwTank
from dt_prototype.dynamic.simulation.pv_system import Battery
from dt_prototype.dynamic.simulation.runner import run_building
from dt_prototype.dynamic.simulation.systems import Boiler


# --------------------------------------------------------------------- #
# AHU recirculation and saturation checks
# --------------------------------------------------------------------- #
def test_psychrometric_helpers_are_inverse():
    """Dew point and saturation humidity ratio are mutually consistent."""
    for t in (5.0, 16.0, 25.0):
        x_sat = saturation_humidity_ratio(t)
        assert abs(dew_point_of(x_sat) - t) < 0.05


def test_recirculation_reduces_heating_coil_load():
    """With recirculation (warm zone air mixed in), the winter heating coil
    load is lower than with 100% outdoor air."""
    full_oa = AirHandlingUnit(sensible_recovery_eff=0.5, outdoor_air_ratio=1.0)
    recirc = AirHandlingUnit(sensible_recovery_eff=0.5, outdoor_air_ratio=0.5)
    args = dict(t_ext=0.0, x_ext=0.003, t_zone=20.0, x_zone=0.007, mass_flow=1.0, heating_mode=True)
    assert recirc.process(**args).heating_coil_load < full_oa.process(**args).heating_coil_load


def test_invalid_outdoor_air_ratio_rejected():
    """The outdoor-air ratio must be within (0, 1]."""
    with pytest.raises(ValueError):
        AirHandlingUnit(outdoor_air_ratio=0.0)


def test_dehumidification_cools_to_dew_point_and_reheats():
    """Humid summer air is cooled below the supply temperature (apparatus
    dew point) and reheated: simultaneous cooling and heating coil loads."""
    ahu = AirHandlingUnit(
        humidity_control=True, supply_temperature_cooling=16.0, supply_specific_humidity=0.008
    )
    state = ahu.process(
        t_ext=32.0, x_ext=0.015, t_zone=26.0, x_zone=0.011, mass_flow=1.0, heating_mode=False
    )
    assert state.cooling_coil_load < 0.0
    assert state.latent_load < 0.0  # moisture removed
    assert state.heating_coil_load > 0.0  # reheat from ADP to 16 °C
    assert state.supply_specific_humidity == pytest.approx(0.008)
    # the supply state respects the saturation curve
    assert state.supply_specific_humidity <= saturation_humidity_ratio(state.supply_temperature)


def test_saturation_check_without_humidity_control():
    """Cooling humid air below its dew point condenses moisture even when
    humidity control is off (saturation check)."""
    ahu = AirHandlingUnit(humidity_control=False, supply_temperature_cooling=12.0)
    state = ahu.process(
        t_ext=30.0, x_ext=0.020, t_zone=26.0, x_zone=0.018, mass_flow=1.0, heating_mode=False
    )
    x_sat_supply = saturation_humidity_ratio(12.0)
    assert state.supply_specific_humidity == pytest.approx(x_sat_supply)
    assert state.latent_load < 0.0  # implicit condensation on the coil


def test_humidity_target_clipped_to_saturation():
    """An unphysical supply humidity set point is clipped to the saturation
    curve at the supply temperature."""
    ahu = AirHandlingUnit(
        humidity_control=True, supply_temperature_heating=20.0, supply_specific_humidity=0.030
    )
    state = ahu.process(
        t_ext=0.0, x_ext=0.003, t_zone=20.0, x_zone=0.007, mass_flow=1.0, heating_mode=True
    )
    assert state.supply_specific_humidity < 0.030
    assert state.supply_specific_humidity <= 0.95 * saturation_humidity_ratio(20.0) + 1e-12


def test_invalid_ahu_mode_rejected():
    """SimulationConfig rejects unknown AHU algorithms."""
    with pytest.raises(ValueError, match="ahu_mode"):
        SimulationConfig(ahu_mode="unknown")


def test_basic_ahu_mode_matches_base_equations_and_ignores_recirculation():
    """BASIC mode uses 100% outdoor air, direct humidity control and the
    original net sensible-coil equations regardless of outdoor_air_ratio."""
    kwargs = dict(
        sensible_recovery_eff=0.5,
        latent_recovery_eff=0.2,
        supply_temperature_heating=20.0,
        supply_specific_humidity=0.030,
        humidity_control=True,
        mode="basic",
    )
    nominal = AirHandlingUnit(outdoor_air_ratio=1.0, **kwargs)
    ignored_recirc = AirHandlingUnit(outdoor_air_ratio=0.25, **kwargs)
    process_args = dict(
        t_ext=0.0,
        x_ext=0.003,
        t_zone=22.0,
        x_zone=0.009,
        mass_flow=1.0,
        heating_mode=True,
    )
    state = ignored_recirc.process(**process_args)
    nominal_state = nominal.process(**process_args)

    t_recovered = 0.0 + 0.5 * (22.0 - 0.0)
    x_recovered = 0.003 + 0.2 * (0.009 - 0.003)
    expected_sensible = AIR_SPECIFIC_HEAT * (20.0 - t_recovered)
    expected_latent = VAPOUR_LATENT_HEAT * (0.030 - x_recovered)

    assert state.supply_temperature == pytest.approx(20.0)
    assert state.supply_specific_humidity == pytest.approx(0.030)
    assert state.heating_coil_load == pytest.approx(expected_sensible)
    assert state.cooling_coil_load == 0.0
    assert state.latent_load == pytest.approx(expected_latent)
    assert state == nominal_state


def test_basic_ahu_mode_has_no_dehumidification_reheat():
    """BASIC mode represents summer conditioning as one net cooling coil,
    without the EXTENDED apparatus-dew-point and reheat sequence."""
    common = dict(
        humidity_control=True,
        supply_temperature_cooling=16.0,
        supply_specific_humidity=0.008,
    )
    basic = AirHandlingUnit(mode="basic", **common)
    extended = AirHandlingUnit(mode="extended", **common)
    args = dict(
        t_ext=32.0,
        x_ext=0.015,
        t_zone=26.0,
        x_zone=0.011,
        mass_flow=1.0,
        heating_mode=False,
    )
    basic_state = basic.process(**args)
    extended_state = extended.process(**args)

    assert basic_state.cooling_coil_load < 0.0
    assert basic_state.heating_coil_load == 0.0
    assert basic_state.supply_specific_humidity == pytest.approx(0.008)
    assert extended_state.heating_coil_load > 0.0


def test_simulation_config_selects_basic_ahu(district):
    """The run configuration is propagated into an AHU-equipped model."""
    from dt_prototype.dynamic.simulation.model_base import get_model_class

    building = next(b for b in district.buildings if b.schedule.ahu is not None)
    model = get_model_class("7R2C")(
        building,
        district.weather,
        SimulationConfig(model="7R2C", ahu_mode="basic"),
    )
    assert model.ahu is not None
    assert model.ahu.mode == "basic"


# --------------------------------------------------------------------- #
# DHW storage tank
# --------------------------------------------------------------------- #
def test_tank_energy_conservation():
    """Over a repeating daily cycle, generator charge covers draw plus
    standing losses (energy balance closes within 2%)."""
    tank = DhwTank(volume=0.3, charge_power=3000.0, timestep=3600.0)
    draw_day = np.array([0.0] * 6 + [2000.0] * 3 + [500.0] * 9 + [2500.0] * 4 + [0.0] * 2)
    draws = np.tile(draw_day, 30)
    charge_total = loss_total = 0.0
    t0 = tank.temperature
    for draw in draws:
        loss_total += tank.ua * (tank.temperature - tank.ambient_temperature) * 3600.0
        charge_total += tank.step(float(draw)) * 3600.0
    storage_change = tank.capacity * (tank.temperature - t0)
    assert charge_total == pytest.approx(draws.sum() * 3600.0 + loss_total + storage_change, rel=0.02)


def test_tank_smooths_generator_peak():
    """The generator charge power stays at the tank's rating even when the
    instantaneous draw peak is much higher (peak shaving)."""
    tank = DhwTank(volume=0.5, charge_power=2000.0, timestep=3600.0)
    peak_draw = 10_000.0
    charges = [tank.step(peak_draw if 6 <= h % 24 < 8 else 0.0) for h in range(72)]
    assert max(charges) <= 2000.0
    assert max(charges) > 0.0


def test_tank_autosize_from_demand():
    """Autosizing returns a plausible tank for a residential DHW profile
    and None when there is no demand."""
    demand = np.tile(np.array([0.0] * 6 + [1500.0] * 12 + [0.0] * 6), 365)
    tank = DhwTank.autosize(demand, 3600.0)
    assert tank is not None
    assert 0.05 <= tank.volume < 2.0
    assert tank.charge_power >= 500.0
    assert DhwTank.autosize(np.zeros(8760), 3600.0) is None


def test_boiler_with_tank_sees_smoothed_load():
    """A boiler with an attached tank consumes gas at the tank charge rate,
    not at the instantaneous DHW peak."""
    boiler = Boiler("condensing")
    boiler.set_capacity(20_000.0)
    boiler.dhw_tank = DhwTank(volume=0.3, charge_power=2500.0, timestep=3600.0)
    out = boiler.solve(0.0, 5.0, dhw=15_000.0)  # huge instantaneous draw
    # generator load bounded by charge power (plus losses margin)
    assert out.gas < 5000.0


# --------------------------------------------------------------------- #
# PV battery
# --------------------------------------------------------------------- #
def _pv_and_load(days: int = 20) -> tuple[np.ndarray, np.ndarray]:
    """Synthetic sunny-day PV bell and flat load with an evening bump."""
    hours = np.arange(24)
    pv_day = np.clip(np.sin((hours - 6) / 12 * np.pi), 0.0, None) * 3000.0
    load_day = np.full(24, 800.0)
    load_day[18:23] = 1500.0
    return np.tile(pv_day, days), np.tile(load_day, days)


def test_battery_sizing_positive_for_surplus_pv():
    """A daily PV surplus yields a positive sized capacity."""
    pv, load = _pv_and_load()
    battery = Battery()
    assert battery.size(pv, load, 1.0) > 0.0


def test_battery_dispatch_energy_conservation():
    """Grid import + PV self-consumption covers the load; charge/discharge
    stays inside the usable SOC window."""
    pv, load = _pv_and_load()
    battery = Battery()
    flows = battery.dispatch(pv, load, 1.0)
    supplied = flows["direct_solar"] + flows["from_battery"] + flows["from_grid"]
    np.testing.assert_allclose(supplied.sum(), load.sum(), rtol=0.05)
    assert flows["soc"].max() <= battery.max_charge + 1e-9
    assert flows["from_battery"].sum() > 0.0  # evening bump served by storage
    assert flows["to_grid"].sum() >= 0.0


def test_battery_raises_self_consumption():
    """With a battery, grid import is lower than without (self-consumption
    increases)."""
    pv, load = _pv_and_load()
    flows = Battery().dispatch(pv, load, 1.0)
    import_no_battery = np.clip(load - pv, 0.0, None).sum()
    assert flows["from_grid"].sum() < import_no_battery


# --------------------------------------------------------------------- #
# Design-day sizing
# --------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def building_2(district):
    """Residential example building for sizing tests."""
    return next(b for b in district.buildings if b.name == "Test building 2")


def test_design_powers_plausible(district, building_2):
    """Design-day powers are positive and within a plausible specific range
    for the Venice climate (heating 20-200 W/m2, cooling 10-150 W/m2)."""
    config = SimulationConfig(model="7R2C", plants=True)
    nfa = building_2.geometry.net_floor_area
    p_heat = design_heating_power(building_2, district.weather, config)
    p_cool = design_cooling_power(building_2, district.weather, config)
    assert 20.0 < p_heat / nfa < 200.0
    assert 10.0 < p_cool / nfa < 150.0


def test_design_day_vs_static_sizing(district, building_2):
    """Design-day heating sizing is tighter than (or comparable to) the
    static steady-state estimate — the mass and gains it resolves can only
    reduce the required capacity. Test building 2 is a two-zone building, so the static
    estimate is summed across both zones' models too (same convention
    ``run_building`` uses), for an apples-to-apples comparison."""
    from dt_prototype.dynamic.simulation.model_base import get_model_class
    from dt_prototype.dynamic.simulation.runner import _design_powers

    config = SimulationConfig(model="7R2C", plants=True)
    static_h = 0.0
    for i in range(len(building_2.zones)):
        model = get_model_class("7R2C")(building_2, district.weather, config, zone_index=i)
        h, _ = _design_powers(model, district.weather)
        static_h += h
    dd_h = design_heating_power(building_2, district.weather, config)
    assert dd_h < 1.2 * static_h


def test_full_run_with_all_extensions(district, building_2):
    """End-to-end run with design-day sizing, DHW tank and PV battery:
    all extended columns present and physically consistent."""
    config = SimulationConfig(
        model="7R2C", plants=True, sizing="design_day", dhw_tank=True, pv_battery=True
    )
    df = run_building(building_2, district.weather, config)
    for col in ("dhw_tank_temperature", "battery_soc", "grid_import", "grid_export",
                "pv_self_consumed", "pv_production"):
        assert col in df.columns, col
    # tank stays within a sane band around its set point
    assert 30.0 < df["dhw_tank_temperature"].min()
    assert df["dhw_tank_temperature"].max() < 70.0
    # battery SOC bounded; self-consumption cannot exceed production
    assert df["battery_soc"].between(0.0, 1.0).all()
    assert df["pv_self_consumed"].sum() <= df["pv_production"].sum() * 1.001
