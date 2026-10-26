"""Standalone life-cycle calculators: POST /lcc, /lca and /circularity.

DT Prototype keeps these in `to_be_integrated/`, outside the installed package, each
with its own runner script that puts its source folder on the import path.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI

from ..core import (
    PROTOTYPE,
    Context,
    InputError,
    Job,
    Part,
    Run,
    Tool,
    python,
    read_json,
    read_manifest,
    read_table,
    route,
    write_json,
)

FOLDER = PROTOTYPE / "to_be_integrated"


@dataclass(frozen=True)
class Calculator:
    tool: Tool
    path: str
    operation_id: str
    runner: str
    details: dict[str, str]


CALCULATORS = (
    Calculator(
        Tool("lcc"),
        "/lcc",
        "runLcc",
        "lcc/run_lcc.py",
        {"component": "technology_costs.csv", "building": "technology_costs.csv"},
    ),
    Calculator(
        Tool("lca"),
        "/lca",
        "runLca",
        "lca/run_lca.py",
        {"component": "technology_impacts.csv", "building": "technology_impacts.csv"},
    ),
    Calculator(
        Tool("circularity"),
        "/circularity",
        "runCircularity",
        "circularity/run_circularity.py",
        {"component": "material_mci.csv", "building": "component_mci.csv"},
    ),
)
MODES = ("component", "building")


def _parts(calculator: Calculator) -> dict[str, Part]:
    parts = {"run_id": Part("text", required=False), "case": Part("json")}
    if calculator.tool.name == "lca":
        parts["indicator_catalog"] = Part("json", required=False)
    if calculator.tool.name == "circularity":
        parts["mode"] = Part("text")
    return parts


def _stager(calculator: Calculator):
    def stager(run: Run, values: dict) -> Job:
        case = run.inputs / "case.json"
        write_json(case, values["case"])
        arguments = ["--input", str(case), "--output", str(run.results)]
        mode = values.get("mode", "building")
        if calculator.tool.name == "circularity":
            if mode not in MODES:
                raise InputError(f"mode must be one of {', '.join(MODES)}", "mode")
            arguments += ["--mode", mode]
        if "indicator_catalog" in values:
            catalog = run.inputs / "indicator_catalog.json"
            write_json(catalog, values["indicator_catalog"])
            arguments += ["--indicator-catalog", str(catalog)]
        return Job(python(str(FOLDER / calculator.runner), *arguments), {"mode": mode})

    return stager


def _reader(calculator: Calculator):
    def reader(run: Run, meta: dict) -> dict:
        return {
            "manifest": read_manifest(run.results / "manifest.json", root=run.root),
            "results": read_json(run.results / "results.json", run.root),
            "details": read_table(run.results / calculator.details[meta.get("mode", "building")]),
        }

    return reader


def register(app: FastAPI, context: Context) -> None:
    for calculator in CALCULATORS:
        route(
            app,
            context,
            calculator.tool,
            calculator.path,
            calculator.operation_id,
            _parts(calculator),
            _stager(calculator),
            _reader(calculator),
        )
