"""Inverse-model configuration staging shared by /inverse, /validate and /pipeline.

DT Prototype inverse configs name input files and model folders by path. Clients send
the files as request parts and refer to earlier runs by ID instead; this module
writes those parts into the run folder and fills in the path fields.
"""

from __future__ import annotations

import copy
from pathlib import Path

from .core import Context, InputError, check_dt_prototype_schema, write_json

DEFAULT_MODELS = ["5p_monthly"]


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
    simulation: tuple[Path, Path] | None = None,
    model_dir: Path | None = None,
    name: str = "inverse_config.json",
    field: str = "config",
) -> Path:
    """Write an inverse config whose path fields point at staged files and runs.

    `simulation` is the (results folder, project config) pair of an earlier energy
    or heat-demand run. Path values the client sends are replaced.
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
                f"A {source['type']} source needs the ID of an earlier run", "energy_run_id"
            )
        source["results"], source["project_config"] = (str(path) for path in simulation)
    if model_dir is not None:
        config["model_dir"] = str(model_dir)
    else:
        config.pop("model_dir", None)
    if uses_opendsm(config):
        if context.opendsm_python is None:
            raise InputError(
                "OpenDSM models are not installed on this server; use 5p_monthly or "
                "build the image with WITH_OPENDSM=true",
                field,
                code="opendsm_unavailable",
            )
        config["opendsm_python"] = str(context.opendsm_python)
    else:
        config.pop("opendsm_python", None)
    check_dt_prototype_schema("inverse", config, field)
    path = directory / name
    write_json(path, config)
    return path
