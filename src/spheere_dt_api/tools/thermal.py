"""Heat-demand methods: POST /runs/dynamic, /runs/monthly and /runs/simplified."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from fastapi import FastAPI

from ..contract import openapi_spec
from ..core import Context, Job, Part, Run, RunnerError, Tool, python, read_manifest, route
from ..project import CLI_ENGINES, PUBLIC_ENGINES, stage_project, validated_project

TOOL = Tool("thermal")
PARTS = {"project": Part("json"), "weather_epw": Part("file")}
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
RESULT_SCHEMAS = {
    "dynamic": "DynamicStep",
    "monthly": "MonthlyDetail",
    "simplified": "SimplifiedDetail",
}


def zone_labels(project: dict) -> list[str]:
    """Zone labels that may prefix detail columns, longest first."""
    geometry = project["inputs"]["geometry"]
    labels = (
        {str(row["zone_id"]) for row in geometry["zones"]}
        if geometry["format"] == "tabular"
        else {"single", "upper", "lower"}
    )
    return sorted(labels, key=len, reverse=True)


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
    if name in {"engine", "engine_id"}:
        return PUBLIC_ENGINES.get(value, value)
    declared_type = properties.get(name, {}).get("type")
    if declared_type is not None:
        return _scalar(value, declared_type)
    try:
        return _scalar(value, "number")
    except ValueError:
        return value


def _row_from_csv(row: dict[str, str], schema_name: str, labels: list[str]) -> dict:
    """Convert a CSV row to API fields, including any zone values."""
    properties = openapi_spec()["components"]["schemas"][schema_name]["properties"]
    result: dict[str, object] = {}
    zone_values: dict[str, dict[str, object]] = {}
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


def _read_csv(path: Path, schema_name: str, labels: list[str] | None = None) -> list[dict]:
    """Read typed result rows, or return an empty list if the file is absent."""
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return [_row_from_csv(row, schema_name, labels or []) for row in csv.DictReader(stream)]


def _read_details(output_path: Path, manifest: dict, schema_name: str, labels: list[str]) -> dict:
    """Read each building's detail CSV listed in the manifest."""
    details: dict[str, list[dict]] = {}
    for building_id, record in manifest["building_outputs"].items():
        filename = record["details_file"]
        if Path(filename).name != filename:
            raise RunnerError("Invalid detail filename in runner manifest")
        detail_path = output_path / filename
        if detail_path.is_file():
            details[building_id] = _read_csv(detail_path, schema_name, labels)
    return details


def result_from_output(engine: str, output_path: Path, labels: list[str]) -> dict:
    """Read the runner's files and assemble the API response."""
    source = read_manifest(output_path / "manifest.json", {"complete", "failed"})
    manifest = {key: source[key] for key in MANIFEST_FIELDS if key in source}
    if "engine" in manifest:
        manifest["engine"] = PUBLIC_ENGINES.get(manifest["engine"], manifest["engine"])
    return {
        "manifest": manifest,
        "monthly": _read_csv(output_path / "monthly.csv", "MonthlyTotal"),
        "annual": _read_csv(output_path / "annual.csv", "AnnualTotal"),
        "details_by_building": _read_details(output_path, manifest, RESULT_SCHEMAS[engine], labels),
    }


def register(app: FastAPI, context: Context) -> None:
    for engine, cli_engine in CLI_ENGINES.items():

        def stager(
            run: Run, values: dict, engine: str = engine, cli_engine: str = cli_engine
        ) -> Job:
            project = values["project"]
            config, _ = stage_project(run.inputs, project, values["weather_epw"])
            command = python(
                "-m",
                "dt_prototype",
                cli_engine,
                "--config",
                str(config),
                "--output",
                str(run.results),
            )
            return Job(command, {"engine": engine, "zone_labels": zone_labels(project)})

        def reader(run: Run, meta: dict) -> dict:
            return result_from_output(meta["engine"], run.results, meta["zone_labels"])

        route(
            app,
            context,
            TOOL,
            f"/runs/{engine}",
            f"run{engine.title()}",
            PARTS,
            stager,
            reader,
            run_id=lambda values, engine=engine: validated_project(engine, values["project"])[
                "run_id"
            ],
            invalid_code={"project": "invalid_project", "weather_epw": "invalid_weather"},
        )
