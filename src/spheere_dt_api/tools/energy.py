"""Energy bought, CO2 and cost: POST /runs/{dynamic,monthly,simplified,vbdd}/energy."""

from __future__ import annotations

from fastapi import FastAPI

from ..core import (
    Context,
    InputError,
    Job,
    Part,
    Run,
    RunnerError,
    Tool,
    check_dt_prototype_schema,
    python,
    read_manifest,
    read_table,
    route,
    write_json,
)
from ..project import CLI_ENGINES, stage_project, validated_project, vbdd_args

TOOL = Tool("energy")
ENGINES = {**CLI_ENGINES, "vbdd": "Monthly_SS_VBDD"}
PARTS = {"project": Part("json"), "weather_epw": Part("file"), "energy": Part("json")}
TABLES = ("energy_monthly", "energy_annual", "service_monthly", "service_annual")
DEFAULT_SIMPLIFIED = {"comparison_mode": "seasonal_ahu", "zone_mode": "sum"}


def check_boundary(method: str, project: dict) -> None:
    """Reject settings that would count heat twice once energy systems are applied.

    The energy layer converts useful sensible heat with its own systems and solar
    model, so the dynamic method must not also run its plants, humidity model or
    battery. DT Prototype treats a missing `latent` as true.
    """
    if method == "dynamic":
        options = project.get("dynamic", {})
        enabled = [
            name
            for name, default in (("plants", False), ("latent", True), ("pv_battery", False))
            if options.get(name, default)
        ]
        if enabled:
            raise InputError(
                "The energy endpoints need dynamic.plants, dynamic.latent and "
                f"dynamic.pv_battery set to false; still enabled: {', '.join(enabled)}",
                "project",
                code="invalid_project",
            )
    if method == "simplified":
        mode = project.get("simplified", DEFAULT_SIMPLIFIED)["comparison_mode"]
        if mode != "seasonal_ahu":
            raise InputError(
                "The energy endpoints need simplified.comparison_mode set to seasonal_ahu",
                "project",
                code="invalid_project",
            )


def stage(run: Run, values: dict, method: str) -> Job:
    from dt_prototype.energy_carriers.config import EnergyConfig

    project = values["project"]
    check_boundary(method, project)
    check_dt_prototype_schema("energy", values["energy"], "energy")
    config, district = stage_project(run.inputs, project, values["weather_epw"])
    energy_path = run.inputs / "energy.json"
    write_json(energy_path, values["energy"])
    try:
        energy = EnergyConfig.load(energy_path)
        for building in district.buildings:
            energy.building(building.geometry.building_id)
    except (KeyError, ValueError) as exc:
        raise InputError(str(exc).strip("'\""), "energy") from exc
    zone_mode = project.get("simplified", DEFAULT_SIMPLIFIED)["zone_mode"]
    arguments = ["--engine", ENGINES[method], "--zone-mode", zone_mode]
    if method == "dynamic":
        arguments += ["--model", project.get("dynamic", {}).get("model", "5R1C")]
    if method == "vbdd":
        arguments += vbdd_args(project)
    command = python(
        "-m",
        "dt_prototype.energy_carriers.cli",
        "--config",
        str(config),
        "--energy-config",
        str(energy_path),
        "--output",
        str(run.results),
        *arguments,
    )
    return Job(command, {"method": method})


def reader(run: Run, meta: dict) -> dict:
    manifest = read_manifest(run.results / "manifest.json", root=run.root)
    if manifest.get("status") != "complete":
        raise RunnerError(manifest.get("error") or "The energy run did not complete")
    return {
        "method": meta["method"],
        "manifest": manifest,
        **{name: read_table(run.results / f"{name}.csv") for name in TABLES},
    }


def run_id(values: dict) -> str:
    method = values["method"]
    if method not in ENGINES:
        raise InputError(f"method must be one of {', '.join(ENGINES)}", "method")
    return validated_project(method, values["project"])["run_id"]


def register(app: FastAPI, context: Context) -> None:
    route(
        app,
        context,
        TOOL,
        "/runs/{method}/energy",
        "runEnergy",
        PARTS,
        lambda run, values: stage(run, values, values["method"]),
        reader,
        run_id=run_id,
        invalid_code={"project": "invalid_project", "weather_epw": "invalid_weather"},
    )
