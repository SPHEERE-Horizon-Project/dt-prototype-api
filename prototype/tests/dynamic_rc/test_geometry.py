"""Tests for the GeoJSON geometry module (FR-02, FR-06)."""

from __future__ import annotations

import math

from dt_prototype.common.preprocessing.geometry import (
    BuildingGeometry,
    building_geometry_from_feature,
    load_district_geojson,
    ring_area,
)


def _square_feature(
    side: float = 10.0,
    height: float = 6.0,
    floors: int = 2,
    upper_end_use: str | None = None,
    lower_end_use: str | None = None,
) -> dict:
    """GeoJSON feature of an axis-aligned square footprint (CCW ring)."""
    props = {
        "id": 1,
        "Name": "sq",
        "End Use": "residential",
        "Envelope": "test",
        "Height": height,
        "Floors": floors,
    }
    if upper_end_use is not None:
        props["Upper End Use"] = upper_end_use
    if lower_end_use is not None:
        props["Lower End Use"] = lower_end_use
    ring = [[0, 0], [side, 0], [side, side], [0, side], [0, 0]]
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


def test_ring_area_signed():
    """Shoelace area is positive for CCW rings and matches the square area."""
    ring = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    assert abs(ring_area(ring) - 100.0) < 1e-9
    assert abs(ring_area(list(reversed(ring))) + 100.0) < 1e-9


def test_square_extrusion():
    """A 10x10x6 m square with 2 floors produces the expected areas/volume."""
    g = building_geometry_from_feature(_square_feature())
    assert abs(g.footprint_area - 100.0) < 1e-9
    assert abs(g.volume - 600.0) < 1e-9
    assert abs(g.net_floor_area - 200.0) < 1e-9
    walls = [s for s in g.surfaces if s.surface_type == "ExtWall"]
    assert len(walls) == 4
    assert all(abs(w.area - 60.0) < 1e-9 for w in walls)
    # outward normals of a CCW square: S, E, N, W in edge order
    azimuths = sorted(round(w.azimuth) % 360 for w in walls)
    assert azimuths == [0, 90, 180, 270]


def test_courtyard_hole_subtracts_area_and_adds_walls():
    """A hole reduces the footprint and its edges become courtyard walls."""
    feature = _square_feature(side=20.0)
    hole = [[8, 8], [8, 12], [12, 12], [12, 8], [8, 8]]  # CW hole, 4x4 m
    feature["geometry"]["coordinates"].append(hole)
    g = building_geometry_from_feature(feature)
    assert abs(g.footprint_area - (400.0 - 16.0)) < 1e-9
    walls = [s for s in g.surfaces if s.surface_type == "ExtWall"]
    assert len(walls) == 8  # 4 outer + 4 courtyard


def test_internal_surfaces_between_storeys():
    """Multi-storey buildings get interstorey floors/ceilings and partitions."""
    g = building_geometry_from_feature(_square_feature(floors=3))
    types = {s.surface_type: s.area for s in g.surfaces}
    assert abs(types["IntFloor"] - 200.0) < 1e-9  # (3-1) x footprint
    assert abs(types["IntCeiling"] - 200.0) < 1e-9
    assert abs(types["IntWall"] - 300.0) < 1e-9  # net floor area


