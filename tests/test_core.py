from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from spheere_dt_api.app import create_app
from spheere_dt_api.core import (
    EmptyMetadata,
    ExecutionPolicy,
    InputError,
    Job,
    Part,
    ReadResult,
    RequestValues,
    Run,
    RunnerError,
    Tool,
    _finish,
    respond,
    route,
    write_json,
)
from spheere_dt_api.inverse_config import resolve_simulation_source


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(tmp_path)) as test_client:
        yield test_client


def report_files(run: Run, tool: str, status: str) -> dict:
    """Minimal CLI outputs needed to exercise each reader's result contract."""
    run.results.mkdir()
    report = {"status": status}
    meta = {}
    if tool == "thermal":
        report["building_outputs"] = {}
        meta = {"engine": "monthly", "zone_labels": []}
    elif tool == "energy":
        meta = {"method": "monthly"}
    elif tool in {"lcc", "lca", "circularity"}:
        meta = {"mode": "building"}
        write_json(run.results / "results.json", {})
    elif tool == "inverse":
        write_json(run.results / "model_index.json", {})
    elif tool == "validate":
        meta = {"kind": "energy"}
    if tool == "footprints":
        geometry = run.results / "geometry"
        geometry.mkdir()
        for name in ("buildings", "zones", "surfaces"):
            (geometry / f"{name}.csv").write_text("building_id\n", encoding="utf-8")
        filename = "preprocessing_manifest.json"
    elif tool in {"validate", "acceptance"}:
        filename = "report.json"
    else:
        filename = "manifest.json"
    write_json(run.results / filename, report)
    return meta


REPORT_EXITS = [
    ("thermal", "complete", 0),
    ("thermal", "failed", 1),
    ("inverse", "complete", 0),
    ("inverse", "failed", 1),
    ("inverse", "partial", 2),
    ("inverse", "incomplete", 2),
    ("pipeline", "complete", 0),
    ("pipeline", "failed", 1),
    ("pipeline", "partial", 2),
    ("pipeline", "incomplete", 2),
    ("quantities", "complete", 0),
    ("quantities", "incomplete", 2),
    ("validate", "passed", 0),
    ("validate", "failed", 1),
    ("acceptance", "accepted", 0),
    ("acceptance", "review_required", 2),
    *[
        (tool, "complete", 0)
        for tool in ("energy", "vbdd", "footprints", "assessment", "lcc", "lca", "circularity")
    ],
]


@pytest.mark.parametrize("tool,status,exit_code", REPORT_EXITS)
def test_report_exit_contract_and_restart(client, monkeypatch, tool, status, exit_code):
    context = client.app.state.context
    run = context.reserve(Tool(tool), "report")
    meta = report_files(run, tool, status)
    run.set_status(meta=meta)
    monkeypatch.setattr(
        "spheere_dt_api.core.execute",
        lambda *_: subprocess.CompletedProcess([], exit_code, "", ""),
    )
    result = _finish(run, Job([], meta), context.readers[tool], 10)
    assert run.status()["status"] == "complete"
    assert client.get("/runs/report").json()["result"] == result

    # Load a stored record without introducing scheduling/outcome fields or a migration.
    record = json.loads(run.status_path.read_text())
    if not meta:
        record.pop("meta", None)
    record.pop("created_utc", None)
    write_json(run.status_path, record)
    with TestClient(create_app(context.root)) as restarted:
        assert restarted.get("/runs/report").json()["result"] == result


@pytest.mark.parametrize(
    "tool",
    [
        "thermal",
        "inverse",
        "pipeline",
        "quantities",
        "validate",
        "acceptance",
        "energy",
        "vbdd",
        "footprints",
        "assessment",
        "lcc",
        "lca",
        "circularity",
    ],
)
@pytest.mark.parametrize("status", ["running", "unknown"])
def test_nonterminal_or_unknown_reports_fail(client, monkeypatch, tool, status):
    context = client.app.state.context
    run = context.reserve(Tool(tool), "bad_report")
    meta = report_files(run, tool, status)
    monkeypatch.setattr(
        "spheere_dt_api.core.execute", lambda *_: subprocess.CompletedProcess([], 0, "", "")
    )
    with pytest.raises(RunnerError):
        _finish(run, Job([], meta), context.readers[tool], 10)
    assert run.status()["status"] == "failed"


@pytest.mark.parametrize("expected,actual", [(0, 1), (1, 0), (2, 1), (0, -9)])
def test_exit_must_match_report_even_without_manifest(client, monkeypatch, expected, actual):
    context = client.app.state.context
    run = context.reserve(Tool("acceptance"), "mismatch")
    monkeypatch.setattr(
        "spheere_dt_api.core.execute", lambda *_: subprocess.CompletedProcess([], actual, "", "")
    )
    with pytest.raises(RunnerError):
        _finish(run, Job([], {}), lambda *_: ReadResult({"status": "accepted"}, expected), 10)
    assert run.status()["status"] == "failed"


