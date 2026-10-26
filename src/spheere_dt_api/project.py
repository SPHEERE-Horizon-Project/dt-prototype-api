"""Project staging shared by every tool that takes a building project."""

from __future__ import annotations

import csv
from pathlib import Path

from .contract import validate_project
from .core import RUN_ID_MESSAGE, InputError, valid_run_id, write_json

# Public method names and the DT Prototype CLI engine each one runs.
CLI_ENGINES = {
    "dynamic": "Dynamic_RC",
    "monthly": "Monthly_SS",
    "simplified": "Monthly_SS_simplified",
}
PUBLIC_ENGINES = {cli: public for public, cli in CLI_ENGINES.items()}
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
        "boundary_condition",
    ),
}
# Project `vbdd` settings and the CLI flag each one sets.
VBDD_FLAGS = {
    "utilisation": "--utilisation",
    "solar": "--solar",
    "eta_heating": "--eta-heating",
    "eta_cooling": "--eta-cooling",
    "attenuation_heating": "--attenuation-heating",
    "attenuation_cooling": "--attenuation-cooling",
}


def validated_project(engine: str, project: object) -> dict:
    """Return a project that matches the engine's schema and has a safe run ID."""
    error = validate_project(engine, project)
    if error is not None:
        field, message = error
        raise InputError(message, field, code="invalid_project")
    if not valid_run_id(project["run_id"]):
        raise InputError(RUN_ID_MESSAGE, "run_id", code="invalid_project")
    return project


def _write_geometry(directory: Path, geometry: dict) -> str:
    """Write geometry files and return their path relative to the run directory."""
    if geometry["format"] == "geojson":
        write_json(directory / "geometry.geojson", geometry["feature_collection"])
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


def write_project(directory: Path, project: dict, weather: bytes) -> Path:
    """Write a project's files into a run folder and return the config path."""
    inputs = project["inputs"]
    geometry_path = _write_geometry(directory, inputs["geometry"])
    for name in ("envelopes", "schedules", "systems"):
        write_json(directory / f"{name}.json", inputs[name])
    (directory / "weather.epw").write_bytes(weather)
    config_path = directory / "config.json"
    write_json(config_path, _source_config(project, geometry_path))
    return config_path


def stage_project(directory: Path, project: dict, weather: bytes) -> tuple[Path, object]:
    """Write the project files and check that DT Prototype accepts them.

    Returns the config path and the preprocessed district. Every tool that takes a
    project (thermal, energy, VBDD, asset quantities, pipeline) stages it this way.
    """
    from dt_prototype.common.project import ProjectInputs

    config_path = write_project(directory, project, weather)
    try:
        district = ProjectInputs.load(config_path).preprocess()
    except Exception as exc:
        message = str(exc)
        if "EPW" in message.upper():
            raise InputError(message, "weather_epw", code="invalid_weather") from exc
        raise InputError(message, "project", code="invalid_project") from exc
    return config_path, district


def vbdd_args(project: dict) -> list[str]:
    """Turn the project's optional `vbdd` settings into CLI arguments."""
    options = project.get("vbdd", {})
    return [
        arg
        for key, flag in VBDD_FLAGS.items()
        if key in options
        for arg in (flag, str(options[key]))
    ]


GEOMETRY_SCHEMAS = {"buildings": "BuildingRow", "zones": "ZoneRow", "surfaces": "SurfaceRow"}


def read_geometry(directory: Path) -> dict:
    """Read buildings/zones/surfaces CSVs as tabular geometry ready for a project."""
    from .contract import openapi_spec

    schemas = openapi_spec()["components"]["schemas"]
    geometry: dict[str, object] = {"format": "tabular"}
    for name, schema_name in GEOMETRY_SCHEMAS.items():
        properties = schemas[schema_name]["properties"]
        with (directory / f"{name}.csv").open(encoding="utf-8-sig", newline="") as stream:
            geometry[name] = [
                {
                    key: _typed(value, properties.get(key, {}).get("type"))
                    for key, value in row.items()
                    if value != "" or properties.get(key, {}).get("type") == "string"
                }
                for row in csv.DictReader(stream)
            ]
    return geometry


def _typed(value: str, declared: object) -> object:
    if declared == "integer":
        return int(float(value))
    if declared == "number":
        return float(value)
    return value
