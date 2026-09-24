"""Prepare CLI inputs and turn prototype output into API responses."""

from __future__ import annotations

import csv
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

from dt_prototype.common.project import ProjectInputs

from .contract import openapi_spec

RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
RESERVED_IDS = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
TABLE_FIELDS = {
    "buildings": (
        "building_id",
        "building_name",
        "envelope",
        "heating_system",
        "cooling_system",
        "solar_technologies",
        "n_floors",
        "height_m",
        "footprint_area_m2",
    ),
    "zones": (
        "building_id",
        "zone_id",
        "zone_name",
        "end_use",
        "n_floors",
        "net_floor_area_m2",
        "volume_m3",
    ),
    "surfaces": (
        "building_id",
        "zone_id",
        "surface_index",
        "surface_type",
        "area_m2",
        "azimuth_deg",
        "tilt_deg",
    ),
}
MANIFEST_FIELDS = (
    "name",
    "version",
    "engine",
    "status",
    "timestamp_utc",
    "input_hashes",
    "building_outputs",
    "failed_buildings",
    "resolved_engine_config",
    "zone_mode",
    "comparison_mode",
)


def valid_run_id(run_id: object) -> bool:
    """Check whether a run ID is safe to use as a directory name."""
    return (
        isinstance(run_id, str)
        and RUN_ID_PATTERN.fullmatch(run_id) is not None
        and run_id.upper() not in RESERVED_IDS
    )


def _write_json(path: Path, value: object) -> None:
    """Write a JSON value to a UTF-8 file."""
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _write_geometry(directory: Path, geometry: dict) -> str:
    """Write geometry files and return their path relative to the run directory."""
    if geometry["format"] == "geojson":
        _write_json(directory / "geometry.geojson", geometry["feature_collection"])
        return "geometry.geojson"
    table_dir = directory / "geometry"
    table_dir.mkdir()
    for name, fields in TABLE_FIELDS.items():
        with (table_dir / f"{name}.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(geometry[name])
    return "geometry"


def _source_config(project: dict, geometry_path: str) -> dict:
    """Build the file-based configuration expected by the CLI."""
    inputs = project["inputs"]
    return {
        "schema_version": project["schema_version"],
        "inputs": {
            "geometry": geometry_path,
            "geometry_format": inputs["geometry"]["format"],
            "weather_epw": "weather.epw",
            "envelopes": "envelopes.json",
            "schedules": "schedules.json",
            "systems": "systems.json",
            "calendar_year": inputs["calendar_year"],
            "time_steps_per_hour": inputs["time_steps_per_hour"],
            "azimuth_subdivisions": inputs["azimuth_subdivisions"],
        },
        "operating": project["operating"],
        "dynamic": project.get("dynamic", {"model": "5R1C"}),
        "simplified": project.get(
            "simplified", {"comparison_mode": "seasonal_ahu", "zone_mode": "sum"}
        ),
    }


def stage_project(directory: Path, project: dict, weather: bytes) -> Path:
    """Write and check the files needed to run a project through the CLI."""
    directory.mkdir(parents=True, exist_ok=False)
    try:
        inputs = project["inputs"]
        geometry_path = _write_geometry(directory, inputs["geometry"])
        for name in ("envelopes", "schedules", "systems"):
            _write_json(directory / f"{name}.json", inputs[name])
        (directory / "weather.epw").write_bytes(weather)
        config_path = directory / "config.json"
        _write_json(config_path, _source_config(project, geometry_path))
        source_project = ProjectInputs.load(config_path)
        source_project.preprocess()
        return config_path
    except Exception:
        shutil.rmtree(directory)
        raise


def run_cli(engine: str, config_path: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
    """Run one prototype engine and capture its process result."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "dt_prototype",
            engine,
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _scalar(value: str, declared_type: str | list[str] | None) -> object:
    """Convert a CSV cell to the type declared by the API schema."""
    types = declared_type if isinstance(declared_type, list) else [declared_type]
    if value == "":
        return None if "null" in types or "number" in types or "integer" in types else ""
    if "integer" in types:
        return int(float(value))
    if "number" in types:
        number = float(value)
        return number if math.isfinite(number) else None
    return value


def _zone_column(name: str, labels: list[str]) -> tuple[str, str] | None:
    """Find a zone label and field name in a CSV column."""
    for label in labels:
        prefix = f"zone_{label}_"
        if name.startswith(prefix):
            return label, name[len(prefix) :]
    return None


def _csv_field(name: str, value: str, properties: dict) -> object:
    """Convert a non-zone CSV field to its API value."""
    if name == "warning_codes":
        return value.split("|") if value else []
    if name == "zone_id" and not value:
        return None
    declared_type = properties.get(name, {}).get("type")
    if declared_type is not None:
        return _scalar(value, declared_type)
    try:
        return _scalar(value, "number")
    except ValueError:
        return value


def _row_from_csv(row: dict[str, str], schema_name: str, zone_labels: set[str]) -> dict:
    """Convert a CSV row to API fields, including any zone values."""
    properties = openapi_spec()["components"]["schemas"][schema_name]["properties"]
    result: dict[str, object] = {}
    zone_values: dict[str, dict[str, object]] = {}
    labels = sorted(zone_labels, key=len, reverse=True)
    for name, value in row.items():
        if value is None:
            value = ""
        zone = _zone_column(name, labels)
        if zone is not None:
            label, field = zone
            zone_values.setdefault(label, {})[field] = _scalar(value, "number")
            continue
        result[name] = _csv_field(name, value, properties)
    if zone_values:
        result["zone_values"] = zone_values
    return result


def _read_csv(path: Path, schema_name: str, zone_labels: set[str] | None = None) -> list[dict]:
    """Read typed result rows, or return an empty list if the file is absent."""
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return [
            _row_from_csv(row, schema_name, zone_labels or set()) for row in csv.DictReader(stream)
        ]


def _read_manifest(output_path: Path) -> dict:
    """Read the runner manifest and keep the fields exposed by the API."""
    manifest_path = output_path / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("The runner produced no manifest")
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("status") not in {"complete", "failed"}:
        raise ValueError("The runner did not finish")
    return {key: source_manifest[key] for key in MANIFEST_FIELDS if key in source_manifest}


def _read_details(
    output_path: Path, manifest: dict, schema_name: str, zone_labels: set[str]
) -> dict:
    """Read each building's detail CSV listed in the manifest."""
    details: dict[str, list[dict]] = {}
    for building_id, record in manifest["building_outputs"].items():
        filename = record["details_file"]
        if Path(filename).name != filename:
            raise ValueError("Invalid detail filename in runner manifest")
        detail_path = output_path / filename
        if detail_path.is_file():
            details[building_id] = _read_csv(detail_path, schema_name, zone_labels)
    return details


def result_from_output(engine: str, output_path: Path, project: dict) -> dict:
    """Read the runner's files and assemble the API response."""
    manifest = _read_manifest(output_path)
    schema_name = {
        "dynamic": "DynamicStep",
        "monthly": "MonthlyDetail",
        "simplified": "SimplifiedDetail",
    }[engine]
    geometry = project["inputs"]["geometry"]
    zone_labels = (
        {str(row["zone_id"]) for row in geometry["zones"]}
        if geometry["format"] == "tabular"
        else {"single", "upper", "lower"}
    )
    return {
        "manifest": manifest,
        "monthly": _read_csv(output_path / "monthly.csv", "MonthlyTotal"),
        "annual": _read_csv(output_path / "annual.csv", "AnnualTotal"),
        "details_by_building": _read_details(output_path, manifest, schema_name, zone_labels),
    }
