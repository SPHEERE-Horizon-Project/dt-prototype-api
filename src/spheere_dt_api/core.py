"""Shared plumbing for every tool: request parts, run folders, lanes and results.

Each tool stages its inputs into a run folder, runs one DT Prototype command in a
separate process, and reads that command's output files. Tool modules use shared
helpers rather than importing each other.
"""

from __future__ import annotations

import asyncio
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict, Unpack, cast

from dt_prototype.validation import schema_errors
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

from . import hooks

ROOT = Path(__file__).resolve().parents[2]
PROTOTYPE = ROOT / "prototype"
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
RESERVED_IDS = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
RUN_ID_MESSAGE = (
    "run_id must be 1–64 ASCII letters, digits, underscores or hyphens, start with a "
    "letter or digit, and avoid reserved device names"
)
# Exception names that DT Prototype commands raise for bad input rather than for bugs.
INPUT_ERRORS = {
    "CircularityInputError",
    "JSONDecodeError",
    "KeyError",
    "LCAInputError",
    "LCCInputError",
    "ValueError",
}
UNFINISHED = {"queued", "running"}
# Input problems that are not plain 422s.
STATUS_BY_CODE = {"run_exists": 409, "opendsm_unavailable": 503}
# Manifest fields that repeat the inputs or list source hashes; responses leave them out.
MANIFEST_NOISE = {"code_hashes", "code_sha256", "configuration"}

type Lane = Literal["fast", "slow"]
type RunState = Literal["staging", "queued", "running", "complete", "failed", "interrupted"]
# Request JSON is checked against each tool's schema after multipart decoding.
type RequestValues = dict[str, Any]


class EmptyMetadata(TypedDict):
    """Metadata for tools whose readers need only the run folders."""


class RunError(TypedDict):
    code: str
    message: str


class RunRecord(TypedDict, total=False):
    """The existing status.json format; older records may omit optional fields."""

    run_id: str
    tool: str
    status: RunState
    created_utc: str
    queued_utc: str
    started_utc: str
    finished_utc: str
    meta: Mapping[str, object]
    error: RunError


def decode_run_record(value: object) -> RunRecord:
    """Check stored record fields at the JSON boundary without changing their format."""
    if not isinstance(value, dict):
        raise ValueError("Run status must be an object")
    if value.get("status") not in {
        "staging",
        "queued",
        "running",
        "complete",
        "failed",
        "interrupted",
    }:
        raise ValueError("Invalid run status")
    for key in ("run_id", "tool", "created_utc", "queued_utc", "started_utc", "finished_utc"):
        if key in value and not isinstance(value[key], str):
            raise ValueError(f"Run {key} must be text")
    if "meta" in value and not isinstance(value["meta"], dict):
        raise ValueError("Run metadata must be an object")
    if "error" in value and (
        not isinstance(value["error"], dict)
        or not all(isinstance(value["error"].get(key), str) for key in ("code", "message"))
    ):
        raise ValueError("Run error needs a code and message")
    return cast(RunRecord, value)


class InputError(Exception):
    """A request problem the caller can fix, reported as 422."""

    def __init__(self, message: str, field: str | None = None, code: str = "invalid_input"):
        super().__init__(message)
        self.field = field
        self.code = code


class RunnerError(Exception):
    """A command that did not produce a usable result."""

    def __init__(self, message: str, status: int = 500, code: str = "runner_failed"):
        super().__init__(message)
        self.status = status
        self.code = code


def problem(status: int, code: str, message: str, field: str | None = None) -> JSONResponse:
    """Build an API error response with an optional field name."""
    body = {"code": code, "message": message}
    if field is not None:
        body["field"] = field
    return JSONResponse(body, status_code=status)


