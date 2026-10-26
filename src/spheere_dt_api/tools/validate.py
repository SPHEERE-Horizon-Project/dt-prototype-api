"""Input checks without a calculation: POST /validate."""

from __future__ import annotations

from typing import Literal, TypedDict

from fastapi import FastAPI

from ..contract import validate_project
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
    read_json,
    route,
    write_json,
)
from ..inverse_config import resolve_simulation_source, stage_inverse
from ..project import write_project

TOOL = Tool("validate")
KINDS = ("project", "energy", "inverse")
PARTS = {
    "kind": Part("text"),
    "run_id": Part("text", required=False),
    "project": Part("json", required=False),
    "weather_epw": Part("file", required=False),
    "energy": Part("json", required=False),
    "config": Part("json", required=False),
    "observations": Part("file", required=False),
    "weather": Part("file", required=False),
    "energy_run_id": Part("text", required=False),
}


class ValidationMetadata(TypedDict):
    kind: Literal["project", "energy", "inverse"]


def _require(values: RequestValues, *names: str) -> None:
    for name in names:
        if name not in values:
            raise InputError(f"kind={values['kind']} needs the {name} part", name)


def register(app: FastAPI, context: Context) -> None:
    def stager(run: Run, values: RequestValues) -> Job[ValidationMetadata]:
        kind = values["kind"]
        if kind not in KINDS:
            raise InputError(f"kind must be one of {', '.join(KINDS)}", "kind")
        if kind == "project":
            _require(values, "project", "weather_epw")
            # Only the shape is checked here; DT Prototype's preflight reports the rest.
            error = validate_project("monthly", {"run_id": run.run_id, **values["project"]})
            if error is not None:
                raise InputError(error[1], error[0])
            config = write_project(run.inputs, values["project"], values["weather_epw"])
        elif kind == "energy":
            _require(values, "energy")
            config = run.inputs / "energy.json"
            write_json(config, values["energy"])
        else:
            _require(values, "config")
            simulation = resolve_simulation_source(
                context, values["config"], energy_run_id=values.get("energy_run_id")
            )
            staged = stage_inverse(
                context,
                run.inputs,
                values["config"],
                observations=values.get("observations"),
                weather=values.get("weather"),
                simulation=simulation,
            )
            config = staged.path
        command = python(
            "-m",
            "dt_prototype.validation",
            "--config",
            str(config),
            "--kind",
            kind,
            "--report",
            str(run.results / "report.json"),
        )
        return Job(command, {"kind": kind})

    def reader(run: Run, meta: ValidationMetadata) -> ReadResult:
        report = read_json(run.results / "report.json", run.root)
        report.pop("configuration", None)
        return ReadResult.reported(report, report.get("status"), {"passed": 0, "failed": 1})

    route(app, context, TOOL, "/validate", "validateInputs", PARTS, stager, reader)
