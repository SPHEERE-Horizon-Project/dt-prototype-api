from __future__ import annotations

import copy
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import jsonschema
import pytest
from dt_prototype.energy_carriers.config import EnergyConfig
from fastapi.testclient import TestClient

from spheere_dt_api.app import create_app
from spheere_dt_api.contract import openapi_spec
from spheere_dt_api.core import write_json

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
CONFIGS = PROTOTYPE / "configs"
EXAMPLES = PROTOTYPE / "data/examples"
CALCULATORS = PROTOTYPE / "to_be_integrated"
WEATHER = (EXAMPLES / "ITA_Venezia-Tessera.161050_IGDG.epw").read_bytes()
SPEC = openapi_spec()
ENERGY = SPEC["components"]["examples"]["EnergyConfigExample"]["value"]


def assert_contract(schema_name: str, result: dict) -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "components": {"schemas": SPEC["components"]["schemas"]},
        "$ref": f"#/components/schemas/{schema_name}",
    }
    jsonschema.Draft202012Validator(schema).validate(result)


def example_project(name: str, run_id: str) -> dict:
    project = copy.deepcopy(SPEC["components"]["examples"][f"{name}Request"]["value"]["project"])
    project["run_id"] = run_id
    return project


def district_project() -> dict:
    """The five-building GeoJSON example from prototype/, without a run ID."""
    source = json.loads((CONFIGS / "example.json").read_text())
    library = lambda name: json.loads((EXAMPLES / name).read_text())  # noqa: E731
    return {
        "schema_version": "1.0",
        "inputs": {
            "geometry": {
                "format": "geojson",
                "feature_collection": library("example_district.geojson"),
            },
            "envelopes": library("archetypes.json"),
            "schedules": library("schedules.json"),
            "systems": library("systems_templates.json"),
            **{
                key: source["inputs"][key]
                for key in ("calendar_year", "time_steps_per_hour", "azimuth_subdivisions")
            },
        },
        "operating": source["operating"],
        "dynamic": source["dynamic"],
        "simplified": source["simplified"],
    }


def json_part(value: object) -> tuple[None, str]:
    return (None, json.dumps(value))


def file_part(path: Path) -> tuple[str, bytes]:
    return (path.name, path.read_bytes())


def energy_request(project: dict, energy: dict = ENERGY) -> dict:
    return {
        "project": json_part(project),
        "weather_epw": ("weather.epw", WEATHER),
        "energy": json_part(energy),
    }


def inverse_files(config: dict | None = None) -> dict:
    config = config or json.loads((CONFIGS / "inverse_5p_example.json").read_text())
    return {
        "config": json_part(config),
        "observations": file_part(EXAMPLES / "inverse/synthetic_billing.csv"),
        "weather": file_part(EXAMPLES / "inverse/synthetic_weather.csv"),
    }


def wait_for(client: TestClient, run_id: str, timeout: float = 300) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = client.get(f"/runs/{run_id}").json()
        if record["status"] not in {"queued", "running"}:
            return record
        time.sleep(0.2)
    raise AssertionError(f"Run {run_id} did not finish")


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(tmp_path)) as test_client:
        yield test_client


@pytest.mark.parametrize("method", ["dynamic", "monthly", "simplified", "vbdd"])
def test_energy_methods_return_energy_tables(client: TestClient, method: str) -> None:
    name = {"dynamic": "Dynamic", "simplified": "Simplified"}.get(method, "Monthly")
    project = example_project(name, f"e_{method}")
    if method == "dynamic":
        project["dynamic"].update(latent=False, plants=False, pv_battery=False)
    response = client.post(f"/runs/{method}/energy", files=energy_request(project))
    assert response.status_code == 200, response.text[:1000]
    result = response.json()
    assert_contract("EnergyRunResult", result)
    assert result["method"] == method
    assert len(result["energy_monthly"]) == 12
    annual = result["energy_annual"][0]
    assert annual["building_id"] == "B1"
    assert annual["grid_import_kWh"] == pytest.approx(
        annual["gross_electricity_kWh"] - annual["pv_self_consumed_kWh"]
    )