def test_two_zone_split_wall_roof_and_ground():
    """Distinct Upper/Lower End Use splits into 2 zones per the retained reference's method:
    walls split by floor height, roof only upper, ground floor only lower,
    whole-building totals unchanged (footprint not doubled, nfa/volume =
    sum of both zones)."""
    g = building_geometry_from_feature(
        _square_feature(side=10.0, height=9.0, floors=3,
                         upper_end_use="services", lower_end_use="food")
    )
    assert len(g.zones) == 2
    upper, lower = g.zones
    assert (upper.zone_label, lower.zone_label) == ("upper", "lower")
    assert upper.end_use == "services"
    assert lower.end_use == "food"
    assert upper.n_floors == 2
    assert lower.n_floors == 1

    upper_walls = [s for s in upper.surfaces if s.surface_type == "ExtWall"]
    lower_walls = [s for s in lower.surfaces if s.surface_type == "ExtWall"]
    assert all(abs(w.area - 60.0) < 1e-9 for w in upper_walls)  # 10 x (9/3 x 2)
    assert all(abs(w.area - 30.0) < 1e-9 for w in lower_walls)  # 10 x (9/3 x 1)

    assert any(s.surface_type == "Roof" for s in upper.surfaces)
    assert not any(s.surface_type == "Roof" for s in lower.surfaces)
    assert any(s.surface_type == "GroundFloor" for s in lower.surfaces)
    assert not any(s.surface_type == "GroundFloor" for s in upper.surfaces)

    # whole-building fields stay building-level, not summed/doubled
    assert abs(g.footprint_area - 100.0) < 1e-9
    assert g.n_floors == 3
    # zone-derived aggregates match the un-split single-zone equivalent
    assert abs(g.net_floor_area - 300.0) < 1e-9  # 100 x 3
    assert abs(g.volume - 900.0) < 1e-9  # 100 x 9


def test_same_upper_lower_end_use_stays_single_zone():
    """Upper == Lower End Use is not a real split (matches the retained reference's trigger
    condition)."""
    g = building_geometry_from_feature(
        _square_feature(upper_end_use="residential", lower_end_use="residential")
    )
    assert len(g.zones) == 1
    assert g.zones[0].zone_label == "single"


def test_empty_lower_end_use_stays_single_zone():
    """An empty Lower End Use (as Test building 5 has in the example district) means
    no split, per the retained reference's trigger condition."""
    g = building_geometry_from_feature(
        _square_feature(upper_end_use="services", lower_end_use="")
    )
    assert len(g.zones) == 1


def test_single_floor_with_lower_end_use_stays_single_zone():
    """A 1-floor building can't have a distinct upper zone (0 floors left),
    so it stays single-zone even with a distinct Lower End Use declared."""
    g = building_geometry_from_feature(
        _square_feature(floors=1, upper_end_use="services", lower_end_use="food")
    )
    assert len(g.zones) == 1


def test_load_reference_example_district(data_dir):
    """The the retained reference example district parses into 5 valid building geometries;
    4 of them (distinct, non-empty Lower End Use) become two-zone, Test building 5
    (empty Lower End Use) stays single-zone."""
    buildings = load_district_geojson(data_dir / "example_district.geojson")
    assert len(buildings) == 5
    names = {b.name for b in buildings}
    assert {"Test building 1", "Test building 2", "Test building 3", "Test building 4", "Test building 5"} == names
    for b in buildings:
        assert b.footprint_area > 0
        assert any(s.surface_type == "ExtWall" for s in b.surfaces)

    two_zone_names = {b.name for b in buildings if len(b.zones) == 2}
    single_zone_names = {b.name for b in buildings if len(b.zones) == 1}
    assert two_zone_names == {"Test building 1", "Test building 2", "Test building 3", "Test building 4"}
    assert single_zone_names == {"Test building 5"}


def test_property_lookup_tolerates_capitalisation_drift():
    """Attribute capitalisation varies between real district files (the retained reference's
    own example writes 'Solar Technologies'; its loader normalises the case).
    A silent miss would disable PV/solar thermal without any error, so the
    parser accepts either casing."""
    feature = _square_feature()
    props = feature["properties"]
    props.pop("End Use")
    props["end use"] = "residential"
    props["Solar Technologies"] = "PV,ST"  # capital T, as the retained reference's file has
    props["FLOORS"] = props.pop("Floors")
    g = building_geometry_from_feature(feature)
    assert g.solar_technologies == "PV,ST"
    assert g.end_use == "residential"
    assert g.n_floors == 2




def test_geometry_dict_round_trip():
    """BuildingGeometry serialises to a plain dict and reloads equal (FR-08)."""
    g = building_geometry_from_feature(_square_feature())
    g2 = BuildingGeometry.from_dict(g.to_dict())
    assert g2.to_dict() == g.to_dict()
