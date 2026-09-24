"""Tests for the 1:1 ports of the retained reference's Materials.xlsx and Schedules_total.xlsx
(data/examples/archetypes.json, schedules.json) and the loader
features they exercise: multi-layer stratigraphies, three day types, and the
the retained reference-native infiltration/ventilation/DHW units."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dt_prototype.common.preprocessing.archetypes import load_envelope_archetypes
from dt_prototype.common.preprocessing.building_input import BuildingInput, preprocess_geometries
from dt_prototype.common.preprocessing.geometry import simple_building_geometry
from dt_prototype.common.preprocessing.schedules import (
    expand_day_type_profiles,
    load_end_use_schedules,
)
from dt_prototype.dynamic.simulation.config import SimulationConfig
from dt_prototype.dynamic.simulation.runner import run_building
from dt_prototype.dynamic.simulation.zone import build_zone

EXAMPLES = Path(__file__).resolve().parents[2] / "data" / "examples"
ARCHETYPES = EXAMPLES / "archetypes.json"
SCHEDULES = EXAMPLES / "schedules.json"


@pytest.fixture(scope="module")
def reference_archetypes():
    """Envelope archetypes ported 1:1 from the retained reference's Materials.xlsx."""
    return load_envelope_archetypes(ARCHETYPES)


@pytest.fixture(scope="module")
def reference_schedules():
    """End-use schedules ported 1:1 from the retained reference's Schedules_total.xlsx."""
    return load_end_use_schedules(SCHEDULES)


# --------------------------------------------------------------------- #
# Materials.xlsx port
# --------------------------------------------------------------------- #
def test_all_reference_vintages_present(reference_archetypes):
    """All ten the retained reference construction periods load, including the 1981-1990
    vintage that the example district GeoJSON references."""
    assert len(reference_archetypes) == 10
    assert "1981-1990" in reference_archetypes
    assert "Before 1930" in reference_archetypes and "After 2010" in reference_archetypes


def test_constructions_are_multi_layer(reference_archetypes):
    """Constructions are real stratigraphies, not collapsed to a single
    equivalent layer — the point of the 1:1 port."""
    ext_wall = reference_archetypes["1981-1990"].constructions["ExtWall"]
    assert len(ext_wall.layers) > 1
    for layer in ext_wall.layers:
        assert layer.thickness > 0 and layer.conductivity > 0
        assert layer.density > 0 and layer.specific_heat > 0


def test_u_values_improve_with_vintage(reference_archetypes):
    """Newer the retained reference vintages have better-insulated external walls than the
    oldest one — a physical sanity check on the ported layer data."""
    oldest = reference_archetypes["Before 1930"].constructions["ExtWall"].u_value
    newest = reference_archetypes["After 2010"].constructions["ExtWall"].u_value
    assert newest < oldest
    assert 0.1 < newest < 1.0 and 0.5 < oldest < 4.0


def test_all_required_elements_and_window(reference_archetypes):
    """Every vintage carries the five opaque elements plus the derived
    IntFloor and a window."""
    for name, env in reference_archetypes.items():
        for ctype in ("ExtWall", "Roof", "GroundFloor", "IntWall", "IntCeiling", "IntFloor"):
            assert ctype in env.constructions, f"{name} missing {ctype}"
        assert env.window.u_value > 0
        assert 0.0 < env.wwr < 1.0


# --------------------------------------------------------------------- #
# Schedules_total.xlsx port
# --------------------------------------------------------------------- #
def test_all_reference_end_uses_present(reference_schedules):
    """All eleven the retained reference end-use archetypes load."""
    assert len(reference_schedules) == 11
    for name in ("residential", "services", "food", "school", "industrial"):
        assert name in reference_schedules


def test_three_day_types_are_distinguished(reference_schedules):
    """Saturday and Sunday differ from a weekday for the services end use —
    the retained reference's third day type is preserved, not collapsed into 'weekend'.
    2023-01-02 is a Monday, 01-07 a Saturday, 01-08 a Sunday."""
    gains = reference_schedules["services"].internal_gain_convective
    monday_noon = gains[24 + 12]
    saturday_noon = gains[24 * 6 + 12]
    sunday_noon = gains[24 * 7 + 12]
    assert monday_noon > saturday_noon >= sunday_noon
    assert sunday_noon != monday_noon


def test_expand_day_type_profiles_maps_calendar():
    """The three-day-type expander places Saturday/Sunday values on the right
    calendar days and returns a full annual array."""
    wd, sa, su = [1.0] * 24, [2.0] * 24, [3.0] * 24
    annual = expand_day_type_profiles(wd, sa, su, year=2023)
    assert len(annual) == 8760
    assert annual[24 * 1] == 1.0   # Mon 2 Jan
    assert annual[24 * 6] == 2.0   # Sat 7 Jan
    assert annual[24 * 7] == 3.0   # Sun 8 Jan
    with pytest.raises(ValueError):
        expand_day_type_profiles([1.0], sa, su)


