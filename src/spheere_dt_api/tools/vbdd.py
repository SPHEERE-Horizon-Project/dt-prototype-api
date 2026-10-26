"""Degree-day heat-demand method: POST /runs/vbdd."""

from __future__ import annotations

from fastapi import FastAPI

from ..core import (
    Context,
    EmptyMetadata,
    Job,
    Part,
    ReadResult,
    RequestValues,
    Run,
    Tool,
    python,
    read_manifest,
    read_table,
    route,
)
from ..project import stage_project, validated_project, vbdd_args

TOOL = Tool("vbdd")
PARTS = {"project": Part("json"), "weather_epw": Part("file")}


def stager(run: Run, values: RequestValues) -> Job[EmptyMetadata]:
    project = values["project"]
    config, _ = stage_project(run.inputs, project, values["weather_epw"])
    command = python(
        "-m",
        "dt_prototype.monthly_ss_vbdd.cli",
        "--config",
        str(config),
        "--output",
        str(run.results),
        *vbdd_args(project),
    )
    return Job(command, {})


def reader(run: Run, meta: EmptyMetadata) -> ReadResult:
    manifest = read_manifest(run.results / "manifest.json", root=run.root)
    payload = {
        "manifest": manifest,
        "monthly": read_table(run.results / "monthly.csv"),
        "annual": read_table(run.results / "annual.csv"),
        "zone_sum_monthly": read_table(run.results / "independent_zone_sum_monthly.csv"),
    }
    return ReadResult.reported(payload, manifest.get("status"), {"complete": 0})


def validate(values: RequestValues) -> None:
    validated_project("vbdd", values["project"])


def register(app: FastAPI, context: Context) -> None:
    route(
        app,
        context,
        TOOL,
        "/runs/vbdd",
        "runVbdd",
        PARTS,
        stager,
        reader,
        validate=validate,
        run_id=lambda values: values["project"]["run_id"],
        invalid_code={"project": "invalid_project", "weather_epw": "invalid_weather"},
    )
