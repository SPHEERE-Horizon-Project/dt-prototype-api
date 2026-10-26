"""Models learned from meter data: POST /inverse and POST /inverse/acceptance."""

from __future__ import annotations

from fastapi import FastAPI

from ..core import (
    Context,
    EmptyMetadata,
    ExecutionPolicy,
    Job,
    Part,
    ReadResult,
    RequestValues,
    Run,
    Tool,
    python,
    read_json,
    read_manifest,
    read_table,
    route,
    server_paths_removed,
    write_json,
)
from ..inverse_config import resolve_simulation_source, stage_inverse

TOOL = Tool("inverse", timeout_s=2400)
ACCEPTANCE = Tool("acceptance")
PARTS = {
    "run_id": Part("text", required=False),
    "config": Part("json"),
    "observations": Part("file", required=False),
    "weather": Part("file", required=False),
    "energy_run_id": Part("text", required=False),
    "thermal_run_id": Part("text", required=False),
    "model_run_id": Part("text", required=False),
}
ACCEPTANCE_PARTS = {
    "run_id": Part("text", required=False),
    "inverse_run_id": Part("text"),
    "policy": Part("json"),
}
TABLES = {
    "models": "models.csv",
    "metrics": "metrics.csv",
    "comparison_metrics": "comparison_metrics.csv",
    "monthly_predictions": "monthly_predictions.csv",
    "predictions": "predictions.csv",
}


def register(app: FastAPI, context: Context) -> None:
    def stager(run: Run, values: RequestValues) -> Job[EmptyMetadata]:
        simulation = resolve_simulation_source(
            context,
            values["config"],
            energy_run_id=values.get("energy_run_id"),
            thermal_run_id=values.get("thermal_run_id"),
        )
        model_dir = None
        if "model_run_id" in values:
            model_dir = context.completed(
                values["model_run_id"], {"inverse"}, "model_run_id"
            ).results
        config = stage_inverse(
            context,
            run.inputs,
            values["config"],
            observations=values.get("observations"),
            weather=values.get("weather"),
            simulation=simulation,
            model_dir=model_dir,
        )
        command = python(
            "-m",
            "dt_prototype.inverse_models.cli",
            "--config",
            str(config.path),
            "--output",
            str(run.results),
        )
        policy = ExecutionPolicy("slow", True) if config.needs_opendsm else ExecutionPolicy()
        return Job(command, {}, policy)

    def reader(run: Run, meta: EmptyMetadata) -> ReadResult:
        manifest = read_manifest(run.results / "manifest.json", root=run.root)
        payload = {
            "manifest": manifest,
            "model_index": read_json(run.results / "model_index.json", run.root),
            # Worker errors in these tables name server paths; make them run-relative.
            **{
                key: server_paths_removed(read_table(run.results / name), run.root)
                for key, name in TABLES.items()
            },
        }
        return ReadResult.reported(
            payload,
            manifest.get("status"),
            {"complete": 0, "failed": 1, "partial": 2, "incomplete": 2},
        )

    route(
        app,
        context,
        TOOL,
        "/inverse",
        "runInverse",
        PARTS,
        stager,
        reader,
    )

    def acceptance_stager(run: Run, values: RequestValues) -> Job[EmptyMetadata]:
        inverse = context.completed(values["inverse_run_id"], {"inverse"}, "inverse_run_id")
        policy = run.inputs / "policy.json"
        write_json(policy, values["policy"])
        run.results.mkdir()
        command = python(
            "-m",
            "dt_prototype.inverse_models.acceptance",
            "--results",
            str(inverse.results),
            "--policy",
            str(policy),
            "--report",
            str(run.results / "report.json"),
        )
        return Job(command, {})

    def acceptance_reader(run: Run, meta: EmptyMetadata) -> ReadResult:
        report = read_json(run.results / "report.json", run.root)
        report.pop("run", None)
        return ReadResult.reported(
            report, report.get("status"), {"accepted": 0, "review_required": 2}
        )

    route(
        app,
        context,
        ACCEPTANCE,
        "/inverse/acceptance",
        "checkInverseAcceptance",
        ACCEPTANCE_PARTS,
        acceptance_stager,
        acceptance_reader,
    )
