"""Assemble the API from independent tool modules plus the shared run endpoints."""

from __future__ import annotations

import importlib
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from .contract import openapi_spec
from .core import Context, InputError, RunnerError, problem, valid_run_id

# Each module registers its own routes and imports DT Prototype code only when a
# request arrives, so one tool's DT Prototype code cannot stop the others from loading.
TOOLS = (
    "thermal",
    "vbdd",
    "energy",
    "validate",
    "footprints",
    "quantities",
    "assessment",
    "calculators",
    "inverse",
    "pipeline",
)


def create_app(runs_root: Path | None = None, environ: dict[str, str] | None = None) -> FastAPI:
    """Create the API with its run directory, tools and run-status routes."""
    root = Path(runs_root or os.environ.get("DT_API_RUNS_ROOT", ".runs")).resolve()
    context = Context(root, environ)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        context.shutdown()

    application = FastAPI(
        title="DT Prototype API", version=openapi_spec()["info"]["version"], lifespan=lifespan
    )
    application.openapi = openapi_spec
    application.state.context = context
    for name in TOOLS:
        importlib.import_module(f".tools.{name}", __package__).register(application, context)

    def existing_run(run_id: str):
        if not valid_run_id(run_id):
            return None
        run = context.run(run_id)
        return run if run.status() is not None else None

    @application.get("/runs/{run_id}", operation_id="getRun")
    async def get_run(run_id: str) -> JSONResponse:
        """Report a run's status and, once it is complete, its result."""
        run = existing_run(run_id)
        if run is None:
            return problem(404, "run_not_found", f"No run named {run_id}", "run_id")
        record = run.status()
        body = {
            key: record[key]
            for key in (
                "run_id",
                "tool",
                "status",
                "created_utc",
                "started_utc",
                "finished_utc",
                "error",
            )
            if key in record
        }
        reader = context.readers.get(record.get("tool", ""))
        if record.get("status") == "complete" and reader is not None:
            try:
                body["result"] = {"run_id": run.run_id, **reader(run, record.get("meta", {}))}
            except (InputError, RunnerError, OSError, ValueError, KeyError) as exc:
                return problem(500, "result_unreadable", str(exc))
        return JSONResponse(body)

    @application.get("/runs/{run_id}/files", operation_id="listRunFiles")
    async def list_files(run_id: str) -> JSONResponse:
        """List every output file of a run, relative to its output folder."""
        run = existing_run(run_id)
        if run is None:
            return problem(404, "run_not_found", f"No run named {run_id}", "run_id")
        files = (
            sorted(
                path.relative_to(run.results).as_posix()
                for path in run.results.rglob("*")
                if path.is_file()
            )
            if run.results.is_dir()
            else []
        )
        return JSONResponse({"run_id": run_id, "files": files})

    @application.get("/runs/{run_id}/files/{path:path}", operation_id="getRunFile")
    async def get_file(run_id: str, path: str):
        """Download one output file of a run."""
        run = existing_run(run_id)
        if run is None:
            return problem(404, "run_not_found", f"No run named {run_id}", "run_id")
        target = (run.results / path).resolve()
        if not target.is_relative_to(run.results.resolve()) or not target.is_file():
            return problem(404, "file_not_found", f"No output file {path} in run {run_id}", "path")
        return FileResponse(target)

    return application


app = create_app()
