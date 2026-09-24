"""Tests for the thermal models (FR-09, FR-10, FR-11).

Analytic checks use the synthetic box building from ``conftest`` under
constant weather, where the steady-state heating demand must approach the
static value (UA + H_ve) * (T_set - T_ext).
"""

from __future__ import annotations

import numpy as np
import pytest

from tests.dynamic.conftest import make_box_building, make_constant_weather
from dt_prototype.common.constants import AIR_DENSITY, AIR_SPECIFIC_HEAT
from dt_prototype.dynamic.simulation.config import SimulationConfig
from dt_prototype.dynamic.simulation.model_base import MODEL_REGISTRY, ThermalModel, get_model_class


def test_registry_contains_both_models():
    """The registry resolves both models and their the retained reference aliases (FR-11)."""
    assert get_model_class("5R1C").name == "5R1C"
    assert get_model_class("7R2C").name == "7R2C"
    assert get_model_class("1C") is get_model_class("5R1C")
    assert get_model_class("2C") is get_model_class("7R2C")


def test_7r2c_rejects_zone_without_internal_mass():
    """The VDI 6007 network inverts the internal-mass conductance, so a zone
    with no IntWall/IntCeiling/IntFloor has no valid parametrisation. It must
    say so clearly instead of raising a bare ZeroDivisionError."""
    building = make_box_building(n_steps=48)
    weather = make_constant_weather(n_steps=48)
    internal = ("IntWall", "IntCeiling", "IntFloor")
    for zone in building.geometry.zones:
        zone.surfaces = [s for s in zone.surfaces if s.surface_type not in internal]
    with pytest.raises(ValueError, match="no internal-mass surfaces"):
        get_model_class("7R2C")(building, weather, SimulationConfig(model="7R2C"))
    # the 5R1C network lumps all mass into one node and stays solvable
    get_model_class("5R1C")(building, weather, SimulationConfig(model="5R1C"))


def test_unknown_model_raises():
    """Requesting an unregistered model gives a helpful error."""
    with pytest.raises(KeyError, match="Unknown thermal model"):
        get_model_class("9R9C")


def test_new_model_registration_is_additive():
    """A new model registers via the decorator without touching existing
    modules (open/closed, FR-11)."""
    from dt_prototype.dynamic.simulation.model_base import register_model

    @register_model
    class _Dummy(ThermalModel):
        name = "_dummy_test_model"

        def _compute_parameters(self):  # pragma: no cover - stub
            pass

        def _compute_loads(self):  # pragma: no cover - stub
            pass

        def sensible_balance(self, *a, **k):  # pragma: no cover - stub
            raise NotImplementedError

    try:
        assert get_model_class("_dummy_test_model") is _Dummy
    finally:
        MODEL_REGISTRY.pop("_dummy_test_model", None)


@pytest.mark.parametrize("model_name", ["5R1C", "7R2C"])
def test_steady_state_heating_demand(model_name):
    """Under constant 0 °C weather with no sun/gains the model's converged
    heating demand approaches the static (UA + H_ve) * dT estimate."""
    t_ext, t_set = 0.0, 20.0
    n = 24 * 30  # one month is far beyond the envelope time constants
    building = make_box_building(ach=0.5, n_steps=n)
    weather = make_constant_weather(t_ext=t_ext, n_steps=n)
    config = SimulationConfig(model=model_name, latent=False, plants=False)
    model = get_model_class(model_name)(building, weather, config)

    sigma = (0.0,) * (model.n_sigma - 1) + (1.0,)
    phi = 0.0
    for t in range(n):
        result = model.solve_timestep(t, True, False, sigma, sigma)
        phi = result.sensible_load
        assert abs(result.air_temperature - t_set) < 1e-6  # set point held

    hve = building.geometry.volume * 0.5 / 3600.0 * AIR_DENSITY * AIR_SPECIFIC_HEAT
    static = (model.UA_tot + hve) * (t_set - t_ext)
    # the RC network's internal film resistances make the dynamic value
    # slightly lower than the naive UA product
    assert 0.75 * static < phi < 1.05 * static


def test_models_agree_on_steady_state():
    """5R1C and 7R2C converge to steady-state demands within 10% of each
    other on the same synthetic building."""
    building = make_box_building(n_steps=24 * 30)
    weather = make_constant_weather(t_ext=0.0, n_steps=24 * 30)
    demands = {}
    for name in ("5R1C", "7R2C"):
        config = SimulationConfig(model=name, latent=False)
        model = get_model_class(name)(building, weather, config)
        sigma = (0.0,) * (model.n_sigma - 1) + (1.0,)
        for t in range(weather.n_steps):
            res = model.solve_timestep(t, True, False, sigma, sigma)
        demands[name] = res.sensible_load
    assert abs(demands["5R1C"] - demands["7R2C"]) / demands["7R2C"] < 0.10


def test_free_floating_approaches_outdoor_temperature():
    """With conditioning off, no sun and no gains, the zone relaxes to just
    below the outdoor temperature — slightly below because the VDI 6007
    equivalent temperature includes long-wave radiative losses to the sky."""
    building = make_box_building(n_steps=24 * 60)
    weather = make_constant_weather(t_ext=10.0, n_steps=24 * 60)
    config = SimulationConfig(model="7R2C", latent=False)
    model = get_model_class("7R2C")(building, weather, config)
    sigma = (0.0, 0.0, 1.0)
    for t in range(weather.n_steps):
        res = model.solve_timestep(t, False, False, sigma, sigma)
        assert res.sensible_load == 0.0
    assert 8.5 < res.air_temperature <= 10.0


def test_capacity_limit_respected():
    """A finite heating_max_power caps the delivered load and the air
    temperature drops below the set point."""
    building = make_box_building(n_steps=48)
    weather = make_constant_weather(t_ext=-5.0, n_steps=48)
    p_max = 2000.0
    config = SimulationConfig(model="7R2C", latent=False, heating_max_power=p_max)
    model = get_model_class("7R2C")(building, weather, config)
    sigma = (0.0, 0.0, 1.0)
    for t in range(weather.n_steps):
        res = model.solve_timestep(t, True, False, sigma, sigma)
        assert res.sensible_load <= p_max + 1e-6
    assert res.air_temperature < 20.0


def test_latent_balance_holds_humidity_band():
    """With latent control enabled the zone relative humidity stays inside
    the configured band once regulated."""
    building = make_box_building(n_steps=24 * 10)
    # widen check: dry outdoor air, humidification keeps RH at the low band
    weather = make_constant_weather(t_ext=0.0, n_steps=24 * 10)
    building.schedule.humidity_setpoint_low[:] = 0.35
    building.schedule.humidity_setpoint_high[:] = 0.55
    config = SimulationConfig(model="7R2C", latent=True)
    model = get_model_class("7R2C")(building, weather, config)
    sigma = (0.0, 0.0, 1.0)
    for t in range(weather.n_steps):
        res = model.solve_timestep(t, True, False, sigma, sigma)
    assert 0.35 - 1e-6 <= res.relative_humidity <= 0.55 + 1e-6
    assert res.latent_load > 0.0  # dry winter air requires humidification