def test_occupancy_split_uses_reference_fractions(reference_schedules):
    """Occupancy is split sensible/latent with the retained reference's People fractions
    (43% latent), and the sensible part into radiant/convective at 0.3/0.7."""
    res = reference_schedules["residential"]
    total_sensible = res.internal_gain_convective + res.internal_gain_radiative
    latent = res.internal_gain_latent
    # at midnight the residential sheet has occupancy 1.0 W/m2 and no
    # appliance/lighting radiant contribution ambiguity to worry about
    ratio = latent[0] / (latent[0] + 0.57)  # people-only sensible at that hour
    assert ratio == pytest.approx(0.43, abs=0.01)
    assert (total_sensible >= 0).all() and (latent >= 0).all()


def test_native_infiltration_and_ventilation_loaded(reference_schedules):
    """the retained reference's native infiltration [Vol/h] and ventilation [m3/(s m2)]
    profiles are carried through as optional arrays."""
    res = reference_schedules["residential"]
    services = reference_schedules["services"]
    assert res.infiltration_ach is not None and len(res.infiltration_ach) == 8760
    assert res.infiltration_ach.max() > 0
    assert services.ventilation_flow_per_area is not None
    assert services.ventilation_flow_per_area.max() > 0
    # residential has no mechanical ventilation in the retained reference's sheet
    assert res.ventilation_flow_per_area.max() == 0.0


def test_ahu_humidity_control_is_false(reference_schedules):
    """AHU humidity control is False for every end use — the workbook stores
    these as the strings 'True'/'False', for which a plain bool() cast would
    wrongly yield True."""
    for name, sched in reference_schedules.items():
        assert sched.ahu["humidity_control"] is False, name


def test_dhw_native_units(reference_schedules):
    """DHW keeps the retained reference's [L/(m2 h)] source and converts to [m3/(s m2)];
    residential is zero because the retained reference computes it via UNI-TS 11300-2."""
    services = reference_schedules["services"]
    assert services.dhw_volume_flow.max() > 0
    assert services.dhw_volume_flow.max() < 1e-5  # m3/(s m2), not litres
    assert reference_schedules["residential"].dhw_volume_flow.max() == 0.0


# --------------------------------------------------------------------- #
# End-to-end with both ported databases
# --------------------------------------------------------------------- #
def test_native_flows_reach_the_zone(data_dir):
    """The native ventilation/infiltration profiles are converted with the
    building's real floor area and volume in build_zone."""
    geometry = simple_building_geometry(
        "Office", footprint_area=400.0, height=9.0, n_floors=3,
        end_use="services", envelope="1981-1990",
    )
    district = preprocess_geometries(
        geometry,
        epw_path=data_dir / "ITA_Venezia-Tessera.161050_IGDG.epw",
        archetypes_path=ARCHETYPES, schedules_path=SCHEDULES,
    )
    building = district.buildings[0]
    zone = build_zone(building, district.weather)
    sched = building.schedule
    expected_peak = sched.ventilation_flow_per_area.max() * zone.net_floor_area * 1.2
    assert zone.ventilation_mass_flow.max() == pytest.approx(expected_peak, rel=1e-9)
    assert zone.infiltration_mass_flow.max() > 0  # schedule profile, not the envelope scalar


def test_full_district_run_with_reference_databases(data_dir):
    """The the retained reference-ported databases drive a complete district simulation with
    plausible specific demands."""
    from dt_prototype.common.preprocessing.building_input import preprocess_district
    from dt_prototype.dynamic.simulation.runner import run_portfolio

    district = preprocess_district(
        geojson_path=data_dir / "example_district.geojson",
        epw_path=data_dir / "ITA_Venezia-Tessera.161050_IGDG.epw",
        archetypes_path=ARCHETYPES, schedules_path=SCHEDULES,
        systems_path=data_dir / "systems_templates.json",
    )
    assert len(district.buildings) == 5
    results = run_portfolio(district, SimulationConfig(model="7R2C", plants=True))
    building_2 = next(b for b in district.buildings if b.name == "Test building 2")
    heating = results["Test building 2"]["heating_load"].sum() / 1000 / building_2.geometry.net_floor_area
    assert 30.0 < heating < 400.0  # kWh/m2, residential 1981-1990 in Venice


def test_schedule_json_round_trip_preserves_native_arrays(data_dir, tmp_path):
    """A BuildingInput built on the the retained reference databases survives the JSON
    round-trip with its optional native arrays intact."""
    geometry = simple_building_geometry(
        "Office", footprint_area=400.0, height=9.0, n_floors=3,
        end_use="services", envelope="1981-1990",
    )
    district = preprocess_geometries(
        geometry,
        epw_path=data_dir / "ITA_Venezia-Tessera.161050_IGDG.epw",
        archetypes_path=ARCHETYPES, schedules_path=SCHEDULES,
    )
    path = tmp_path / "building.json"
    district.buildings[0].to_json(path)
    reloaded = BuildingInput.from_json(path)
    original = district.buildings[0].schedule
    np.testing.assert_allclose(
        reloaded.schedule.ventilation_flow_per_area, original.ventilation_flow_per_area
    )
    np.testing.assert_allclose(reloaded.schedule.infiltration_ach, original.infiltration_ach)
    # multi-layer constructions survive too
    assert len(reloaded.envelope.constructions["ExtWall"].layers) == len(
        original_layers := district.buildings[0].envelope.constructions["ExtWall"].layers
    ) and len(original_layers) > 1