def test_energy_rejects_double_counting_and_missing_buildings(client: TestClient) -> None:
    dynamic = example_project("Dynamic", "latent_default")
    response = client.post("/runs/dynamic/energy", files=energy_request(dynamic))
    assert response.status_code == 422
    assert "latent" in response.json()["message"]

    energy = copy.deepcopy(ENERGY)
    energy["buildings"] = {"other": energy["buildings"]["B1"]}
    response = client.post(
        "/runs/monthly/energy", files=energy_request(example_project("Monthly", "m"), energy)
    )
    assert response.status_code == 422
    assert response.json()["field"] == "energy"

    response = client.post(
        "/runs/monthly/energy",
        files={
            "project": json_part(example_project("Monthly", "n")),
            "weather_epw": ("w", WEATHER),
        },
    )
    assert response.status_code == 422
    assert response.json()["field"] == "energy"


def test_vbdd_returns_cases_and_zone_sums(client: TestClient) -> None:
    project = example_project("Monthly", "vbdd_case")
    project["vbdd"] = {"utilisation": "fixed", "eta_heating": 0.9}
    response = client.post(
        "/runs/vbdd", files={"project": json_part(project), "weather_epw": ("w.epw", WEATHER)}
    )
    assert response.status_code == 200, response.text[:1000]
    result = response.json()
    assert_contract("VbddRunResult", result)
    assert len(result["zone_sum_monthly"]) == 12
    assert {row["utilisation"] for row in result["monthly"]} == {"fixed"}


def test_validate_reports_problems_without_failing(client: TestClient) -> None:
    project = district_project()
    passed = client.post(
        "/validate",
        data={"kind": "project"},
        files={"project": json_part(project), "weather_epw": ("w.epw", WEATHER)},
    )
    assert passed.status_code == 200, passed.text[:1000]
    assert_contract("ValidationReport", passed.json())
    assert passed.json()["status"] == "passed"

    broken = client.post("/validate", data={"kind": "energy"}, files={"energy": json_part({})})
    assert broken.status_code == 200
    assert broken.json()["status"] == "failed"
    assert broken.json()["failed_checks"] > 0

    missing = client.post("/validate", data={"kind": "inverse"})
    assert missing.status_code == 422
    assert missing.json()["field"] == "config"


def test_footprint_geometry_feeds_a_heat_demand_run(client: TestClient) -> None:
    response = client.post(
        "/geometry/from-footprints",
        files={
            "footprints": file_part(EXAMPLES / "example_district.geojson"),
            "rules": json_part(
                json.loads((CONFIGS / "cadastral_archetype_rules.example.json").read_text())
            ),
        },
    )
    assert response.status_code == 200, response.text[:1000]
    result = response.json()
    assert_contract("FootprintsResult", result)
    assert len(result["geometry"]["buildings"]) == 5

    project = district_project()
    project["run_id"] = "from_footprints"
    project["inputs"]["geometry"] = result["geometry"]
    run = client.post(
        "/runs/monthly", files={"project": json_part(project), "weather_epw": ("w.epw", WEATHER)}
    )
    assert run.status_code == 200, run.text[:1000]
    assert len(run.json()["annual"]) == 5


def test_adiabatic_surface_reduces_heating(client: TestClient) -> None:
    results = {}
    for boundary in ("auto", "adiabatic"):
        project = example_project("Monthly", f"wall_{boundary}")
        surfaces = project["inputs"]["geometry"]["surfaces"]
        wall = next(row for row in surfaces if row["surface_type"] == "ExtWall")
        wall["boundary_condition"] = boundary
        response = client.post(
            "/runs/monthly", files={"project": json_part(project), "weather_epw": ("w", WEATHER)}
        )
        assert response.status_code == 200, response.text[:1000]
        results[boundary] = response.json()["annual"][0]["heating_kWh"]
    assert results["adiabatic"] < results["auto"]


