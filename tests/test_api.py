from __future__ import annotations

import copy
import csv
import json
import subprocess
import tomllib
from importlib.metadata import version
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient

from spheere_dt_api.adapter import result_from_output
from spheere_dt_api.app import create_app
from spheere_dt_api.contract import openapi_spec

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "prototype/data/examples"
WEATHER = (EXAMPLES / "ITA_Venezia-Tessera.161050_IGDG.epw").read_bytes()
SPEC = openapi_spec()


def test_package_lock_and_api_versions_agree(tmp_path: Path) -> None:
    package = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    locked = next(
        entry
        for entry in tomllib.loads((ROOT / "uv.lock").read_text())["package"]
        if entry["name"] == package["name"]
    )
    application = create_app(tmp_path)
    with TestClient(application) as client:
        assert client.get("/openapi.json").json()["info"]["version"] == package["version"]
    assert (
        application.version == version(package["name"]) == locked["version"] == package["version"]
    )


def example_project(engine: str, run_id: str) -> dict:
    project = copy.deepcopy(
        SPEC["components"]["examples"][f"{engine.title()}Request"]["value"]["project"]
    )
    project["run_id"] = run_id
    return project


def send(client: TestClient, engine: str, project: dict, weather: bytes = WEATHER):
    return client.post(
        f"/runs/{engine}",
        files={
            "project": ("project.json", json.dumps(project), "application/json"),
            "weather_epw": ("weather.epw", weather, "text/plain"),
        },
    )


def assert_contract(engine: str, result: dict) -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "components": {"schemas": SPEC["components"]["schemas"]},
        "$ref": f"#/components/schemas/{engine.title()}RunResult",
    }

    jsonschema.Draft202012Validator(schema).validate(result)


@pytest.mark.parametrize("engine,details", [("dynamic", 8760), ("monthly", 12), ("simplified", 12)])
def test_each_engine_returns_source_results(tmp_path: Path, engine: str, details: int) -> None:
    with TestClient(create_app(tmp_path)) as client:
        response = send(client, engine, example_project(engine, f"test_{engine}"))

    assert response.status_code == 200, response.text[:1000]
    result = response.json()
    assert_contract(engine, result)
    assert result["manifest"]["status"] == "complete"
    assert len(result["monthly"]) == 12
    assert len(result["annual"]) == 1
    assert len(result["details_by_building"]["B1"]) == details

    output = tmp_path / "results" / f"test_{engine}"

    with (output / "monthly.csv").open(newline="") as stream:
        source_monthly = list(csv.DictReader(stream))

    with (output / "annual.csv").open(newline="") as stream:
        source_annual = list(csv.DictReader(stream))

    assert result["monthly"][0]["heating_kWh"] == pytest.approx(
        float(source_monthly[0]["heating_kWh"])
    )

    assert result["annual"][0]["cooling_kWh"] == pytest.approx(
        float(source_annual[0]["cooling_kWh"])
    )


def test_invalid_weather_duplicate_and_unsafe_id(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        project = example_project("monthly", "case_one")
        bad_weather = send(client, "monthly", project, b"invalid EPW")
        assert bad_weather.status_code == 422
        assert bad_weather.json()["code"] == "invalid_weather"
        assert not (tmp_path / "inputs" / "case_one").exists()

        good = send(client, "monthly", project)
        assert good.status_code == 200
        assert send(client, "monthly", project).status_code == 409

        project["run_id"] = "../escape"
        unsafe = send(client, "monthly", project)
        assert unsafe.status_code == 422
        assert not (tmp_path / "escape").exists()


def test_malformed_multipart_parts_return_input_errors(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        malformed = client.post(
            "/runs/monthly",
            files={
                "project": ("project.json", "{", "application/json"),
                "weather_epw": ("weather.epw", WEATHER, "text/plain"),
            },
        )
        assert malformed.status_code == 422
        assert malformed.json()["field"] == "project"

        missing_weather = client.post(
            "/runs/monthly",
            files={
                "project": (
                    "project.json",
                    json.dumps(example_project("monthly", "missing_weather")),
                    "application/json",
                )
            },
        )
        assert missing_weather.status_code == 422
        assert missing_weather.json()["field"] == "weather_epw"


def test_runner_failure_without_manifest_returns_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "spheere_dt_api.app.run_cli",
        lambda *_: subprocess.CompletedProcess([], 1, "", "runner stopped"),
    )

    with TestClient(create_app(tmp_path)) as client:
        response = send(client, "monthly", example_project("monthly", "failed_runner"))

    assert response.status_code == 500
    assert response.json()["code"] == "runner_failed"
    assert "runner stopped" in response.json()["message"]


def test_failed_building_manifest_keeps_completed_building(tmp_path: Path) -> None:
    output = tmp_path / "failed_run"
    output.mkdir()

    (output / "manifest.json").write_text(
        json.dumps(
            {
                "name": "DT-Prototype",
                "version": "0.4.0",
                "engine": "monthly",
                "status": "failed",
                "timestamp_utc": "2026-09-24T09:00:00Z",
                "input_hashes": {},
                "building_outputs": {
                    "B1": {"building_name": "First", "details_file": "B1_details.csv"},
                    "B2": {"building_name": "Second", "details_file": "B2_details.csv"},
                },
                "failed_buildings": [{"building_id": "B2", "error": "calculation failed"}],
            }
        )
    )

    (output / "B1_details.csv").write_text("month,heating_demand_kWh\n2023-01-01,12\n")
    (output / "monthly.csv").write_text("building_id,heating_kWh\nB1,12\n")
    (output / "annual.csv").write_text("building_id,heating_kWh\nB1,12\n")
    result = result_from_output("monthly", output, example_project("monthly", "failed_run"))
    assert result["manifest"]["status"] == "failed"
    assert result["manifest"]["failed_buildings"][0]["building_id"] == "B2"
    assert result["annual"] == [{"building_id": "B1", "heating_kWh": 12.0}]
    assert set(result["details_by_building"]) == {"B1"}


def test_csv_details_keep_zone_labels_and_warning_codes(tmp_path: Path) -> None:
    project = example_project("monthly", "csv_details")

    project["inputs"]["geometry"] = {
        "format": "tabular",
        "zones": [{"zone_id": "A"}, {"zone_id": "A_B"}],
    }

    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "building_outputs": {"B1": {"details_file": "B1.csv"}},
            }
        )
    )

    (tmp_path / "B1.csv").write_text(
        "zone_id,warning_codes,zone_A_heat,zone_A_B_heat\n,first|second,1,2\n"
    )

    result = result_from_output("monthly", tmp_path, project)
    detail = result["details_by_building"]["B1"][0]
    assert detail["zone_id"] is None
    assert detail["warning_codes"] == ["first", "second"]
    assert detail["zone_values"] == {"A": {"heat": 1.0}, "A_B": {"heat": 2.0}}


