"""Handle synchronous HTTP requests for the three prototype engines."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

from .adapter import result_from_output, run_cli, stage_project, valid_run_id
from .contract import openapi_spec, validate_project


def _problem(status: int, code: str, message: str, field: str | None = None) -> JSONResponse:
    """Build an API error response with an optional field name."""
    body = {"code": code, "message": message}
    if field is not None:
        body["field"] = field
    return JSONResponse(body, status_code=status)


def _decode_json(raw: bytes) -> object:
    """Parse JSON while rejecting nonstandard numeric constants."""

    def reject_constant(value: str) -> None:
        """Reject a numeric constant that JSON does not allow."""
        raise ValueError(f"{value} is not valid JSON")

    return json.loads(raw, parse_constant=reject_constant)


async def _request_parts(request: Request) -> tuple[object, bytes] | JSONResponse:
    """Read the project JSON and weather file from a multipart request."""
    try:
        form = await request.form()
    except Exception as exc:
        return _problem(422, "invalid_project", str(exc), "project")
    project_part = form.get("project")
    weather_part = form.get("weather_epw")
    if project_part is None:
        return _problem(422, "invalid_project", "Missing project JSON part", "project")
    if not isinstance(weather_part, UploadFile):
        return _problem(422, "invalid_weather", "Missing weather_epw file part", "weather_epw")
    try:
        raw_project = (
            await project_part.read()
            if isinstance(project_part, UploadFile)
            else str(project_part).encode("utf-8")
        )
        project = _decode_json(raw_project)
    except (UnicodeDecodeError, ValueError) as exc:
        return _problem(422, "invalid_project", str(exc), "project")
    weather = await weather_part.read()
    if not weather:
        return _problem(422, "invalid_weather", "The EPW file is empty", "weather_epw")
    return project, weather


def _validate_project_request(engine: str, project: object) -> dict | JSONResponse:
    """Return a validated project or an API error."""
    error = validate_project(engine, project)
    if error is not None:
        field, message = error
        return _problem(422, "invalid_project", message, field)
    project = cast(dict, project)
    if not valid_run_id(project["run_id"]):
        return _problem(
            422,
            "invalid_project",
            "run_id must be 1–64 ASCII letters, digits, underscores or hyphens, start with a letter or digit, and avoid reserved device names",
            "run_id",
        )
    return project


async def _stage_run(root: Path, project: dict, weather: bytes) -> tuple[Path, Path] | JSONResponse:
    """Stage input files and return the config and output paths."""
    run_id = project["run_id"]
    input_root = root / "inputs"
    result_root = root / "results"
    input_root.mkdir(parents=True, exist_ok=True)
    result_root.mkdir(parents=True, exist_ok=True)
    config_path = input_root / run_id / "config.json"
    output_path = result_root / run_id
    if output_path.exists():
        return _problem(409, "run_exists", f"Run ID {run_id} has already been used", "run_id")
    try:
        await run_in_threadpool(stage_project, config_path.parent, project, weather)
    except FileExistsError:
        return _problem(409, "run_exists", f"Run ID {run_id} has already been used", "run_id")
    except Exception as exc:
        message = str(exc)
        if "EPW" in message.upper():
            return _problem(422, "invalid_weather", message, "weather_epw")
        return _problem(422, "invalid_project", message, "project")
    return config_path, output_path


async def _run_and_read(
    engine: str, config_path: Path, output_path: Path, project: dict
) -> JSONResponse:
    """Run the CLI and return its result or a runner error."""
    process = await run_in_threadpool(run_cli, engine, config_path, output_path)
    try:
        result = await run_in_threadpool(result_from_output, engine, output_path, project)
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as exc:
        message = str(exc)
        if process.returncode and process.stderr:
            message = f"{message}: {process.stderr[-1000:]}"
        return _problem(500, "runner_failed", message)
    if process.returncode and result["manifest"]["status"] != "failed":
        return _problem(
            500, "runner_failed", process.stderr[-1000:] or "The runner exited unexpectedly"
        )
    return JSONResponse(result)


async def _run_engine(engine: str, request: Request, root: Path) -> JSONResponse:
    """Validate a request, stage its inputs, and run one engine."""
    parts = await _request_parts(request)
    if isinstance(parts, JSONResponse):
        return parts
    project, weather = parts
    project = _validate_project_request(engine, project)
    if isinstance(project, JSONResponse):
        return project
    paths = await _stage_run(root, project, weather)
    if isinstance(paths, JSONResponse):
        return paths
    config_path, output_path = paths
    return await _run_and_read(engine, config_path, output_path, project)


def create_app(runs_root: Path | None = None) -> FastAPI:
    """Create the API with its run directory and simulation routes."""
    root = Path(runs_root or os.environ.get("DT_API_RUNS_ROOT", ".runs")).resolve()
    application = FastAPI(title="DT Prototype API", version="0.2.0")
    application.openapi = openapi_spec

    @application.post("/runs/dynamic", operation_id="runDynamic")
    async def run_dynamic(request: Request) -> JSONResponse:
        """Run a dynamic simulation and return its results."""
        return await _run_engine("dynamic", request, root)

    @application.post("/runs/monthly", operation_id="runMonthly")
    async def run_monthly(request: Request) -> JSONResponse:
        """Run a monthly simulation and return its results."""
        return await _run_engine("monthly", request, root)

    @application.post("/runs/simplified", operation_id="runSimplified")
    async def run_simplified(request: Request) -> JSONResponse:
        """Run a simplified simulation and return its results."""
        return await _run_engine("simplified", request, root)

    return application


app = create_app()