def test_life_cycle_chain_from_quantities_to_assessment(client: TestClient) -> None:
    project = district_project()
    quantities = client.post(
        "/assets/quantities",
        data={"run_id": "quantities"},
        files={
            "inputs": file_part(EXAMPLES / "asset_quantity_inputs.xlsx"),
            "catalogue": json_part(json.loads((CONFIGS / "asset_catalogue.json").read_text())),
            "project": json_part(project),
            "weather_epw": ("w.epw", WEATHER),
        },
    )
    assert quantities.status_code == 200, quantities.text[:1000]
    assert_contract("QuantitiesResult", quantities.json())

    energy = json.loads((CONFIGS / "energy_example.json").read_text())
    district = {**project, "run_id": "district_energy"}
    assert (
        client.post("/runs/monthly/energy", files=energy_request(district, energy)).status_code
        == 200
    )

    assessment = client.post(
        "/assessment",
        data={"energy_run_id": "district_energy"},
        files={"asset_results": file_part(CONFIGS / "asset_results_example.csv")},
    )
    assert assessment.status_code == 200, assessment.text[:1000]
    result = assessment.json()
    assert_contract("AssessmentResult", result)
    assert result["building_operation"]

    unknown = client.post(
        "/assessment",
        data={"energy_run_id": "quantities"},
        files={"asset_results": file_part(CONFIGS / "asset_results_example.csv")},
    )
    assert unknown.status_code == 422
    assert unknown.json()["field"] == "energy_run_id"


@pytest.mark.parametrize(
    "path,case,data,headline",
    [
        ("/lcc", "lcc/benchmark_case.json", {}, ("outputs", "T560_global_cost_eur")),
        ("/lca", "lca/benchmark_case.json", {}, ("outputs", "T585_total_embodied_carbon_kg")),
        (
            "/circularity",
            "circularity/building_case.json",
            {"mode": "building"},
            ("building", "mci"),
        ),
    ],
)
def test_calculators_return_results_and_details(
    client: TestClient, path: str, case: str, data: dict, headline: tuple[str, str]
) -> None:
    response = client.post(
        path, data=data, files={"case": json_part(json.loads((CALCULATORS / case).read_text()))}
    )
    assert response.status_code == 200, response.text[:1000]
    result = response.json()
    assert_contract("CalculatorResult", result)
    section, key = headline
    assert isinstance(result["results"][section][key], float)
    assert result["details"]


def test_calculator_input_errors_are_422(client: TestClient) -> None:
    response = client.post("/lcc", files={"case": json_part({"assumptions": {}})})
    assert response.status_code == 422
    assert "Missing required field" in response.json()["message"]
    response = client.post("/circularity", data={"mode": "street"}, files={"case": json_part({})})
    assert response.status_code == 422
    assert response.json()["field"] == "mode"


def test_inverse_fit_predict_and_acceptance(client: TestClient) -> None:
    fit = client.post("/inverse", data={"run_id": "fit"}, files=inverse_files())
    assert fit.status_code == 200, fit.text[:1000]
    assert_contract("InverseResult", fit.json())
    assert fit.json()["metrics"]

    config = json.loads((CONFIGS / "inverse_5p_example.json").read_text())
    config["operation"] = "predict"
    predict = client.post("/inverse", data={"model_run_id": "fit"}, files=inverse_files(config))
    assert predict.status_code == 200, predict.text[:1000]

    acceptance = client.post(
        "/inverse/acceptance",
        data={"inverse_run_id": "fit"},
        files={
            "policy": json_part(
                json.loads((CONFIGS / "measured_acceptance_policy.json").read_text())
            )
        },
    )
    assert acceptance.status_code == 200, acceptance.text[:1000]
    assert_contract("AcceptanceReport", acceptance.json())
    assert "run" not in acceptance.json()


