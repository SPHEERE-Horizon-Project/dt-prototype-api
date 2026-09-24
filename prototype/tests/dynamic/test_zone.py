"""Tests for thermal zone assembly (``simulation.zone.build_zone``),
including the ``zone_index`` selector two-zone buildings need."""

from __future__ import annotations

from dt_prototype.dynamic.simulation.zone import build_zone


def test_build_zone_defaults_to_index_zero(district):
    """Omitting zone_index builds the primary (single, or upper) zone."""
    building_2 = next(b for b in district.buildings if b.name == "Test building 2")
    zone = build_zone(building_2, district.weather)
    zone_0 = build_zone(building_2, district.weather, zone_index=0)
    assert zone.name == zone_0.name == building_2.zones[0].geometry.name


def test_two_zone_building_has_two_distinct_zones(district):
    """Test building 2 (Upper End Use 'residential', Lower End Use 'food') builds two
    Zone objects with different net floor area and different gains, since
    each zone's own schedule is applied."""
    building_2 = next(b for b in district.buildings if b.name == "Test building 2")
    assert len(building_2.zones) == 2
    upper = build_zone(building_2, district.weather, zone_index=0)
    lower = build_zone(building_2, district.weather, zone_index=1)
    assert upper.name != lower.name
    assert upper.net_floor_area != lower.net_floor_area
    assert not (upper.gains_convective == lower.gains_convective).all()


def test_building_level_fields_identical_across_zones(district):
    """Heating/cooling system and solar technologies are building-level
    (shared plant/roof, per the retained reference), so both zones of a two-zone building
    must see the identical values even though each zone's own
    net_floor_area/gains/schedule differ."""
    building_2 = next(b for b in district.buildings if b.name == "Test building 2")
    upper = build_zone(building_2, district.weather, zone_index=0)
    lower = build_zone(building_2, district.weather, zone_index=1)
    assert upper.heating_system_name == lower.heating_system_name == building_2.geometry.heating_system
    assert upper.cooling_system_name == lower.cooling_system_name == building_2.geometry.cooling_system
    assert upper.solar_technologies == lower.solar_technologies == building_2.geometry.solar_technologies


def test_single_zone_building_only_has_index_zero(district):
    """Test building 5 (empty Lower End Use) has exactly one zone."""
    building_5 = next(b for b in district.buildings if b.name == "Test building 5")
    assert len(building_5.zones) == 1
    zone = build_zone(building_5, district.weather, zone_index=0)
    assert zone.name == building_5.zones[0].geometry.name

