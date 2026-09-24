"""Tests for the system template database, input validation and the
direct-geometry pipeline route."""

from __future__ import annotations

import pytest

from dt_prototype.common.preprocessing.building_input import preprocess_geometries
from dt_prototype.common.preprocessing.geometry import (
    building_geometry_from_feature,
    simple_building_geometry,
)
from dt_prototype.common.preprocessing.system_templates import load_system_templates
from dt_prototype.dynamic.simulation.config import SimulationConfig
from dt_prototype.dynamic.simulation.runner import run_building
from dt_prototype.dynamic.simulation.systems import (
    Boiler,
    CoolingFromParams,
    HeatingFromParams,
    IdealLoad,
    resolve_cooling_system,
    resolve_heating_system,
)
from dt_prototype.dynamic.validation import validate_district, validate_district_inputs


@pytest.fixture(scope="module")
def templates(data_dir):
    """Loaded HVAC system template database (the retained reference Systems.xlsx port)."""
    return load_system_templates(data_dir / "systems_templates.json")


# --------------------------------------------------------------------- #
# System template database
# --------------------------------------------------------------------- #
def test_template_database_loads(templates):
    """The ported the retained reference Systems.xlsx provides all short-code templates,
    including those referenced by the example district."""
    for code in ("s2", "s4", "s14", "s19"):
        assert code in templates["heating_systems"] or code in templates["cooling_systems"]
    assert len(templates["heating_systems"]) >= 30
    assert len(templates["cooling_systems"]) >= 5


def test_template_lookup_precedes_catalog(templates):
    """Short codes resolve via the template DB; descriptive catalog names
    still resolve via parsing; templates win only for exact matches."""
    system, warning = resolve_heating_system("s19", templates)
    assert isinstance(system, HeatingFromParams) and warning is None
    system, warning = resolve_cooling_system("s2", templates)
    assert isinstance(system, CoolingFromParams) and warning is None
    system, warning = resolve_heating_system("CondensingBoiler", templates)
    assert isinstance(system, Boiler) and warning is None  # catalog route


def test_unresolvable_name_reports_warning(templates):
    """A name in neither the template DB nor the catalog falls back to
    IdealLoad with a structured warning."""
    system, warning = resolve_heating_system("nonexistent-system", templates)
    assert isinstance(system, IdealLoad)
    assert "falling back to IdealLoad" in warning


def test_template_system_consumes_declared_fuel(templates):
    """A gas template books consumption on gas; electric templates with a
    COP divide by it."""
    s19 = HeatingFromParams(templates["heating_systems"]["s19"])
    out = s19.solve(10_000.0, 5.0, dhw=1_000.0)
    assert out.gas > 11_000.0  # chain efficiency < 1 → more fuel than load
    assert out.electric == 0.0


# --------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------- #
def test_validation_without_templates_flags_scodes(data_dir):
    """Without the template DB, the example district's short system codes
    are reported as IdealLoad fallbacks (one issue each)."""
    issues = validate_district_inputs(
        geojson_path=data_dir / "example_district.geojson",
        archetypes_path=data_dir / "archetypes_fixture.json",
        schedules_path=data_dir / "schedules_fixture.json",
    )
    system_issues = [i for i in issues if "System" in i["field"]]
    assert {(i["building"], i["value"]) for i in system_issues} == {
        ("Test building 2", "s19"), ("Test building 2", "s4"), ("Test building 3", "s2"), ("Test building 4", "s14"),
    }


def test_validation_with_templates_resolves_all_systems(data_dir):
    """The corrected reference inputs pass all preflight checks."""
    issues = validate_district_inputs(
        geojson_path=data_dir / "example_district.geojson",
        archetypes_path=data_dir / "archetypes_fixture.json",
        schedules_path=data_dir / "schedules_fixture.json",
        systems_path=data_dir / "systems_templates.json",
    )
    assert issues == []


