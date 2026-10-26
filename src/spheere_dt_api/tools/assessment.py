"""Cost, impact and circularity totals per building: POST /assessment."""

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
)

TOOL = Tool("assessment")
PARTS = {
    "run_id": Part("text", required=False),
    "asset_results": Part("file"),
    "energy_run_id": Part("text", required=False),
    "asset_quantities": Part("file", required=False),
    "quantities_run_id": Part("text", required=False),
}
TABLES = {
    "asset_results": "validated_asset_results.csv",
    "building_assets": "building_asset_results.csv",
    "building_operation": "building_operational_results.csv",
}


def register(app: FastAPI, context: Context) -> None:
    def stager(run: Run, values: dict) -> Job:
        results = run.inputs / "asset_results.csv"
        results.write_bytes(values["asset_results"])
        arguments = []
        if "energy_run_id" in values:
            energy = context.completed(values["energy_run_id"], {"energy"}, "energy_run_id")
            arguments += ["--energy-results", str(energy.results)]
        if "asset_quantities" in values and "quantities_run_id" in values:
            raise InputError(
                "Send asset_quantities or quantities_run_id, not both", "quantities_run_id"
            )
        if "asset_quantities" in values:
            quantities = run.inputs / "asset_quantities.csv"
            quantities.write_bytes(values["asset_quantities"])
            arguments += ["--asset-quantities", str(quantities)]
        if "quantities_run_id" in values:
            earlier = context.completed(
                values["quantities_run_id"], {"quantities"}, "quantities_run_id"
            )
            arguments += [
                "--asset-quantities",
                str(earlier.results / "resolved_asset_quantities.csv"),
            ]
        command = python(
            "-m",
            "dt_prototype.assessment.cli",
            "--asset-results",
            str(results),
            "--output",
            str(run.results),
            *arguments,
        )
        return Job(command)

    def reader(run: Run, meta: dict) -> dict:
        return {
            "manifest": read_manifest(run.results / "manifest.json", root=run.root),
            **{key: read_table(run.results / name) for key, name in TABLES.items()},
        }

    route(app, context, TOOL, "/assessment", "runAssessment", PARTS, stager, reader)
