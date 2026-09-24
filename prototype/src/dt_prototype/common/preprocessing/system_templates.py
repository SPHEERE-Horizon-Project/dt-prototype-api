"""HVAC system template database (FR-05 companion).

Migrated from ``reference_ubem.systems_templates.load_system_templates`` /
``Systems.xlsx``: short template names (``s1`` .. ``s39``) mapped to explicit
EN 15316-style efficiency-chain parameters. GeoJSON ``Heating System`` /
``Cooling System`` attributes are matched against these templates *before*
the descriptive catalog-name parsing of ``dt_prototype.dynamic.simulation.systems`` —
only names found in neither fall back to ``IdealLoad``.

This module only loads and validates the JSON database (a plain dict); the
system objects themselves are built in the simulation layer, keeping the
layer dependency direction intact (NFR-01).
"""

from __future__ import annotations

import json
from pathlib import Path

# required numeric fields per template kind (defaults applied when missing)
_HEATING_DEFAULTS = {
    "convective_fraction": 0.65,
    "emission_efficiency": 1.0,
    "distribution_efficiency": 1.0,
    "regulation_efficiency": 1.0,
    "generation_efficiency": 1.0,
    "cop": None,
    "fuel": "gas",
    "dhw_emission_efficiency": 1.0,
    "dhw_distribution_efficiency": 1.0,
    "dhw_regulation_efficiency": 1.0,
    "dhw_generation_efficiency": 1.0,
    "dhw_cop": None,
    "dhw_fuel": "gas",
}
_COOLING_DEFAULTS = {
    "convective_fraction": 1.0,
    "emission_efficiency": 1.0,
    "distribution_efficiency": 1.0,
    "regulation_efficiency": 1.0,
    "eer": 2.5,
    "fuel": "electric",
}
_FUELS = ("gas", "electric", "district_heat", "other_fuel")


def load_system_templates(path: str | Path) -> dict[str, dict[str, dict]]:
    """Load and validate a system template JSON database.

    See ``data/examples/systems_templates.json`` for the schema (one entry
    per template under ``heating_systems`` / ``cooling_systems``; unknown
    numeric fields get conservative defaults).

    Parameters
    ----------
    path : str or pathlib.Path
        JSON template database.

    Returns
    -------
    dict
        ``{"heating_systems": {name: params}, "cooling_systems": {...}}``
        with defaults applied — the plain-dict currency consumed by
        ``dt_prototype.dynamic.simulation.systems``.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, dict[str, dict]] = {"heating_systems": {}, "cooling_systems": {}}
    for kind, defaults in (
        ("heating_systems", _HEATING_DEFAULTS),
        ("cooling_systems", _COOLING_DEFAULTS),
    ):
        for name, params in data.get(kind, {}).items():
            if name.startswith("_"):  # comment keys
                continue
            entry = {**defaults, **{k: v for k, v in params.items() if v is not None or k in params}}
            fuel = entry.get("fuel", defaults["fuel"])
            if fuel not in _FUELS:
                raise ValueError(
                    f"System template '{name}': unknown fuel '{fuel}'; allowed: {_FUELS}"
                )
            out[kind][name] = entry
    return out