def test_geojson_and_two_zone_detail(tmp_path: Path) -> None:
    source_config = json.loads((ROOT / "prototype/configs/example.json").read_text())

    project = {
        "run_id": "geojson_case",
        "schema_version": "1.0",
        "inputs": {
            "geometry": {
                "format": "geojson",
                "feature_collection": json.loads(
                    (EXAMPLES / "example_district.geojson").read_text()
                ),
            },
            "envelopes": json.loads((EXAMPLES / "archetypes.json").read_text()),
            "schedules": json.loads((EXAMPLES / "schedules.json").read_text()),
            "systems": json.loads((EXAMPLES / "systems_templates.json").read_text()),
            "calendar_year": source_config["inputs"]["calendar_year"],
            "time_steps_per_hour": source_config["inputs"]["time_steps_per_hour"],
            "azimuth_subdivisions": source_config["inputs"]["azimuth_subdivisions"],
        },
        "operating": source_config["operating"],
    }

    with TestClient(create_app(tmp_path)) as client:
        response = send(client, "monthly", project)

    assert response.status_code == 200, response.text[:1000]
    result = response.json()
    assert_contract("monthly", result)
    assert len(result["annual"]) == 5
    assert len(result["monthly"]) == 60
    assert result["details_by_building"]["1"][0]["zone_values"].keys() == {
        "upper",
        "lower",
    }


def test_tabular_two_zone_dynamic_detail(tmp_path: Path) -> None:
    source_config = json.loads((ROOT / "prototype/configs/example_tabular.json").read_text())

    numeric_fields = {
        "n_floors",
        "height_m",
        "footprint_area_m2",
        "net_floor_area_m2",
        "volume_m3",
        "surface_index",
        "area_m2",
        "azimuth_deg",
        "tilt_deg",
    }

    tables = {}

    for name in ("buildings", "zones", "surfaces"):
        with (EXAMPLES / "tabular_geometry" / f"{name}.csv").open(newline="") as stream:
            rows = [row for row in csv.DictReader(stream) if row["building_id"] == "1"]
        for row in rows:
            for field in numeric_fields & row.keys():
                row[field] = float(row[field]) if "." in row[field] else int(row[field])
        tables[name] = rows

    project = {
        "run_id": "two_zone_case",
        "schema_version": "1.0",
        "inputs": {
            "geometry": {"format": "tabular", **tables},
            "envelopes": json.loads((EXAMPLES / "archetypes.json").read_text()),
            "schedules": json.loads((EXAMPLES / "schedules.json").read_text()),
            "systems": json.loads((EXAMPLES / "systems_templates.json").read_text()),
            "calendar_year": source_config["inputs"]["calendar_year"],
            "time_steps_per_hour": source_config["inputs"]["time_steps_per_hour"],
            "azimuth_subdivisions": source_config["inputs"]["azimuth_subdivisions"],
        },
        "operating": source_config["operating"],
        "dynamic": source_config["dynamic"],
    }

    with TestClient(create_app(tmp_path)) as client:
        response = send(client, "dynamic", project)

    assert response.status_code == 200, response.text[:1000]
    result = response.json()
    assert_contract("dynamic", result)
    assert result["monthly"][0]["zone_count"] == 2
    assert result["details_by_building"]["1"][0]["zone_values"].keys() == {
        "upper",
        "lower",
    }
