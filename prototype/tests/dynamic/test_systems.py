"""Tests for the HVAC plant models (UNI-TS boilers, Staffell HP, chillers,
DHW routing, name factories)."""

from __future__ import annotations

import pytest

from dt_prototype.dynamic.simulation.systems import (
    Boiler,
    ElectricChiller,
    ElectricHeater,
    FuelHeating,
    HeatPump,
    IdealLoad,
    cooling_system_from_name,
    heating_system_from_name,
)


def test_condensing_boiler_part_load_efficiency():
    """The UNI-TS condensing boiler exceeds LHV efficiency 1 at part load
    (condensing regime) and stays just below 1 at full load."""
    boiler = Boiler("condensing")
    boiler.set_capacity(100_000.0)
    eta_30 = 30_000.0 / boiler.solve(30_000.0, 5.0).gas
    eta_100 = 100_000.0 / boiler.solve(100_000.0, 5.0).gas
    assert eta_30 > 1.0
    assert 0.9 < eta_100 < 1.0
    assert eta_30 > eta_100


def test_traditional_boiler_efficiency_below_condensing():
    """At every load fraction the traditional boiler burns more gas than the
    condensing one for the same output."""
    cond, trad = Boiler("condensing"), Boiler("traditional")
    for b in (cond, trad):
        b.set_capacity(50_000.0)
    for frac in (0.3, 0.6, 1.0):
        load = frac * 50_000.0
        assert trad.solve(load, 5.0).gas > cond.solve(load, 5.0).gas


def test_boiler_requires_sizing():
    """Solving an unsized boiler raises instead of returning garbage."""
    with pytest.raises(RuntimeError, match="set_capacity"):
        Boiler("condensing").solve(1000.0, 5.0)


def test_boiler_serves_dhw():
    """DHW demand adds gas consumption through the EN 15316 DHW efficiency."""
    boiler = Boiler("condensing")
    boiler.set_capacity(50_000.0)
    with_dhw = boiler.solve(10_000.0, 5.0, dhw=5_000.0).gas
    without = boiler.solve(10_000.0, 5.0).gas
    assert with_dhw > without


def test_heat_pump_staffell_cop():
    """The HP COP matches the Staffell regression and improves with milder
    source temperatures."""
    hp = HeatPump(source="air", emitter="Fan coil")  # emitter water 40 °C
    dt = 40.0 - 7.0
    expected = 6.81 - 0.121 * dt + 0.000630 * dt**2
    assert abs(hp.cop(7.0, 40.0) - expected) < 1e-9
    assert hp.cop(10.0, 40.0) > hp.cop(-5.0, 40.0)


def test_chiller_part_load_eer():
    """The chiller EER follows the the retained reference part-load table (best around 50%)."""
    chiller = ElectricChiller(emitter="Split system")
    chiller.set_capacity(10_000.0)
    assert abs(chiller.eer(0.50, 25.0) - 2.94) < 1e-9
    assert abs(chiller.eer(1.00, 25.0) - 2.35) < 1e-9
    assert chiller.eer(0.50, 25.0) > chiller.eer(1.00, 25.0)
    # electricity only for cooling (negative) loads
    assert chiller.solve(+500.0, 30.0).electric == 0.0
    assert chiller.solve(-5000.0, 30.0).electric > 0.0


def test_heating_factory_reference_names():
    """the retained reference-style GeoJSON names resolve to the right system classes."""
    assert isinstance(
        heating_system_from_name("Traditional Gas Boiler, Centralized, Low Temp Radiator"),
        Boiler,
    )
    assert isinstance(
        heating_system_from_name("Condensing Gas Boiler, Single, Fan coil"), Boiler
    )
    assert isinstance(
        heating_system_from_name("A-W Heat Pump, Single, Fan coil"), HeatPump
    )
    assert heating_system_from_name("G-W HP Staffel, Centralized, Fan coil").source == "ground"
    assert isinstance(
        heating_system_from_name("District Heating, Centralized, Fan coil"), FuelHeating
    )
    assert isinstance(heating_system_from_name("Electric Heater"), ElectricHeater)
    assert isinstance(heating_system_from_name("IdealLoad"), IdealLoad)


def test_unknown_names_fall_back_to_ideal():
    """Custom template names (as in the the retained reference example GeoJSON) degrade
    gracefully to IdealLoad."""
    assert isinstance(heating_system_from_name("s19"), IdealLoad)
    assert isinstance(cooling_system_from_name("s4"), IdealLoad)


def test_cooling_factory_names():
    """Cooling names resolve to chillers with the proper emitter."""
    assert isinstance(cooling_system_from_name("A-A split"), ElectricChiller)
    chiller = cooling_system_from_name("A-W chiller, Centralized, Fan coil")
    assert isinstance(chiller, ElectricChiller)
    assert chiller.convective_fraction == 1.0  # fan coil is fully convective


def test_sigma_split_sums_to_one():
    """Radiative/convective sigma splits are consistent for both model
    arities (2 for 5R1C, 3 for 7R2C)."""
    for system in (IdealLoad(), heating_system_from_name("A-W Heat Pump, Single, Radiant surface")):
        for n in (2, 3):
            assert abs(sum(system.sigma(n)) - 1.0) < 1e-12
