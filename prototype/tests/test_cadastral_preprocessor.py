"""Tests for conservative cadastral-to-engine input generation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from dt_prototype.common.preprocessing.cadastre import generate_cadastral_inputs
from dt_prototype.common.preprocessing.geometry import load_district_geojson
from dt_prototype.common.preprocessing.tabular_geometry import load_district_tables


ROOT = Path(__file__).resolve().parents[1]


def _feature(building_id: str, properties: dict) -> dict:
    return {
        "type": "Feature",
        "properties": {"building_id": building_id, **properties},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[1000.0, 1000.0], [1010.0, 1000.0], [1010.0, 1010.0],
                 [1000.0, 1010.0], [1000.0, 1000.0]]
            ],
        },
    }


def _rules() -> dict:
    return {
        "schema_version": "1.0",
        "defaults": {
            "envelope": "fallback",
            "end_use": "residential",
            "storey_height_m": 3.0,
            "n_floors": 1,
        },
        "use_map": {
            "residenziale": "residential",
            "commerciale": "shop",
        },
        "rules": [
            {
                "id": "urbem-pie-e-1981",
                "source": "URBEM",
                "source_archetype": "RES_APPBLOCK_1981-1990_E_PIE",
                "envelope": "1981-1990",
                "year_min": 1981,
                "year_max": 1990,
                "end_uses": ["residential"],
                "building_types": ["apartment block"],
                "regions": ["Piemonte"],
                "climate_zones": ["E"],
            }
        ],
    }


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_generates_single_and_explicit_two_zone_buildings(tmp_path):
    source = {
        "type": "FeatureCollection",
        "features": [
            _feature(
                "one",
                {
                    "construction_year": 1985,
                    "use": "residenziale",
                    "building_type": "apartment block",
                    "region": "Piemonte",
                    "climate_zone": "E",
                    "n_floors": 3,
                },
            ),
            _feature(
                "two",
                {
                    "construction_year": 1985,
                    "use": "residenziale",
                    "ground_floor_use": "commerciale",
                    "building_type": "apartment block",
                    "region": "Piemonte",
                    "climate_zone": "E",
                    "n_floors": 4,
                    "height_m": 12,
                },
            ),
        ],
    }
    source_path = tmp_path / "cadastre.geojson"
    rules_path = tmp_path / "rules.json"
    output = tmp_path / "generated"
    _write_json(source_path, source)
    _write_json(rules_path, _rules())

    manifest = generate_cadastral_inputs(source_path, rules_path, output)

    assert manifest["building_count"] == 2
    assert manifest["single_zone_count"] == 1
    assert manifest["two_zone_count"] == 1
    geometries = load_district_tables(output / "geometry")
    assert geometries[0].height == 9.0
    assert geometries[0].zones[0].zone_label == "single"
    assert geometries[0].envelope == "1981-1990"
    assert [zone.zone_label for zone in geometries[1].zones] == ["upper", "lower"]
    assert [zone.end_use for zone in geometries[1].zones] == ["residential", "shop"]

    with (output / "preprocessing_report.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["dimension_method"] == "height_from_floors"
    assert rows[0]["source_archetype"] == "RES_APPBLOCK_1981-1990_E_PIE"
    assert rows[1]["zoning_reason"] == "two zones: explicit distinct ground-floor use"


def test_unknown_ground_floor_use_stays_single_zone_and_is_reported(tmp_path):
    source = {
        "type": "FeatureCollection",
        "features": [
            _feature(
                "one",
                {
                    "use": "residenziale",
                    "ground_floor_use": "unknown use",
                    "n_floors": 3,
                },
            )
        ],
    }
    source_path = tmp_path / "cadastre.geojson"
    rules_path = tmp_path / "rules.json"
    output = tmp_path / "generated"
    _write_json(source_path, source)
    _write_json(rules_path, _rules())

    manifest = generate_cadastral_inputs(source_path, rules_path, output)

    assert manifest["single_zone_count"] == 1
    report = (output / "preprocessing_report.csv").read_text(encoding="utf-8")
    assert "two-zone split suppressed" in report
    assert "ground-floor use was not recognized" in report


def test_geographic_crs_is_rejected(tmp_path):
    source = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": [_feature("one", {"n_floors": 1})],
    }
    source_path = tmp_path / "cadastre.geojson"
    rules_path = tmp_path / "rules.json"
    _write_json(source_path, source)
    _write_json(rules_path, _rules())

    with pytest.raises(ValueError, match="Reproject footprints"):
        generate_cadastral_inputs(source_path, rules_path, tmp_path / "generated")


def test_equal_rank_rules_are_rejected_as_ambiguous(tmp_path):
    source = {
        "type": "FeatureCollection",
        "features": [_feature("one", {"use": "residenziale", "n_floors": 1})],
    }
    rules = _rules()
    rules["rules"] = [
        {"id": "a", "envelope": "a", "end_uses": ["residential"]},
        {"id": "b", "envelope": "b", "end_uses": ["residential"]},
    ]
    source_path = tmp_path / "cadastre.geojson"
    rules_path = tmp_path / "rules.json"
    _write_json(source_path, source)
    _write_json(rules_path, rules)

    with pytest.raises(ValueError, match="Ambiguous archetype rules"):
        generate_cadastral_inputs(source_path, rules_path, tmp_path / "generated")


def test_existing_output_is_never_overwritten(tmp_path):
    source_path = tmp_path / "cadastre.geojson"
    rules_path = tmp_path / "rules.json"
    output = tmp_path / "generated"
    output.mkdir()
    _write_json(
        source_path,
        {"type": "FeatureCollection", "features": [_feature("one", {"n_floors": 1})]},
    )
    _write_json(rules_path, _rules())

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        generate_cadastral_inputs(source_path, rules_path, output)


def test_existing_geojson_is_reproduced_exactly_when_assignments_are_present(tmp_path):
    source = ROOT / "data" / "examples" / "example_district.geojson"
    rules = ROOT / "configs" / "cadastral_archetype_rules.example.json"
    output = tmp_path / "generated"

    manifest = generate_cadastral_inputs(source, rules, output)
    expected = load_district_geojson(source)
    actual = load_district_tables(output / "geometry")

    assert [building.to_dict() for building in actual] == [
        building.to_dict() for building in expected
    ]
    assert manifest["single_zone_count"] == 1
    assert manifest["two_zone_count"] == 4
