"""Energy bought, CO2 and cost: POST /runs/{dynamic,monthly,simplified,vbdd}/energy."""

from __future__ import annotations

from typing import TypedDict

from fastapi import FastAPI

from ..core import (
    Context,
    InputError,
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
from ..energy_config import DEFAULT_SIMPLIFIED, stage_energy
from ..project import CLI_ENGINES, validated_project, vbdd_args

TOOL = Tool("energy")
ENGINES = {**CLI_ENGINES, "vbdd": "Monthly_SS_VBDD"}
PARTS = {"project": Part("json"), "weather_epw": Part("file"), "energy": Part("json")}
TABLES = ("energy_monthly", "energy_annual", "service_monthly", "service_annual")


class EnergyMetadata(TypedDict):
    method: str


def stage(run: Run, values: RequestValues, method: str) -> Job[EnergyMetadata]:
    project = values["project"]
    staged = stage_energy(
        run.inputs, project, values["weather_epw"], values["energy"], engine=ENGINES[method]
    )
    zone_mode = project.get("simplified", DEFAULT_SIMPLIFIED)["zone_mode"]
    arguments = ["--engine", ENGINES[method], "--zone-mode", zone_mode]
    if method == "dynamic":
        arguments += ["--model", project.get("dynamic", {}).get("model", "5R1C")]
    if method == "vbdd":
        arguments += vbdd_args(project)
    command = python(
        "-m",
        "dt_prototype.energy_carriers.cli",
        "--config",
        str(staged.project_config),
        "--energy-config",
        str(staged.energy_config),
        "--output",
        str(run.results),
        *arguments,
    )
    return Job(command, {"method": method})


def reader(run: Run, meta: EnergyMetadata) -> ReadResult:
    manifest = read_manifest(run.results / "manifest.json", root=run.root)
    payload = {
        "method": meta["method"],
        "manifest": manifest,
        **{name: read_table(run.results / f"{name}.csv") for name in TABLES},
    }
    return ReadResult.reported(payload, manifest.get("status"), {"complete": 0})


def validate(values: RequestValues) -> None:
    method = values["method"]
    if method not in ENGINES:
        raise InputError(f"method must be one of {', '.join(ENGINES)}", "method")
    validated_project(method, values["project"])


def register(app: FastAPI, context: Context) -> None:
    route(
        app,
        context,
        TOOL,
        "/runs/{method}/energy",
        "runEnergy",
        PARTS,
        lambda run, values: stage(run, values, values["method"]),
        reader,
        validate=validate,
        run_id=lambda values: values["project"]["run_id"],
        invalid_code={"project": "invalid_project", "weather_epw": "invalid_weather"},
    )
