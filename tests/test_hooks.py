from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from spheere_dt_api import hooks
from spheere_dt_api.app import create_app
from spheere_dt_api.contract import openapi_spec
from spheere_dt_api.core import Run, Tool

ROOT = Path(__file__).resolve().parents[1]
WEATHER = (ROOT / "prototype/data/examples/ITA_Venezia-Tessera.161050_IGDG.epw").read_bytes()
SPEC = openapi_spec()


def with_fields(changes: dict[tuple[int, int], str]) -> bytes:
    """The example EPW with fields changed, keyed by 1-based file line and field index."""
    lines = WEATHER.decode("latin-1").splitlines(keepends=True)
    for (line, field), value in changes.items():
        body = lines[line - 1].rstrip("\r\n")
        fields = body.split(",")
        fields[field] = value
        lines[line - 1] = ",".join(fields) + lines[line - 1][len(body) :]
    return "".join(lines).encode("latin-1")


def send(client: TestClient, run_id: str, weather: bytes):
    project = copy.deepcopy(SPEC["components"]["examples"]["DynamicRequest"]["value"]["project"])
    project["run_id"] = run_id
    return client.post(
        "/runs/dynamic",
        files={
            "project": ("project.json", json.dumps(project), "application/json"),
            "weather_epw": ("weather.epw", weather, "text/plain"),
        },
    )


def test_repair_epw_replaces_only_bad_wind_and_dew_point(tmp_path: Path) -> None:
    run = Run("repair", tmp_path, tmp_path / "results")
    bad = with_fields({(9, 21): "-0.2", (10, 21): "999", (11, 7): "99.9"})
    repaired = hooks.repair_epw(Tool("thermal"), run, {"weather_epw": bad})["weather_epw"]
    air = WEATHER.decode("latin-1").splitlines()[10].split(",")[6]
    assert repaired == with_fields({(9, 21): "0.0", (10, 21): "0.0", (11, 7): air})
    assert (
        hooks.repair_epw(Tool("thermal"), run, {"weather_epw": WEATHER})["weather_epw"] == WEATHER
    )
    assert hooks.repair_epw(Tool("thermal"), run, {}) == {}


def test_dynamic_run_accepts_bad_wind_and_dew_point(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        weather = with_fields({(9, 21): "-0.2", (500, 7): "99.9"})
        response = send(client, "pvgis_like", weather)
        assert response.status_code == 200, response.text[:1000]
        uploaded = hashlib.sha256(weather).hexdigest()
        for result in (response.json(), client.get("/runs/pvgis_like").json()["result"]):
            assert result["manifest"]["input_hashes"]["weather_epw"] == uploaded
            assert result["monthly"][0]["weather_id"] == f"weather_{uploaded[:16]}"

        bad_air = send(client, "bad_air", with_fields({(20, 6): "99.9"}))
        assert bad_air.status_code == 422
        assert bad_air.json()["code"] == "invalid_weather"
        assert "temp_air" in bad_air.json()["message"]
        assert "line 20" in bad_air.json()["message"]


def test_after_hooks_change_results(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        hooks, "AFTER", (lambda tool, run, payload: {**payload, "hooked": tool.name},)
    )
    with TestClient(create_app(tmp_path)) as client:
        response = send(client, "after_hook", WEATHER)
        assert response.json()["hooked"] == "thermal"
        assert client.get("/runs/after_hook").json()["result"]["hooked"] == "thermal"
