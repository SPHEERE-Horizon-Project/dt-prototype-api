"""Models learned from meter data: POST /inverse and POST /inverse/acceptance."""

from __future__ import annotations

from fastapi import FastAPI

from ..core import (
    Context,
    Job,
    Part,
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
from ..inverse_config import stage_inverse, uses_opendsm

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
    def stager(run: Run, values: dict) -> Job:
        simulation = None
        for field, tools in (("energy_run_id", {"energy"}), ("thermal_run_id", {"thermal"})):
            if field in values:
                earlier = context.completed(values[field], tools, field)
                simulation = (earlier.results, earlier.inputs / "config.json")
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
            str(config),
            "--output",
            str(run.results),
        )
        return Job(command)

    def reader(run: Run, meta: dict) -> dict:
        return {
            "manifest": read_manifest(run.results / "manifest.json", root=run.root),
            "model_index": read_json(run.results / "model_index.json", run.root),
            # Worker errors in these tables name server paths; make them run-relative.
            **{
                key: server_paths_removed(read_table(run.results / name), run.root)
                for key, name in TABLES.items()
            },
        }

    route(
        app,
        context,
        TOOL,
        "/inverse",
        "runInverse",
        PARTS,
        stager,
        reader,
        background=lambda values: uses_opendsm(values.get("config") or {}),
    )

    def acceptance_stager(run: Run, values: dict) -> Job:
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
        return Job(command)

    def acceptance_reader(run: Run, meta: dict) -> dict:
        report = read_json(run.results / "report.json", run.root)
        report.pop("run", None)
        return report

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