def test_opendsm_models_need_the_worker(client: TestClient) -> None:
    config = json.loads((CONFIGS / "inverse_5p_example.json").read_text())
    config["models"] = ["opendsm_billing"]
    response = client.post("/inverse", files=inverse_files(config))
    assert response.status_code == 503
    assert response.json()["code"] == "opendsm_unavailable"


def test_pipeline_runs_in_the_background(client: TestClient) -> None:
    pipeline = json.loads((CONFIGS / "pipeline_assessment_example.json").read_text())
    response = client.post(
        "/pipeline",
        data={"run_id": "pipeline"},
        files={
            "pipeline": json_part(pipeline),
            "project": json_part(district_project()),
            "weather_epw": ("w.epw", WEATHER),
            "energy": json_part(json.loads((CONFIGS / "energy_example.json").read_text())),
            "asset_results": file_part(CONFIGS / "pipeline_assets_example.csv"),
            "asset_quantities": file_part(CONFIGS / "pipeline_quantities_example.csv"),
        },
    )
    assert response.status_code == 202, response.text[:1000]
    assert_contract("RunAccepted", response.json())
    record = wait_for(client, "pipeline")
    assert record["status"] == "complete", record
    assert_contract("RunStatus", record)
    assert set(record["result"]) >= {"manifest", "energy", "assessment"}


def test_runs_report_status_files_and_downloads(client: TestClient) -> None:
    case = json.loads((CALCULATORS / "lcc/benchmark_case.json").read_text())
    assert (
        client.post("/lcc", data={"run_id": "cost"}, files={"case": json_part(case)}).status_code
        == 200
    )
    record = client.get("/runs/cost").json()
    assert record["status"] == "complete"
    assert record["result"]["run_id"] == "cost"
    files = client.get("/runs/cost/files").json()["files"]
    assert "results.json" in files
    download = client.get("/runs/cost/files/results.json")
    assert download.status_code == 200
    assert "outputs" in download.json()
    assert client.get("/runs/cost/files/..%2F..%2Finputs%2Fcost%2Fstatus.json").status_code == 404
    assert client.get("/runs/missing").status_code == 404
    assert (
        client.post("/lcc", data={"run_id": "cost"}, files={"case": json_part(case)}).status_code
        == 409
    )


def test_disabled_tool_and_timeouts_stay_local(tmp_path: Path) -> None:
    case = json.loads((CALCULATORS / "lcc/benchmark_case.json").read_text())
    environ = {"DT_API_DISABLED_TOOLS": "lca", "DT_API_TIMEOUT_LCC": "0.001"}
    with TestClient(create_app(tmp_path, environ)) as client:
        disabled = client.post("/lca", files={"case": json_part(case)})
        assert disabled.status_code == 503
        assert disabled.json()["code"] == "tool_disabled"
        timed_out = client.post("/lcc", files={"case": json_part(case)})
        assert timed_out.status_code == 504
        mci = json.loads((CALCULATORS / "circularity/building_case.json").read_text())
        working = client.post(
            "/circularity", data={"mode": "building"}, files={"case": json_part(mci)}
        )
        assert working.status_code == 200


def test_dt_prototype_runtime_failure_stays_in_its_tool(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        EnergyConfig, "load", Mock(side_effect=RuntimeError("broken energy reader"))
    )
    broken = client.post(
        "/runs/monthly/energy", files=energy_request(example_project("Monthly", "broken"))
    )
    assert broken.status_code == 500
    assert broken.json()["code"] == "staging_failed"
    working = client.post(
        "/runs/monthly",
        files={
            "project": json_part(example_project("Monthly", "fine")),
            "weather_epw": ("w", WEATHER),
        },
    )
    assert working.status_code == 200


