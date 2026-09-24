"""Up-front input validation: check every cross-reference before simulating.

At portfolio/urban scale, discovering broken references one ``KeyError`` (or
one silently ignored fallback) at a time is unreliable — this module checks
the *whole* district in one pass and returns every problem at once.

This is a pipeline-level utility (like a CLI would be): it sits above the
four layers and may import from preprocessing and simulation; no layer
imports it back, so the dependency direction of NFR-01 is preserved.

Typical use::

    from dt_prototype.dynamic.validation import validate_district_inputs

    issues = validate_district_inputs(
        geojson_path=..., archetypes_path=..., schedules_path=...,
        systems_path=...,
    )
    errors = [i for i in issues if i["severity"] == "error"]
    assert not errors, errors
"""

from __future__ import annotations

from pathlib import Path

from dt_prototype.common.preprocessing.archetypes import load_envelope_archetypes
from dt_prototype.common.preprocessing.building_input import DistrictInput
from dt_prototype.common.preprocessing.geometry import BuildingGeometry, load_district_geojson
from dt_prototype.common.preprocessing.schedules import load_end_use_schedules
from dt_prototype.common.preprocessing.system_templates import load_system_templates
from dt_prototype.dynamic.simulation.systems import resolve_cooling_system, resolve_heating_system

_KNOWN_SOLAR_TAGS = {"pv", "st"}


def _issue(building: str, field: str, value, message: str, severity: str) -> dict:
    """One structured validation finding."""
    return {
        "building": building,
        "field": field,
        "value": value,
        "message": message,
        "severity": severity,  # "error" (simulation will fail / be wrong)
        #             or "warning" (graceful degradation, e.g. IdealLoad)
    }


def validate_geometries(
    geometries: list[BuildingGeometry],
    archetypes: dict,
    schedules: dict,
    system_templates: dict | None = None,
) -> list[dict]:
    """Check every building's references and basic geometry sanity.

    Parameters
    ----------
    geometries : list of BuildingGeometry
        Parsed building geometries (GeoJSON route or built directly).
    archetypes, schedules : dict
        Loaded envelope archetype and end-use schedule databases.
    system_templates : dict, optional
        Loaded HVAC template database; without it, template codes are
        expected to fall back to IdealLoad and are reported as warnings.

    Returns
    -------
    list of dict
        Issues (``building``, ``field``, ``value``, ``message``,
        ``severity``), errors first. Empty list = all clear.
    """
    issues: list[dict] = []
    seen_names: set[str] = set()
    for g in geometries:
        if g.name in seen_names:
            issues.append(
                _issue(g.name, "Name", g.name, "duplicate building name (results overwrite each other)", "error")
            )
        seen_names.add(g.name)

        if g.envelope not in archetypes:
            issues.append(
                _issue(
                    g.name, "Envelope", g.envelope,
                    f"envelope archetype not in database; available: {sorted(archetypes)}",
                    "error",
                )
            )
        for zone in g.zones:
            if zone.end_use not in schedules:
                field_name = "End Use" if zone.zone_label == "single" else f"{zone.zone_label.capitalize()} End Use"
                issues.append(
                    _issue(
                        g.name, field_name, zone.end_use,
                        f"end use not in schedule database; available: {sorted(schedules)}",
                        "error",
                    )
                )
        for field, name, resolver in (
            ("Heating System", g.heating_system, resolve_heating_system),
            ("Cooling System", g.cooling_system, resolve_cooling_system),
        ):
            _, warning = resolver(name, system_templates)
            if warning:
                issues.append(_issue(g.name, field, name, warning, "warning"))
        for tag in filter(None, (t.strip().lower() for t in g.solar_technologies.replace(";", ",").split(","))):
            if tag not in _KNOWN_SOLAR_TAGS:
                issues.append(
                    _issue(g.name, "Solar technologies", g.solar_technologies,
                           f"unknown solar technology tag '{tag}' (known: PV, ST)", "warning")
                )
        if g.footprint_area <= 0.0:
            issues.append(_issue(g.name, "geometry", g.footprint_area, "non-positive footprint area", "error"))
        if g.height <= 0.0 or g.n_floors < 1:
            issues.append(
                _issue(g.name, "geometry", (g.height, g.n_floors),
                       "invalid height / floor count", "error")
            )
        elif g.height / g.n_floors < 2.0 or g.height / g.n_floors > 6.0:
            issues.append(
                _issue(g.name, "geometry", round(g.height / g.n_floors, 2),
                       "storey height outside 2-6 m; Height must be the total "
                       "building height (check Height/Floors attributes)", "error")
            )
    return sorted(issues, key=lambda i: (i["severity"] != "error", i["building"]))


def validate_district_inputs(
    geojson_path: str | Path,
    archetypes_path: str | Path,
    schedules_path: str | Path,
    systems_path: str | Path | None = None,
) -> list[dict]:
    """Pre-flight check of the raw input files (GeoJSON route).

    Loads the databases, parses the GeoJSON and cross-checks every
    reference — call this before ``preprocess_district`` to get all
    problems in one report instead of one failure at a time.

    Parameters
    ----------
    geojson_path, archetypes_path, schedules_path : str or pathlib.Path
        The raw input files.
    systems_path : str or pathlib.Path, optional
        HVAC system template database.

    Returns
    -------
    list of dict
        See :func:`validate_geometries`.
    """
    geometries = load_district_geojson(geojson_path)
    archetypes = load_envelope_archetypes(archetypes_path)
    schedules = load_end_use_schedules(schedules_path)
    templates = load_system_templates(systems_path) if systems_path is not None else None
    return validate_geometries(geometries, archetypes, schedules, templates)


def validate_district(district: DistrictInput) -> list[dict]:
    """Validate an already-preprocessed :class:`DistrictInput` (both input
    routes): system-name resolution against its own template database plus
    geometry sanity. Envelope/end-use references are already bound at this
    stage (assembly would have raised otherwise).

    Parameters
    ----------
    district : DistrictInput
        Output of ``preprocess_geometries`` / ``preprocess_district``.

    Returns
    -------
    list of dict
        See :func:`validate_geometries`.
    """
    geometries = [b.geometry for b in district.buildings]
    archetypes = {b.geometry.envelope: b.envelope for b in district.buildings}
    schedules = {
        zone.geometry.end_use: zone.schedule for b in district.buildings for zone in b.zones
    }
    return validate_geometries(geometries, archetypes, schedules, district.system_templates)