def decode_json(raw: bytes) -> object:
    """Parse JSON while rejecting nonstandard numeric constants."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"{value} is not valid JSON")

    return json.loads(raw, parse_constant=reject_constant)


def write_json(path: Path, value: object) -> None:
    """Write a JSON value to a UTF-8 file."""
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def valid_run_id(run_id: object) -> bool:
    """Check whether a run ID is safe to use as a directory name."""
    return (
        isinstance(run_id, str)
        and RUN_ID_PATTERN.fullmatch(run_id) is not None
        and run_id.upper() not in RESERVED_IDS
    )


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Part:
    """One multipart field: a JSON document, an uploaded file or a short text value."""

    kind: Literal["json", "file", "text"]
    required: bool = True


async def read_parts(request: Request, spec: Mapping[str, Part]) -> RequestValues:
    """Read the declared multipart fields, raising InputError for missing or bad ones."""
    try:
        form = await request.form()
    except Exception as exc:
        raise InputError(str(exc)) from exc
    values: dict[str, Any] = {}
    for name, part in spec.items():
        item = form.get(name)
        if item is None or (isinstance(item, str) and not item.strip()):
            if part.required:
                raise InputError(f"Missing {name} part", name)
            continue
        raw = await item.read() if isinstance(item, UploadFile) else str(item).encode("utf-8")
        if part.kind == "file":
            if not raw:
                raise InputError(f"The {name} file is empty", name)
            values[name] = raw
        elif part.kind == "json":
            try:
                values[name] = decode_json(raw)
            except (UnicodeDecodeError, ValueError) as exc:
                raise InputError(str(exc), name) from exc
        else:
            values[name] = raw.decode("utf-8", errors="replace").strip()
    return values


@dataclass(frozen=True)
class ExecutionPolicy:
    """Worker selection and whether the caller waits are independent decisions."""

    lane: Lane = "fast"
    background: bool = False


@dataclass(frozen=True)
class Job[Meta: Mapping[str, object]]:
    """A staged command plus what the reader needs to interpret its output later."""

    command: list[str]
    meta: Meta
    policy: ExecutionPolicy = ExecutionPolicy()


@dataclass(frozen=True)
class ReadResult:
    """An API payload and the CLI exit code its report describes."""

    payload: dict[str, Any]
    expected_exit_code: int = 0

    @classmethod
    def reported(
        cls, payload: dict[str, Any], status: object, exits: Mapping[str, int]
    ) -> ReadResult:
        """Interpret a report using the tool's declared terminal statuses."""
        if not isinstance(status, str) or status not in exits:
            raise RunnerError(
                f"The runner produced an unknown or unfinished report status: {status!r}"
            )
        return cls(payload, exits[status])


@dataclass(frozen=True)
class Tool:
    """A tool's identity and default timeout."""

    name: str
    timeout_s: float = 600.0


@dataclass(frozen=True)
class Run:
    """The two folders of one run: staged inputs plus state, and command output."""

    run_id: str
    inputs: Path
    results: Path

    @property
    def root(self) -> Path:
        return self.inputs.parent.parent

    @property
    def status_path(self) -> Path:
        return self.inputs / "status.json"

    def status(self) -> RunRecord | None:
        if not self.status_path.is_file():
            return None
        return decode_run_record(json.loads(self.status_path.read_text(encoding="utf-8")))

    def set_status(self, **changes: Unpack[RunRecord]) -> RunRecord:
        record: RunRecord = {**(self.status() or {}), **changes}
        temporary = self.status_path.with_suffix(".tmp")
        write_json(temporary, record)
        temporary.replace(self.status_path)
        return record


type Validator = Callable[[RequestValues], None]
type RunIdSelector = Callable[[RequestValues], str | None]
type Stager[Meta: Mapping[str, object]] = Callable[[Run, RequestValues], Job[Meta]]
type Reader[Meta: Mapping[str, object]] = Callable[[Run, Meta], ReadResult]


class Context:
    """Run storage, the two lanes and the per-tool settings for one app instance."""

    def __init__(self, root: Path, environ: Mapping[str, str] | None = None):
        env = os.environ if environ is None else environ
        self.root = root
        self.lanes = {
            "fast": ThreadPoolExecutor(int(env.get("DT_API_FAST_WORKERS", "4")), "dt-fast"),
            "slow": ThreadPoolExecutor(int(env.get("DT_API_SLOW_WORKERS", "1")), "dt-slow"),
        }
        self.disabled = {
            name.strip() for name in env.get("DT_API_DISABLED_TOOLS", "").split(",") if name.strip()
        }
        self.timeouts = {
            key.removeprefix("DT_API_TIMEOUT_").lower(): float(value)
            for key, value in env.items()
            if key.startswith("DT_API_TIMEOUT_")
        }
        worker = env.get("DT_OPENDSM_PYTHON", "")
        self.opendsm_python = Path(worker) if worker and Path(worker).is_file() else None
        # Different tools persist different metadata. Type erasure is confined to
        # this registry, which is used when polling deserialized run records.
        self.readers: dict[str, Reader[Any]] = {}
        (root / "inputs").mkdir(parents=True, exist_ok=True)
        (root / "results").mkdir(parents=True, exist_ok=True)
        self._mark_interrupted()

    def run(self, run_id: str) -> Run:
        return Run(run_id, self.root / "inputs" / run_id, self.root / "results" / run_id)

    def timeout(self, tool: Tool) -> float:
        return self.timeouts.get(tool.name, tool.timeout_s)

    def reserve(self, tool: Tool, run_id: str | None) -> Run:
        """Claim a new run folder, or raise a 409 if the ID was used before."""
        run_id = run_id or f"{tool.name}-{uuid.uuid4().hex[:12]}"
        if not valid_run_id(run_id):
            raise InputError(RUN_ID_MESSAGE, "run_id")
        run = self.run(run_id)
        try:
            if run.results.exists():
                raise FileExistsError(run_id)
            run.inputs.mkdir()
        except FileExistsError:
            raise InputError(
                f"Run ID {run_id} has already been used", "run_id", code="run_exists"
            ) from None
        run.set_status(run_id=run_id, tool=tool.name, status="staging", created_utc=now())
        return run

    def completed(self, run_id: object, tool_names: set[str], field_name: str) -> Run:
        """Resolve a reference to an earlier completed run of one of the given tools."""
        if not valid_run_id(run_id):
            raise InputError(RUN_ID_MESSAGE, field_name)
        run = self.run(str(run_id))
        record = run.status()
        if record is None or record.get("tool") not in tool_names:
            raise InputError(f"No {' or '.join(sorted(tool_names))} run named {run_id}", field_name)
        if record.get("status") != "complete" or not run.results.is_dir():
            raise InputError(f"Run {run_id} has not completed", field_name)
        return run

    def _mark_interrupted(self) -> None:
        for path in (self.root / "inputs").glob("*/status.json"):
            run = self.run(path.parent.name)
            try:
                record = run.status() or {}
            except (OSError, ValueError):
                continue
            if record.get("status") in UNFINISHED | {"staging"}:
                run.set_status(status="interrupted", finished_utc=now())

    def shutdown(self) -> None:
        for lane in self.lanes.values():
            lane.shutdown(wait=False, cancel_futures=True)


