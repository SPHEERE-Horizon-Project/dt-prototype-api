"""Compatibility checks for flat parametric and canonical zoned inputs."""

from __future__ import annotations

import json

import pandas as pd

from tests.dynamic.conftest import make_box_building, make_constant_weather
from dt_prototype.common.preprocessing.building_input import BuildingInput
from dt_prototype.common.preprocessing.geometry import BuildingGeometry, SurfaceSpec
from dt_prototype.dynamic.simulation.config import SimulationConfig
from dt_prototype.dynamic.simulation.runner import run_building


def _flat_geometry_from(building: BuildingInput) -> BuildingGeometry:
    """Recreate a canonical one-zone geometry through CURRENT's flat API."""
    geometry = building.geometry
    zone = geometry.zones[0]
    return BuildingGeometry(
        geometry.name,
        geometry.building_id,
        zone.end_use,
        geometry.envelope,
        geometry.heating_system,
        geometry.cooling_system,
        geometry.solar_technologies,
        geometry.n_floors,
        geometry.height,
        geometry.footprint_area,
        zone.net_floor_area,
        zone.volume,
        list(zone.surfaces),
    )


def test_flat_geometry_constructor_normalises_to_one_zone():
    """The prior CURRENT positional constructor remains accepted."""
    surfaces = [SurfaceSpec("IntWall", 200.0)]
    geometry = BuildingGeometry(
        "flat", "flat-id", "residential", "test",
        n_floors=2, height=6.0, footprint_area=100.0,
        net_floor_area=200.0, volume=600.0, surfaces=surfaces,
    )

    assert len(geometry.zones) == 1
    assert geometry.zones[0].zone_label == "single"
    assert geometry.end_use == "residential"
    assert geometry.net_floor_area == 200.0
    assert geometry.volume == 600.0
    assert geometry.surfaces == surfaces


def test_flat_and_canonical_single_zone_runs_are_identical():
    """Input normalisation does not alter any single-zone numerical result."""
    canonical = make_box_building(n_steps=72)
    flat_geometry = _flat_geometry_from(canonical)
    flat = BuildingInput(flat_geometry, canonical.envelope, canonical.schedule)
    weather = make_constant_weather(t_ext=5.0, n_steps=72)
    config = SimulationConfig(model="7R2C", plants=False, latent=True)

    expected = run_building(canonical, weather, config)
    actual = run_building(flat, weather, config)
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)


def test_legacy_flat_json_is_still_readable(tmp_path):
    """CURRENT's old flat geometry + singular schedule payload migrates on load."""
    canonical = make_box_building(n_steps=24)
    flat_geometry = _flat_geometry_from(canonical)
    zone = flat_geometry.zones[0]
    legacy_geometry = {
        "name": flat_geometry.name,
        "building_id": flat_geometry.building_id,
        "end_use": zone.end_use,
        "envelope": flat_geometry.envelope,
        "heating_system": flat_geometry.heating_system,
        "cooling_system": flat_geometry.cooling_system,
        "solar_technologies": flat_geometry.solar_technologies,
        "n_floors": flat_geometry.n_floors,
        "height": flat_geometry.height,
        "footprint_area": flat_geometry.footprint_area,
        "net_floor_area": zone.net_floor_area,
        "volume": zone.volume,
        "surfaces": [s.__dict__ for s in zone.surfaces],
    }
    payload = {
        "geometry": legacy_geometry,
        "envelope": canonical.envelope.to_dict(),
        "schedule": canonical.schedule.to_dict(),
    }
    path = tmp_path / "legacy-flat-building.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = BuildingInput.from_json(path)
    assert len(loaded.zones) == 1
    assert loaded.geometry.end_use == canonical.geometry.end_use
    assert loaded.geometry.net_floor_area == canonical.geometry.net_floor_area
    assert loaded.schedule.name == canonical.schedule.name
