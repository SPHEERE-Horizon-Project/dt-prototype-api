"""Inverse-model configuration staging shared by /inverse, /validate and /pipeline.

DT Prototype inverse configs name input files and model folders by path. Clients send
the files as request parts and refer to earlier runs by ID instead; this module
writes those parts into the run folder and fills in the path fields.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

from .core import Context, InputError, check_dt_prototype_schema, write_json

DEFAULT_MODELS = ["5p_monthly"]


@dataclass(frozen=True)
class SimulationSource:
    results: Path
    project_config: Path


@dataclass(frozen=True)
class StagedInverse:
    path: Path
    needs_opendsm: bool


def resolve_simulation_source(
    context: Context,
    config: object,
    *,
    energy_run_id: str | None = None,
    thermal_run_id: str | None = None,
    field: str = "config",
) -> SimulationSource | None:
    """Resolve exactly the earlier run selected by the inverse source type."""
    if not isinstance(config, dict) or not isinstance(config.get("source"), dict):
        raise InputError("The inverse config needs a source object", field)
    if energy_run_id is not None and thermal_run_id is not None:
        raise InputError("Send energy_run_id or thermal_run_id, not both", "thermal_run_id")
    source_type = config["source"].get("type")
    references = {
        "energy_run_id": (energy_run_id, "energy", "energy_run"),
        "thermal_run_id": (thermal_run_id, "thermal", "thermal_monthly"),
    }
    for name, (run_id, tool, expected_source) in references.items():
        if run_id is not None:
            if source_type != expected_source:
                raise InputError(f"{name} requires source.type={expected_source}", name)
            run = context.completed(run_id, {tool}, name)
            return SimulationSource(run.results, run.inputs / "config.json")
    if source_type in {"energy_run", "thermal_monthly"}:
        name = "energy_run_id" if source_type == "energy_run" else "thermal_run_id"
        raise InputError(f"A {source_type} source needs the {name} part", name)
    return None


def uses_opendsm(config: dict) -> bool:
    """Whether any requested model needs the separate OpenDSM environment."""
    for model in config.get("models", DEFAULT_MODELS):
        backend = model.get("backend", "") if isinstance(model, dict) else str(model)
        if backend.startswith("opendsm"):
            return True
    return False


def stage_inverse(
    context: Context,
    directory: Path,
    config: object,
    *,
    observations: bytes | None = None,
    weather: bytes | None = None,
    simulation: SimulationSource | None = None,
    model_dir: Path | None = None,
    name: str = "inverse_config.json",
    field: str = "config",
) -> StagedInverse:
    """Write an inverse config whose path fields point at staged files and runs.

    `simulation` names an earlier run, or the energy stage of this same pipeline.
    Path values the client sends are replaced.
    """
    if not isinstance(config, dict) or not isinstance(config.get("source"), dict):
        raise InputError("The inverse config needs a source object", field)
    config = copy.deepcopy(config)
    source = config["source"]
    if source.get("type") == "csv":
        if observations is None or weather is None:
            raise InputError(
                "A csv source needs the observations and weather files", "observations"
            )
        stem = Path(name).stem
        (directory / f"{stem}_observations.csv").write_bytes(observations)
        (directory / f"{stem}_weather.csv").write_bytes(weather)
        source["observations"] = f"{stem}_observations.csv"
        source["weather"] = f"{stem}_weather.csv"
    elif source.get("type") in {"energy_run", "thermal_monthly"}:
        if simulation is None:
            raise InputError(
                f"A {source['type']} source needs the ID of an earlier run",
                "energy_run_id" if source["type"] == "energy_run" else "thermal_run_id",
            )
        source["results"] = str(simulation.results)
        source["project_config"] = str(simulation.project_config)
    if model_dir is not None:
        config["model_dir"] = str(model_dir)
    else:
        config.pop("model_dir", None)
    # Check model shapes before inspecting backends or injecting the worker path.
    config.pop("opendsm_python", None)
    check_dt_prototype_schema("inverse", config, field)
    needs_opendsm = uses_opendsm(config)
    if needs_opendsm:
        if context.opendsm_python is None:
            raise InputError(
                "OpenDSM models are not installed on this server; use 5p_monthly or "
                "build the image with WITH_OPENDSM=true",
                field,
                code="opendsm_unavailable",
            )
        config["opendsm_python"] = str(context.opendsm_python)
    path = directory / name
    write_json(path, config)
    return StagedInverse(path, needs_opendsm)