def execute(
    job: Job[Mapping[str, object]], run: Run, timeout: float
) -> subprocess.CompletedProcess[str]:
    """Run one staged command with the run folder as its working directory."""
    try:
        return subprocess.run(
            job.command,
            cwd=run.inputs,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RunnerError(
            f"The run took longer than {timeout:g} s and was stopped", 504, "runner_timeout"
        ) from exc


def python(*args: str) -> list[str]:
    """Build a command that runs the API's own interpreter."""
    return [sys.executable, *args]


def check_dt_prototype_schema(kind: str, value: object, field: str) -> None:
    """Validate a JSON part against the DT Prototype schema of that kind."""
    errors = schema_errors(value, kind)
    if errors:
        first = errors[0]
        raise InputError(f"{first['field']}: {first['message']}", field)


def classify_failure(process: subprocess.CompletedProcess[str]) -> Exception:
    """Turn a failed command into an input error or a runner error."""
    lines = [line for line in (process.stderr or "").splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    match = re.match(r"(?:[\w.]+\.)?(\w+): (.*)", last)
    if match and match.group(1) in INPUT_ERRORS:
        message = match.group(2).strip("'\"")
        if match.group(1) == "KeyError":
            message = f"Missing required field {message!r}"
        return InputError(message)
    return RunnerError(last or process.stdout[-1000:] or "The runner exited unexpectedly")


def server_paths_removed(value: object, root: Path) -> object:
    """Replace absolute run-storage paths in DT Prototype output with run-relative ones."""
    prefix = f"{root}/"
    if isinstance(value, str):
        return value.replace(prefix, "")
    if isinstance(value, list):
        return [server_paths_removed(item, root) for item in value]
    if isinstance(value, dict):
        return {key: server_paths_removed(item, root) for key, item in value.items()}
    return value


def read_manifest(
    path: Path, finished: set[str] | None = None, root: Path | None = None
) -> dict[str, Any]:
    """Read a command manifest without the fields that only repeat inputs or hashes."""
    if not path.is_file():
        raise RunnerError("The runner produced no manifest")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if finished is not None and manifest.get("status") not in finished:
        raise RunnerError("The runner did not finish")
    manifest = {key: value for key, value in manifest.items() if key not in MANIFEST_NOISE}
    return server_paths_removed(manifest, root) if root is not None else manifest


def cell(name: str, value: str | None) -> object:
    """Type one CSV cell: identifiers stay text, numbers and booleans are converted."""
    if value is None or value == "":
        return None
    if name == "id" or name.endswith(("_id", "_ids")):
        return value
    if value in {"True", "False", "true", "false"}:
        return value.lower() == "true"
    if re.fullmatch(r"[+-]?\d+", value):
        return int(value)
    try:
        number = float(value)
    except ValueError:
        return value
    return number if math.isfinite(number) else None


def read_table(path: Path) -> list[dict[str, object]]:
    """Read a CSV file as typed rows, or return an empty list if it is absent."""
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return [
            {key: cell(key, value) for key, value in row.items()} for row in csv.DictReader(stream)
        ]


def read_json(path: Path, root: Path | None = None) -> Any:
    """Read a JSON output file, with run-storage paths made relative when root is given."""
    if not path.is_file():
        raise RunnerError(f"The runner produced no {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    return server_paths_removed(value, root) if root is not None else value


async def respond[Meta: Mapping[str, object]](
    context: Context,
    tool: Tool,
    run: Run,
    job: Job[Meta],
    reader: Reader[Meta],
) -> JSONResponse:
    """Run a staged job in its lane and answer with its result, or with 202."""
    run.set_status(status="queued", meta=job.meta, queued_utc=now())
    timeout = context.timeout(tool)
    lane = context.lanes[job.policy.lane]
    if job.policy.background:
        lane.submit(_finish, run, job, reader, timeout)
        return JSONResponse(
            {"run_id": run.run_id, "status": "queued", "status_url": f"/runs/{run.run_id}"},
            status_code=202,
        )
    try:
        result = await asyncio.wrap_future(lane.submit(_finish, run, job, reader, timeout))
    except RunnerError as exc:
        return problem(exc.status, exc.code, str(exc))
    except InputError as exc:
        return problem(422, exc.code, str(exc), exc.field)
    return JSONResponse(result)


def _finish[Meta: Mapping[str, object]](
    run: Run, job: Job[Meta], reader: Reader[Meta], timeout: float
) -> dict[str, Any]:
    """Run the command, read its output and record the final state."""
    run.set_status(status="running", started_utc=now())
    try:
        process = execute(job, run, timeout)
        try:
            result = reader(run, job.meta)
        except (RunnerError, FileNotFoundError, KeyError, ValueError) as exc:
            if process.returncode:
                raise classify_failure(process) from exc
            raise RunnerError(str(exc)) from exc
        if process.returncode != result.expected_exit_code:
            if process.returncode:
                raise classify_failure(process)
            raise RunnerError(
                f"Runner exit code {process.returncode} does not match its report "
                f"(expected {result.expected_exit_code})"
            )
    except (InputError, RunnerError) as exc:
        run.set_status(
            status="failed", finished_utc=now(), error={"code": exc.code, "message": str(exc)}
        )
        raise
    except Exception as exc:
        run.set_status(
            status="failed",
            finished_utc=now(),
            error={"code": "runner_failed", "message": str(exc)},
        )
        raise RunnerError(str(exc)) from exc
    run.set_status(status="complete", finished_utc=now())
    return {"run_id": run.run_id, **result.payload}


async def stage[Meta: Mapping[str, object]](
    context: Context, tool: Tool, run_id: str | None, stager: Callable[[Run], Job[Meta]]
) -> tuple[Run, Job[Meta]]:
    """Reserve a run folder and stage inputs, removing the folder if staging fails."""
    run = context.reserve(tool, run_id)
    try:
        job = await run_in_threadpool(stager, run)
    except BaseException:
        shutil.rmtree(run.inputs, ignore_errors=True)
        raise
    return run, job


def route[Meta: Mapping[str, object]](
    app: FastAPI,
    context: Context,
    tool: Tool,
    path: str,
    operation_id: str,
    parts: Mapping[str, Part],
    stager: Stager[Meta],
    reader: Reader[Meta],
    *,
    validate: Validator | None = None,
    run_id: RunIdSelector = lambda values: values.get("run_id"),
    invalid_code: Mapping[str, str] | None = None,
) -> None:
    """Register one POST endpoint that stages inputs, runs a job and returns its result."""

    def read(run: Run, meta: Meta) -> ReadResult:
        result = reader(run, meta)
        payload = result.payload
        for hook in hooks.AFTER:
            payload = hook(tool, payload)
        return ReadResult(payload, result.expected_exit_code)

    context.readers[tool.name] = read

    async def endpoint(request: Request) -> JSONResponse:
        if tool.name in context.disabled:
            return disabled(tool)
        try:
            # Path parameters, such as the method in /runs/{method}/energy, join the parts.
            values = {**request.path_params, **await read_parts(request, parts)}
            for hook in hooks.BEFORE:
                values = hook(tool, values)
            if validate is not None:
                validate(values)
            requested_id = run_id(values)
            run, job = await stage(context, tool, requested_id, lambda run: stager(run, values))
        except InputError as exc:
            code = exc.code
            if code == "invalid_input" and invalid_code and exc.field in invalid_code:
                code = invalid_code[exc.field]
            return problem(STATUS_BY_CODE.get(code, 422), code, str(exc), exc.field)
        except (ValueError, KeyError, TypeError) as exc:
            return problem(422, "invalid_input", str(exc))
        except Exception as exc:
            # A staging failure affects this request only.
            return problem(500, "staging_failed", f"{type(exc).__name__}: {exc}")
        return await respond(context, tool, run, job, read)

    app.add_api_route(path, endpoint, methods=["POST"], operation_id=operation_id)


def disabled(tool: Tool) -> JSONResponse:
    return problem(
        503,
        "tool_disabled",
        f"The {tool.name} tool is switched off on this server (DT_API_DISABLED_TOOLS)",
    )
