"""Tests for the serialised preprocessing→simulation handoff (FR-08)."""

from __future__ import annotations

import numpy as np
import pytest

from dt_prototype.common.preprocessing.building_input import (
    BuildingInput,
    assemble_building_input,
)
from dt_prototype.common.preprocessing.geometry import ZoneGeometry, load_district_geojson


def test_district_assembly(district):
    """The full pipeline binds all 5 example buildings to their archetypes,
    and — per building — every zone's schedule to its own end use (Test building 2,
    Test building 3, Test building 1, Test building 4 are two-zone; Test building 5 is single-zone)."""
    assert len(district.buildings) == 5
    for b in district.buildings:
        assert b.envelope.name == b.geometry.envelope
        assert b.schedule.name == b.geometry.end_use
        for zone in b.zones:
            assert zone.schedule.name == zone.geometry.end_use
    two_zone = {b.name for b in district.buildings if len(b.zones) == 2}
    assert two_zone == {"Test building 1", "Test building 2", "Test building 3", "Test building 4"}


def test_missing_archetype_raises(data_dir, archetypes, schedules):
    """Referencing an unknown envelope archetype fails with a clear error."""
    geometry = load_district_geojson(data_dir / "example_district.geojson")[0]
    geometry.envelope = "does-not-exist"
    with pytest.raises(KeyError, match="does-not-exist"):
        assemble_building_input(geometry, archetypes, schedules)


def test_missing_lower_end_use_raises_naming_the_zone(data_dir, archetypes, schedules):
    """A two-zone building whose Lower End Use isn't in the schedule
    database fails with a clear, zone-naming error."""
    geometries = load_district_geojson(data_dir / "example_district.geojson")
    building_2 = next(g for g in geometries if g.name == "Test building 2")
    assert len(building_2.zones) == 2
    broken_lower = ZoneGeometry(
        name=building_2.zones[1].name,
        zone_label="lower",
        end_use="does-not-exist",
        n_floors=building_2.zones[1].n_floors,
        net_floor_area=building_2.zones[1].net_floor_area,
        volume=building_2.zones[1].volume,
        surfaces=building_2.zones[1].surfaces,
    )
    building_2.zones = [building_2.zones[0], broken_lower]
    with pytest.raises(KeyError, match="does-not-exist"):
        assemble_building_input(building_2, archetypes, schedules)


def test_building_json_round_trip(district, tmp_path):
    """A BuildingInput serialises to one JSON file and reloads equal —
    the pipeline artefact is fully inspectable (FR-08, NFR-03). Uses Test building 2, a
    two-zone building, so both zones' schedules are exercised."""
    b = next(x for x in district.buildings if x.name == "Test building 2")
    assert len(b.zones) == 2
    path = tmp_path / "building.json"
    b.to_json(path)
    b2 = BuildingInput.from_json(path)
    assert b2.geometry.to_dict() == b.geometry.to_dict()
    assert b2.envelope.to_dict() == b.envelope.to_dict()
    assert len(b2.zones) == len(b.zones)
    for z2, z in zip(b2.zones, b.zones):
        np.testing.assert_allclose(z2.schedule.heating_setpoint, z.schedule.heating_setpoint)
        np.testing.assert_allclose(z2.schedule.dhw_volume_flow, z.schedule.dhw_volume_flow)
        assert z2.schedule.ahu == z.schedule.ahu


def test_pipeline_writes_artifacts(district, data_dir, tmp_path):
    """preprocess_district(output_dir=...) writes weather CSV and one JSON
    per building (self-documenting pipeline, NFR-03)."""
    from dt_prototype.common.preprocessing.building_input import preprocess_district

    out = tmp_path / "preproc"
    preprocess_district(
        geojson_path=data_dir / "example_district.geojson",
        epw_path=data_dir / "ITA_Venezia-Tessera.161050_IGDG.epw",
        archetypes_path=data_dir / "archetypes_fixture.json",
        schedules_path=data_dir / "schedules_fixture.json",
        output_dir=out,
    )
    assert (out / "weather.csv").exists()
    assert (out / "weather.meta.json").exists()
    assert len(list((out / "buildings").glob("*.json"))) == 5