def test_slow_lane_does_not_block_fast_requests(tmp_path: Path) -> None:
    pipeline = {"schema_version": "1.0", "mode": "inverse", "inverse_config": "set by the API"}
    case = json.loads((CALCULATORS / "lcc/benchmark_case.json").read_text())
    release = threading.Event()
    with TestClient(create_app(tmp_path, {"DT_API_SLOW_WORKERS": "1"})) as client:
        # Occupy the only slow worker until the fast request has been answered.
        client.app.state.context.lanes["slow"].submit(release.wait, 60)
        queued = client.post(
            "/pipeline",
            data={"run_id": "slow"},
            files={
                "pipeline": json_part(pipeline),
                **{
                    ("inverse_config" if name == "config" else name): part
                    for name, part in inverse_files().items()
                },
            },
        )
        assert queued.status_code == 202
        assert client.post("/lcc", files={"case": json_part(case)}).status_code == 200
        assert client.get("/runs/slow").json()["status"] == "queued"
        release.set()
        assert wait_for(client, "slow")["status"] == "complete"


def test_unknown_energy_method_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/runs/hourly/energy", files=energy_request(example_project("Monthly", "unknown"))
    )
    assert response.status_code == 422
    assert response.json()["field"] == "method"


def test_unfinished_runs_are_marked_interrupted_on_start(tmp_path: Path) -> None:
    run = tmp_path / "inputs" / "stale"
    run.mkdir(parents=True)
    (run / "status.json").write_text(
        json.dumps({"run_id": "stale", "tool": "pipeline", "status": "running"})
    )
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/runs/stale").json()["status"] == "interrupted"


def test_every_schema_property_has_a_description() -> None:
    missing = [
        f"{name}.{prop}"
        for name, schema in SPEC["components"]["schemas"].items()
        for part in [schema, *schema.get("allOf", [])]
        for prop, value in part.get("properties", {}).items()
        if "description" not in value and "$ref" not in value
    ]
    assert not missing, missing


@pytest.mark.parametrize(
    "source,references,field",
    [
        ("csv", {"energy_run_id": "energy", "thermal_run_id": "thermal"}, "thermal_run_id"),
        ("csv", {"energy_run_id": "energy"}, "energy_run_id"),
        ("energy_run", {"thermal_run_id": "thermal"}, "thermal_run_id"),
        ("thermal_monthly", {"energy_run_id": "energy"}, "energy_run_id"),
        ("energy_run", {}, "energy_run_id"),
        ("thermal_monthly", {}, "thermal_run_id"),
        ("energy_run", {"energy_run_id": "missing"}, "energy_run_id"),
    ],
)
def test_inverse_rejects_conflicting_or_missing_references(client, source, references, field):
    config = {"schema_version": "1.0", "source": {"type": source}}
    response = client.post(
        "/inverse", data={"run_id": "bad_source", **references}, files={"config": json_part(config)}
    )
    assert response.status_code == 422, response.text
    assert response.json()["field"] == field
    assert not client.app.state.context.run("bad_source").inputs.exists()


@pytest.mark.parametrize("path", ["/inverse", "/validate", "/pipeline"])
def test_shared_inverse_staging_rejects_csv_with_energy_reference(client, path):
    data = {"run_id": "bad_csv", "energy_run_id": "unused"}
    files = inverse_files()
    if path == "/validate":
        data["kind"] = "inverse"
    elif path == "/pipeline":
        files["inverse_config"] = files.pop("config")
        files["pipeline"] = json_part({"schema_version": "1.0", "mode": "inverse"})
    response = client.post(path, data=data, files=files)
    assert response.status_code == 422, response.text
    assert response.json()["field"] == "energy_run_id"