def test_implausible_storey_height_warns_and_is_a_validation_error(
    archetypes, schedules, templates
):
    """A total-height/storey-count mix-up is visible during parsing and
    blocks a clean validation result."""
    feature = {
        "type": "Feature",
        "properties": {
            "id": "bad-height",
            "Name": "bad-height",
            "End Use": next(iter(schedules)),
            "Envelope": next(iter(archetypes)),
            "Height": 3.0,
            "Floors": 12,
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
        },
    }
    with pytest.warns(RuntimeWarning, match="implausible mean storey height"):
        geometry = building_geometry_from_feature(feature)

    from dt_prototype.dynamic.validation import validate_geometries

    issues = validate_geometries([geometry], archetypes, schedules, templates)
    geometry_issues = [issue for issue in issues if issue["field"] == "geometry"]
    assert len(geometry_issues) == 1
    assert geometry_issues[0]["severity"] == "error"
    assert "total building height" in geometry_issues[0]["message"]


def test_validation_catches_bad_references(data_dir, archetypes, schedules, templates):
    """Broken envelope/end-use references are reported as errors, all at
    once, instead of failing one KeyError at a time."""
    from dt_prototype.dynamic.validation import validate_geometries

    bad = simple_building_geometry(
        "bad", 100.0, 6.0, 2, end_use="no-such-use", envelope="no-such-envelope"
    )
    issues = validate_geometries([bad], archetypes, schedules, templates)
    errors = {i["field"] for i in issues if i["severity"] == "error"}
    assert {"Envelope", "End Use"} <= errors


def test_validate_district_after_preprocessing(district):
    """The post-preprocessing check runs on a DistrictInput and finds no
    system issues (fixture is preprocessed with the template DB)."""
    issues = validate_district(district)
    assert all("System" not in i["field"] for i in issues)


# --------------------------------------------------------------------- #
# Direct-geometry route
# --------------------------------------------------------------------- #
def test_direct_geometry_route(data_dir):
    """A building built without any GeoJSON runs through the identical
    pipeline and resolves its template systems."""
    box = simple_building_geometry(
        name="direct", footprint_area=400.0, height=9.0, n_floors=3,
        end_use="services", envelope="1991-2005",
        heating_system="s19", cooling_system="s2",
    )
    district = preprocess_geometries(
        box,
        epw_path=data_dir / "ITA_Venezia-Tessera.161050_IGDG.epw",
        archetypes_path=data_dir / "archetypes_fixture.json",
        schedules_path=data_dir / "schedules_fixture.json",
        systems_path=data_dir / "systems_templates.json",
    )
    assert district.building_names == ["direct"]
    df = run_building(
        district.buildings[0], district.weather,
        SimulationConfig(model="7R2C", plants=True),
        system_templates=district.system_templates,
    )
    assert df.attrs["warnings"] == []
    assert df["gas"].sum() > 0.0  # s19 template gas boiler engaged


def test_simple_geometry_matches_feature_route():
    """simple_building_geometry produces the same surface set as the
    equivalent GeoJSON feature (four walls, roof, ground, internals)."""
    g = simple_building_geometry("sq", 100.0, 6.0, 2, "residential", "test")
    types = sorted(s.surface_type for s in g.surfaces)
    assert types.count("ExtWall") == 4
    assert g.footprint_area == pytest.approx(100.0)
    assert g.net_floor_area == pytest.approx(200.0)
    walls = sorted(round(s.azimuth) % 360 for s in g.surfaces if s.surface_type == "ExtWall")
    assert walls == [0, 90, 180, 270]
    with pytest.raises(ValueError):
        simple_building_geometry("bad", -1.0, 6.0, 2, "residential", "test")


def test_runner_warnings_attached(district_no_templates):
    """Runs without the template DB attach the IdealLoad fallbacks to the
    result DataFrame attrs (visible in batch workflows)."""
    building = next(b for b in district_no_templates.buildings if b.name == "Test building 2")
    df = run_building(
        building, district_no_templates.weather, SimulationConfig(model="5R1C", plants=True)
    )
    assert any("s19" in w for w in df.attrs["warnings"])
