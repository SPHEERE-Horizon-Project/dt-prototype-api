"""Asset quantities for cost and impact work: POST /assets/quantities."""

from __future__ import annotations

from fastapi import FastAPI

from ..core import (
    Context,
    InputError,
    Job,
    Part,
    Run,
    Tool,
    python,
    read_manifest,
    read_table,
    route,
    write_json,
)
from ..project import stage_project, validated_project

TOOL = Tool("quantities")
PARTS = {
    "run_id": Part("text", required=False),
    "inputs": Part("file"),
    "catalogue": Part("json"),
    "project": Part("json", required=False),
    "weather_epw": Part("file", required=False),
}
XLSX_SIGNATURE = b"PK\x03\x04"


def stager(run: Run, values: dict) -> Job:
    # The fillable workbook is a ZIP container; anything else is read as JSON.
    raw = values["inputs"]
    inputs = run.inputs / ("inputs.xlsx" if raw.startswith(XLSX_SIGNATURE) else "inputs.json")
    inputs.write_bytes(raw)
    catalogue = run.inputs / "catalogue.json"
    write_json(catalogue, values["catalogue"])
    arguments = []
    if "project" in values:
        if "weather_epw" not in values:
            raise InputError("A project needs the weather_epw file", "weather_epw")
        project = {"run_id": run.run_id, **values["project"]}
        validated_project("monthly", project)
        config, _ = stage_project(run.inputs, project, values["weather_epw"])
        arguments = ["--config", str(config)]
    command = python(
        "-m",
        "dt_prototype.assessment.quantity_cli",
        "--inputs",
        str(inputs),
        "--catalogue",
        str(catalogue),
        "--output",
        str(run.results),
        *arguments,
    )
    return Job(command)


def reader(run: Run, meta: dict) -> dict:
    return {
        "manifest": read_manifest(run.results / "manifest.json", root=run.root),
        "quantities": read_table(run.results / "resolved_asset_quantities.csv"),
    }


def register(app: FastAPI, context: Context) -> None:
    route(app, context, TOOL, "/assets/quantities", "resolveAssetQuantities", PARTS, stager, reader)
