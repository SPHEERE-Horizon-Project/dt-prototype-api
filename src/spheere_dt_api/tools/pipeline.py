"""Energy, assessment and inverse models in one call: POST /pipeline.

The pipeline JSON follows the DT Prototype format. Its file-path fields are filled
in by the API from the request parts, and it always runs in the background.
"""

from __future__ import annotations

import copy

from dt_prototype.pipeline import load_configuration
from fastapi import FastAPI

from ..core import (
    Context,
    EmptyMetadata,
    ExecutionPolicy,
    InputError,
    Job,
    Part,
    ReadResult,
    RequestValues,
    Run,
    Tool,
    check_dt_prototype_schema,
    python,
    read_manifest,
    read_table,
    route,
    write_json,
)
from ..energy_config import stage_energy
from ..inverse_config import SimulationSource, resolve_simulation_source, stage_inverse
from ..project import validated_project

TOOL = Tool("pipeline", timeout_s=7200)
PARTS = {
    "run_id": Part("text", required=False),
    "pipeline": Part("json"),
    "project": Part("json", required=False),
    "weather_epw": Part("file", required=False),
    "energy": Part("json", required=False),
    "energy_run_id": Part("text", required=False),
    "asset_results": Part("file", required=False),
    "asset_quantities": Part("file", required=False),
    "inverse_config": Part("json", required=False),
    "observations": Part("file", required=False),
    "weather": Part("file", required=False),
}
STAGE_TABLES = {
    "energy": ("energy_monthly", "energy_annual", "service_monthly", "service_annual"),
    "assessment": (
        "validated_asset_results",
        "building_asset_results",
        "building_operational_results",
    ),
    "inverse": ("models", "metrics", "comparison_metrics", "monthly_predictions"),
}


def _require(values: RequestValues, *names: str) -> None:
    for name in names:
        if name not in values:
            raise InputError(f"This pipeline needs the {name} part", name)


def register(app: FastAPI, context: Context) -> None:
    def stage_forward(run: Run, values: RequestValues, pipeline: dict) -> None:
        _require(values, "project", "weather_epw", "energy")
        validated_project("monthly", {"run_id": run.run_id, **values["project"]})
        settings = pipeline.setdefault("energy", {})
        staged = stage_energy(
            run.inputs,
            values["project"],
            values["weather_epw"],
            values["energy"],
            engine=None if settings.get("mode") == "reuse" else settings.get("engine", "all"),
        )
        pipeline["project_config"] = str(staged.project_config)
        pipeline["energy_config"] = str(staged.energy_config)
        if settings.get("mode") == "reuse":
            _require(values, "energy_run_id")
            earlier = context.completed(values["energy_run_id"], {"energy"}, "energy_run_id")
            settings["results"] = str(earlier.results)
        else:
            settings.pop("results", None)
        assessment = pipeline.get("assessment", {})
        if assessment.get("enabled"):
            _require(values, "asset_results")
            (run.inputs / "asset_results.csv").write_bytes(values["asset_results"])
            assessment["asset_results"] = str(run.inputs / "asset_results.csv")
            if "asset_quantities" in values:
                (run.inputs / "asset_quantities.csv").write_bytes(values["asset_quantities"])
                assessment["resolved_quantities"] = str(run.inputs / "asset_quantities.csv")
        analysis = pipeline.get("analysis", {})
        if analysis.get("enabled"):
            _require(values, "inverse_config")
            # Forward analysis reads the energy results this same pipeline writes.
            analysis["config"] = str(
                stage_inverse(
                    context,
                    run.inputs,
                    values["inverse_config"],
                    simulation=SimulationSource(run.results / "energy", staged.project_config),
                    field="inverse_config",
                ).path
            )

    def stager(run: Run, values: RequestValues) -> Job[EmptyMetadata]:
        pipeline = values["pipeline"]
        if not isinstance(pipeline, dict):
            raise InputError("The pipeline part must be a JSON object", "pipeline")
        pipeline = copy.deepcopy(pipeline)
        for section in ("energy", "assessment", "analysis"):
            if section in pipeline and not isinstance(pipeline[section], dict):
                raise InputError(f"pipeline.{section} must be an object", "pipeline")
        if pipeline.get("mode") == "inverse":
            _require(values, "inverse_config")
            simulation = resolve_simulation_source(
                context,
                values["inverse_config"],
                energy_run_id=values.get("energy_run_id"),
                field="inverse_config",
            )
            pipeline["inverse_config"] = str(
                stage_inverse(
                    context,
                    run.inputs,
                    values["inverse_config"],
                    observations=values.get("observations"),
                    weather=values.get("weather"),
                    simulation=simulation,
                    field="inverse_config",
                ).path
            )
        else:
            stage_forward(run, values, pipeline)
        check_dt_prototype_schema("pipeline", pipeline, "pipeline")
        path = run.inputs / "pipeline.json"
        write_json(path, pipeline)
        try:
            load_configuration(path)
        except (ValueError, KeyError, TypeError) as exc:
            raise InputError(str(exc), "pipeline") from exc
        command = python(
            "-m", "dt_prototype.pipeline", "--config", str(path), "--output", str(run.results)
        )
        return Job(command, {}, ExecutionPolicy("slow", True))

    def reader(run: Run, meta: EmptyMetadata) -> ReadResult:
        result = {"manifest": read_manifest(run.results / "manifest.json", root=run.root)}
        for stage, tables in STAGE_TABLES.items():
            folder = run.results / stage
            if folder.is_dir():
                result[stage] = {name: read_table(folder / f"{name}.csv") for name in tables}
        return ReadResult.reported(
            result,
            result["manifest"].get("status"),
            {"complete": 0, "failed": 1, "partial": 2, "incomplete": 2},
        )

    route(
        app,
        context,
        TOOL,
        "/pipeline",
        "runPipeline",
        PARTS,
        stager,
        reader,
    )
