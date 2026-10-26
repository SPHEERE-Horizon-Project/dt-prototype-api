"""Tests for the archetype and schedule databases (FR-05, FR-07)."""

from __future__ import annotations

import numpy as np
import pytest

from dt_prototype.common.preprocessing.archetypes import ConstructionSpec, EnvelopeArchetype


def test_archetype_database_loads(archetypes):
    """The TABULA-style fixture provides all construction periods with
    complete envelopes."""
    assert "1981-1990" in archetypes  # referenced by the example GeoJSON
    env = archetypes["1981-1990"]
    for ctype in ("ExtWall", "Roof", "GroundFloor", "IntWall", "IntCeiling", "IntFloor"):
        assert ctype in env.constructions


def test_equivalent_layer_reproduces_u_value(archetypes):
    """The equivalent single-layer construction reproduces the archetype
    U-value (the ISO 13786 mass-class derivation, as the retained reference from_U_value)."""
    wall = archetypes["1981-1990"].constructions["ExtWall"]
    assert abs(wall.u_value - 0.8) < 1e-9
    roof = archetypes["1981-1990"].constructions["Roof"]
    assert abs(roof.u_value - 0.9) < 1e-9
    # GroundFloor carries the the retained reference 0.7 ground-contact reduction
    gf = archetypes["1981-1990"].constructions["GroundFloor"]
    assert abs(gf.u_value - 0.9 * 0.7) < 1e-9


def test_unphysical_u_value_rejected():
    """A U-value higher than the film coefficients allow is rejected."""
    with pytest.raises(ValueError):
        ConstructionSpec.from_u_value("bad", 10.0, "Medium", "ExtWall")


def test_construction_dict_round_trip(archetypes):
    """Envelope archetypes serialise to plain dicts and reload equal (FR-08)."""
    env = archetypes["1981-1990"]
    env2 = EnvelopeArchetype.from_dict(env.to_dict())
    assert env2.to_dict() == env.to_dict()


def test_schedule_annual_arrays(schedules):
    """Every end use expands to 8760-value arrays with plausible ranges."""
    for schedule in schedules.values():
        assert len(schedule.heating_setpoint) == 8760
        assert len(schedule.internal_gain_convective) == 8760
        assert schedule.heating_setpoint.min() >= 10.0
        assert schedule.cooling_setpoint.max() <= 35.0
        assert (schedule.ventilation_ach >= 0).all()


def test_weekday_weekend_pattern(schedules):
    """The services occupancy differs between a weekday and a weekend day
    (2023-01-02 is a Monday, 2023-01-07 a Saturday)."""
    services = schedules["services"]
    monday = services.internal_gain_convective[24:48]
    saturday = services.internal_gain_convective[24 * 6 : 24 * 7]
    assert monday.max() > saturday.max()


def test_dhw_daily_volume_integrates(schedules):
    """The DHW draw-off profile integrates to the configured daily volume
    (residential fixture: 1.4 l/(m2 day))."""
    res = schedules["residential"]
    day_m3_per_m2 = res.dhw_volume_flow[:24].sum() * 3600.0
    assert abs(day_m3_per_m2 - 1.4 / 1000.0) < 1e-12


def test_ahu_block_passthrough(schedules):
    """The services end use carries its AHU parameters; residential has none."""
    assert schedules["services"].ahu is not None
    assert schedules["services"].ahu["humidity_control"] is True
    assert schedules["residential"].ahu is None


def test_latent_and_humidity_fields(schedules):
    """Latent gains and humidity set point bands are populated."""
    res = schedules["residential"]
    assert res.internal_gain_latent.max() > 0
    assert (res.humidity_setpoint_low < res.humidity_setpoint_high).all()