def test_missing_report_fails(client, monkeypatch):
    context = client.app.state.context
    run = context.reserve(Tool("lcc"), "missing")
    monkeypatch.setattr(
        "spheere_dt_api.core.execute", lambda *_: subprocess.CompletedProcess([], 0, "", "")
    )
    with pytest.raises(RunnerError, match="no manifest"):
        _finish(run, Job([], {}), context.readers["lcc"], 10)
    assert run.status()["status"] == "failed"


@pytest.mark.parametrize("lane", ["fast", "slow"])
@pytest.mark.parametrize("background", [False, True])
def test_lane_and_response_mode_are_independent(client, monkeypatch, lane, background):
    context = client.app.state.context
    submissions = {}
    for name, executor in context.lanes.items():
        submissions[name] = Mock(wraps=executor.submit)
        monkeypatch.setattr(executor, "submit", submissions[name])
    monkeypatch.setattr(
        "spheere_dt_api.core.execute", lambda *_: subprocess.CompletedProcess([], 0, "", "")
    )
    run = context.reserve(Tool("test"), "schedule")
    job = Job([], {}, ExecutionPolicy(lane, background))
    response = asyncio.run(respond(context, Tool("test"), run, job, lambda *_: ReadResult({})))
    assert response.status_code == (202 if background else 200)
    submissions[lane].assert_called_once()
    submissions["fast" if lane == "slow" else "slow"].assert_not_called()
    context.lanes[lane].shutdown(wait=True)
    assert run.status()["status"] == "complete"


def test_validation_precedes_reservation_and_staging_failures_release_id(client, monkeypatch):
    context = client.app.state.context
    reserve = Mock(wraps=context.reserve)
    monkeypatch.setattr(context, "reserve", reserve)
    monkeypatch.setattr(
        "spheere_dt_api.core.execute", lambda *_: subprocess.CompletedProcess([], 0, "", "")
    )

    def validate(values: RequestValues) -> None:
        if values["mode"] == "invalid":
            raise InputError("Rejected before reservation", "mode")

    def stager(run: Run, values: RequestValues) -> Job[EmptyMetadata]:
        if values["mode"] == "bad_stage":
            raise InputError("Rejected during staging", "mode")
        return Job([], {})

    route(
        client.app,
        context,
        Tool("test"),
        "/test-flow",
        "testFlow",
        {"run_id": Part("text"), "mode": Part("text")},
        stager,
        lambda *_: ReadResult({}),
        validate=validate,
    )
    response = client.post("/test-flow", data={"run_id": "retry", "mode": "invalid"})
    assert response.status_code == 422
    reserve.assert_not_called()
    response = client.post("/test-flow", data={"run_id": "retry", "mode": "bad_stage"})
    assert response.status_code == 422
    assert not context.run("retry").inputs.exists()
    assert client.post("/test-flow", data={"run_id": "retry", "mode": "good"}).status_code == 200


@pytest.mark.parametrize("engine", ["dynamic", "monthly", "simplified"])
def test_thermal_reference_accepts_each_method(client, engine):
    context = client.app.state.context
    run = context.reserve(Tool("thermal"), "source")
    run.results.mkdir()
    run.set_status(status="complete", meta={"engine": engine, "zone_labels": []})
    source = resolve_simulation_source(
        context, {"source": {"type": "thermal_monthly"}}, thermal_run_id="source"
    )
    assert source.results == run.results
    assert source.project_config == run.inputs / "config.json"


@pytest.mark.parametrize("state", ["staging", "queued", "running", "failed", "interrupted"])
def test_simulation_reference_requires_completed_run(client, state):
    context = client.app.state.context
    run = context.reserve(Tool("energy"), "source")
    run.results.mkdir()
    run.set_status(status=state)
    with pytest.raises(InputError, match="not completed"):
        resolve_simulation_source(
            context, {"source": {"type": "energy_run"}}, energy_run_id="source"
        )


@pytest.mark.parametrize("tool", ["energy", "quantities"])
def test_simulation_reference_checks_tool_identity(client, tool):
    context = client.app.state.context
    run = context.reserve(Tool(tool), "source")
    run.results.mkdir()
    run.set_status(status="complete")
    if tool != "energy":
        with pytest.raises(InputError, match="No energy run"):
            resolve_simulation_source(
                context, {"source": {"type": "energy_run"}}, energy_run_id="source"
            )
    else:
        source = resolve_simulation_source(
            context, {"source": {"type": "energy_run"}}, energy_run_id="source"
        )
        assert source.results == run.results