@pytest.mark.parametrize(
    "problem,field",
    [
        ("schema", "energy"),
        ("coverage", "energy"),
        ("dynamic_boundary", "project"),
        ("simplified_boundary", "project"),
        ("nested", "pipeline"),
        ("options", "pipeline"),
    ],
)
def test_pipeline_rejects_invalid_energy_inputs_before_queueing(client, problem, field):
    project = example_project("Dynamic", "project")
    project["dynamic"].update(latent=False, plants=False, pv_battery=False)
    energy = copy.deepcopy(ENERGY)
    pipeline = {"schema_version": "1.0", "energy": {"engine": "Monthly_SS"}}
    if problem == "schema":
        energy = {}
    elif problem == "coverage":
        energy["buildings"] = {"other": energy["buildings"]["B1"]}
    elif problem == "dynamic_boundary":
        pipeline["energy"]["engine"] = "all"
        project["dynamic"]["latent"] = True
    elif problem == "simplified_boundary":
        pipeline["energy"]["engine"] = "all"
        project["simplified"] = {"comparison_mode": "legacy", "zone_mode": "sum"}
    elif problem == "nested":
        pipeline["assessment"] = None
    elif problem == "options":
        pipeline["energy"]["zone_mode"] = "invalid"
    response = client.post(
        "/pipeline",
        data={"run_id": "bad_pipeline"},
        files={
            "pipeline": json_part(pipeline),
            "project": json_part(project),
            "weather_epw": ("weather.epw", WEATHER),
            "energy": json_part(energy),
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["field"] == field
    run = client.app.state.context.run("bad_pipeline")
    assert not run.inputs.exists()
    assert not run.results.exists()


def test_pipeline_reuse_keeps_existing_results_without_running_other_engines(client):
    # This project enables latent handling, which would prohibit an all-engine run.
    project = example_project("Monthly", "energy_source")
    response = client.post("/runs/monthly/energy", files=energy_request(project))
    assert response.status_code == 200, response.text
    pipeline = {"schema_version": "1.0", "energy": {"mode": "reuse"}}
    response = client.post(
        "/pipeline",
        data={"run_id": "reuse", "energy_run_id": "energy_source"},
        files={"pipeline": json_part(pipeline), **energy_request(project)},
    )
    assert response.status_code == 202, response.text
    record = wait_for(client, "reuse")
    assert record["status"] == "complete", record
    assert record["result"]["manifest"]["status"] == "complete"
    assert record["result"]["manifest"]["stages"]["energy"]["status"] == "reused"


@pytest.mark.parametrize(
    "backend,expected_status,lane",
    [
        ("5p_monthly", 200, "fast"),
        ("opendsm_billing", 202, "slow"),
    ],
)
def test_inverse_backend_selects_worker_and_response_mode(
    client, monkeypatch, backend, expected_status, lane
):
    context = client.app.state.context
    context.opendsm_python = Path(sys.executable)
    submissions = {}
    for name, executor in context.lanes.items():
        submissions[name] = Mock(wraps=executor.submit)
        monkeypatch.setattr(executor, "submit", submissions[name])

    def execute(job, run, timeout):
        # Verify API scheduling without needing an installed OpenDSM environment.
        run.results.mkdir()
        write_json(run.results / "manifest.json", {"status": "complete"})
        write_json(run.results / "model_index.json", {})
        return subprocess.CompletedProcess(job.command, 0, "", "")

    monkeypatch.setattr("spheere_dt_api.core.execute", execute)
    config = json.loads((CONFIGS / "inverse_5p_example.json").read_text())
    config["models"] = [backend]
    response = client.post("/inverse", data={"run_id": "backend"}, files=inverse_files(config))
    assert response.status_code == expected_status, response.text
    submissions[lane].assert_called_once()
    submissions["slow" if lane == "fast" else "fast"].assert_not_called()
    record = wait_for(client, "backend")
    assert record["status"] == "complete", record
    staged = json.loads((context.run("backend").inputs / "inverse_config.json").read_text())
    if backend == "opendsm_billing":
        assert staged["opendsm_python"] == sys.executable
    else:
        assert "opendsm_python" not in staged
