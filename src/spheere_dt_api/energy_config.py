"""Energy input staging shared by standalone endpoints and forward pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dt_prototype.energy_carriers.config import EnergyConfig

from .core import InputError, check_dt_prototype_schema, write_json
from .project import stage_project

DEFAULT_SIMPLIFIED = {"comparison_mode": "seasonal_ahu", "zone_mode": "sum"}


@dataclass(frozen=True)
class StagedEnergy:
    project_config: Path
    energy_config: Path


def check_boundary(engine: str | None, project: dict) -> None:
    """Check sensible-heat boundaries for engines that will actually run.

    A missing dynamic.latent is true in DT Prototype. Reused results have their
    own provenance checks and do not run the project's current engine settings.
    """
    if engine in {"Dynamic_RC", "all"}:
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
    if engine in {"Monthly_SS_simplified", "all"}:
        mode = project.get("simplified", DEFAULT_SIMPLIFIED)["comparison_mode"]
        if mode != "seasonal_ahu":
            raise InputError(
                "The energy endpoints need simplified.comparison_mode set to seasonal_ahu",
                "project",
                code="invalid_project",
            )


def stage_energy(
    directory: Path, project: dict, weather: bytes, energy: object, *, engine: str | None
) -> StagedEnergy:
    """Stage a project and check energy configuration and building coverage."""
    check_boundary(engine, project)
    check_dt_prototype_schema("energy", energy, "energy")
    project_path, district = stage_project(directory, project, weather)
    energy_path = directory / "energy.json"
    write_json(energy_path, energy)
    try:
        config = EnergyConfig.load(energy_path)
        for building in district.buildings:
            config.building(building.geometry.building_id)
    except (KeyError, ValueError) as exc:
        raise InputError(str(exc).strip("'\""), "energy") from exc
    return StagedEnergy(project_path, energy_path)
