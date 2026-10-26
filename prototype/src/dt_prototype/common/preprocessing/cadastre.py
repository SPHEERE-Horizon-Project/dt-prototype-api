"""Conservative cadastral-to-simulation preprocessing.

The module turns sparse building-footprint GeoJSON into the normalized
``buildings.csv`` / ``zones.csv`` / ``surfaces.csv`` contract used by every
DT-Prototype engine.  Archetype selection is declarative: a small JSON rule
catalogue maps available cadastral attributes to envelope-library keys while
retaining the source and source-archetype identifiers in an audit report.

One thermal zone is the default.  The existing upper/lower two-zone
representation is emitted only when the input explicitly declares a distinct
ground-floor use and the building has at least two storeys.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .geometry import BuildingGeometry, building_geometry_from_feature
from .tabular_geometry import write_district_tables


SCHEMA_VERSION = "1.0"

DEFAULT_PROPERTY_ALIASES: dict[str, list[str]] = {
    "building_id": ["building_id", "id", "cadastral_id", "gml_id", "fid"],
    "building_name": ["building_name", "name", "nome"],
    "construction_year": [
        "construction_year",
        "year",
        "year_built",
        "anno_costruzione",
    ],
    "use": ["use", "building_use", "end_use", "Upper End Use", "destinazione_uso"],
    "ground_floor_use": [
        "ground_floor_use",
        "lower_end_use",
        "Lower End Use",
        "uso_piano_terra",
    ],
    "building_type": ["building_type", "type", "typology", "tipologia"],
    "region": ["region", "regione"],
    "climate_zone": ["climate_zone", "zona_climatica"],
    "envelope": ["envelope", "envelope_archetype", "archetipo_involucro"],
    "height_m": ["height_m", "height", "altezza", "measuredheight"],
    "n_floors": ["n_floors", "floors", "storeys", "levels", "numero_piani"],
    "ext_wall_coeff": ["ext_wall_coeff", "ExtWallCoeff"],
    "volume_coeff": ["volume_coeff", "VolCoeff"],
    "heating_system": ["heating_system", "impianto_riscaldamento"],
    "cooling_system": ["cooling_system", "impianto_raffrescamento"],
    "solar_technologies": ["solar_technologies", "tecnologie_solari"],
}


@dataclass(frozen=True)
class ArchetypeChoice:
    envelope: str
    rule_id: str
    source: str
    source_archetype: str
    specificity: int
    used_fallback: bool = False


def _normalise(value: Any) -> str:
    return " ".join(str(value).strip().lower().replace("_", " ").replace("-", " ").split())


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_number(value: Any, field: str, building_id: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"Building {building_id!r}: {field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Building {building_id!r}: {field} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"Building {building_id!r}: {field} must be finite")
    return number


def _positive_number(value: Any, field: str, building_id: str) -> float:
    number = _finite_number(value, field, building_id)
    if number <= 0:
        raise ValueError(f"Building {building_id!r}: {field} must be positive")
    return number


def _positive_integer(value: Any, field: str, building_id: str) -> int:
    number = _positive_number(value, field, building_id)
    if not number.is_integer():
        raise ValueError(f"Building {building_id!r}: {field} must be an integer")
    return int(number)


def _aliases(configuration: dict) -> dict[str, list[str]]:
    aliases = {key: list(values) for key, values in DEFAULT_PROPERTY_ALIASES.items()}
    for field, values in configuration.get("property_aliases", {}).items():
        if field not in aliases:
            raise ValueError(f"Unknown property_aliases field {field!r}")
        if not isinstance(values, list) or not values or not all(
            isinstance(value, str) and value.strip() for value in values
        ):
            raise ValueError(f"property_aliases.{field} must be a nonempty string list")
        aliases[field] = values + [value for value in aliases[field] if value not in values]
    return aliases


def _property(properties: dict, aliases: dict[str, list[str]], field: str) -> Any:
    normalised = {_normalise(key): value for key, value in properties.items()}
    for alias in aliases[field]:
        key = _normalise(alias)
        if key in normalised and normalised[key] not in (None, ""):
            return normalised[key]
    return None


def _canonical_use(value: Any, use_map: dict[str, str], default: str) -> tuple[str, bool]:
    if value in (None, ""):
        return default, True
    key = _normalise(value)
    if key in use_map:
        return use_map[key], False
    return default, True


def _selector_matches(rule: dict, field: str, value: str | None) -> tuple[bool, int]:
    values = rule.get(field, ["*"])
    if not isinstance(values, list) or not values:
        raise ValueError(f"Rule {rule.get('id', '?')!r}: {field} must be a nonempty list")
    normalised = {_normalise(item) for item in values}
    if "*" in normalised:
        return True, 0
    if value is None:
        return False, 0
    return (_normalise(value) in normalised, 1)


def _select_archetype(
    configuration: dict,
    *,
    year: int | None,
    end_use: str,
    building_type: str | None,
    region: str | None,
    climate_zone: str | None,
) -> ArchetypeChoice:
    matches: list[tuple[int, int, dict]] = []
    for rule in configuration.get("rules", []):
        rule_id = rule.get("id", "?")
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise ValueError("Every archetype rule requires a nonempty id")
        specificity = 0
        for field, value in (
            ("end_uses", end_use),
            ("building_types", building_type),
            ("regions", region),
            ("climate_zones", climate_zone),
        ):
            matched, points = _selector_matches(rule, field, value)
            if not matched:
                break
            specificity += points
        else:
            year_min = rule.get("year_min")
            year_max = rule.get("year_max")
            if year_min is not None or year_max is not None:
                if year is None:
                    continue
                if year_min is not None and year < int(year_min):
                    continue
                if year_max is not None and year > int(year_max):
                    continue
                specificity += 1
            matches.append((int(rule.get("priority", 0)), specificity, rule))

    if not matches:
        defaults = configuration["defaults"]
        return ArchetypeChoice(
            envelope=str(defaults["envelope"]),
            rule_id="default",
            source=str(defaults.get("source", "local default")),
            source_archetype=str(defaults.get("source_archetype", defaults["envelope"])),
            specificity=0,
            used_fallback=True,
        )

    best_rank = max((priority, specificity) for priority, specificity, _ in matches)
    best = [rule for priority, specificity, rule in matches if (priority, specificity) == best_rank]
    if len(best) != 1:
        ids = sorted(str(rule["id"]) for rule in best)
        raise ValueError(f"Ambiguous archetype rules at rank {best_rank}: {ids}")
    rule = best[0]
    if not isinstance(rule.get("envelope"), str) or not rule["envelope"].strip():
        raise ValueError(f"Rule {rule['id']!r}: envelope must be nonempty")
    return ArchetypeChoice(
        envelope=rule["envelope"],
        rule_id=rule["id"],
        source=str(rule.get("source", "unspecified")),
        source_archetype=str(rule.get("source_archetype", rule["id"])),
        specificity=best_rank[1],
    )


def _load_configuration(path: Path) -> dict:
    configuration = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(configuration, dict) or configuration.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{path}: expected schema_version {SCHEMA_VERSION!r}")
    defaults = configuration.get("defaults")
    if not isinstance(defaults, dict):
        raise ValueError(f"{path}: defaults must be an object")
    required_defaults = {"envelope", "end_use", "storey_height_m", "n_floors"}
    missing = required_defaults - set(defaults)
    if missing:
        raise ValueError(f"{path}: missing defaults {sorted(missing)}")
    if _positive_number(defaults["storey_height_m"], "storey_height_m", "defaults") < 2:
        raise ValueError(f"{path}: defaults.storey_height_m must be at least 2 m")
    _positive_integer(defaults["n_floors"], "n_floors", "defaults")
    if not isinstance(configuration.get("use_map", {}), dict):
        raise ValueError(f"{path}: use_map must be an object")
    if not isinstance(configuration.get("rules", []), list):
        raise ValueError(f"{path}: rules must be a list")
    _aliases(configuration)
    return configuration


def _crs_assumption(source: dict) -> str | None:
    crs = source.get("crs")
    if crs is None:
        return "CRS not declared; coordinates assumed to be projected metres"
    text = json.dumps(crs).lower()
    if "4326" in text or "crs84" in text or "wgs84" in text or "wgs 84" in text:
        raise ValueError(
            "Cadastral GeoJSON uses a geographic CRS. Reproject footprints to a metric CRS first."
        )
    return None


def _make_feature(
    feature: dict,
    feature_index: int,
    configuration: dict,
    aliases: dict[str, list[str]],
) -> tuple[BuildingGeometry, dict[str, Any]]:
    properties = feature.get("properties") or {}
    raw_id = _property(properties, aliases, "building_id")
    if raw_id in (None, ""):
        raise ValueError(f"Feature {feature_index}: no building identifier found")
    building_id = str(raw_id).strip()
    raw_name = _property(properties, aliases, "building_name")
    building_name = str(raw_name).strip() if raw_name not in (None, "") else building_id

    defaults = configuration["defaults"]
    assumptions: list[str] = []

    raw_year = _property(properties, aliases, "construction_year")
    year = None
    if raw_year not in (None, ""):
        year_number = _finite_number(raw_year, "construction_year", building_id)
        if not year_number.is_integer() or not 1000 <= year_number <= 2200:
            raise ValueError(
                f"Building {building_id!r}: construction_year must be an integer from 1000 to 2200"
            )
        year = int(year_number)

    use_map = {
        _normalise(alias): str(canonical)
        for alias, canonical in configuration.get("use_map", {}).items()
    }
    default_end_use = str(defaults["end_use"])
    raw_use = _property(properties, aliases, "use")
    end_use, use_defaulted = _canonical_use(raw_use, use_map, default_end_use)
    if use_defaulted:
        assumptions.append(
            "primary use defaulted" if raw_use in (None, "") else f"unmapped primary use {raw_use!r} defaulted"
        )

    raw_type = _property(properties, aliases, "building_type")
    raw_region = _property(properties, aliases, "region")
    raw_climate = _property(properties, aliases, "climate_zone")
    raw_envelope = _property(properties, aliases, "envelope")
    if raw_envelope not in (None, ""):
        choice = ArchetypeChoice(
            envelope=str(raw_envelope).strip(),
            rule_id="source-property",
            source="building-specific source property",
            source_archetype=str(raw_envelope).strip(),
            specificity=5,
        )
    else:
        choice = _select_archetype(
            configuration,
            year=year,
            end_use=end_use,
            building_type=None if raw_type in (None, "") else str(raw_type),
            region=None if raw_region in (None, "") else str(raw_region),
            climate_zone=None if raw_climate in (None, "") else str(raw_climate),
        )
    if choice.used_fallback:
        assumptions.append("default envelope used: no archetype rule matched")

    raw_floors = _property(properties, aliases, "n_floors")
    raw_height = _property(properties, aliases, "height_m")
    if raw_floors not in (None, ""):
        n_floors = _positive_integer(raw_floors, "n_floors", building_id)
    else:
        n_floors = None
    if raw_height not in (None, ""):
        height = _positive_number(raw_height, "height_m", building_id)
    else:
        height = None

    storey_height = float(defaults["storey_height_m"])
    if n_floors is None and height is None:
        n_floors = int(defaults["n_floors"])
        height = n_floors * storey_height
        dimension_method = "default_floors_and_height"
        assumptions.append("floors and height defaulted")
    elif n_floors is None:
        n_floors = max(1, int(round(height / storey_height)))
        dimension_method = "floors_from_height"
        assumptions.append(f"floors inferred using {storey_height:g} m/storey")
    elif height is None:
        height = n_floors * storey_height
        dimension_method = "height_from_floors"
        assumptions.append(f"height inferred using {storey_height:g} m/storey")
    else:
        dimension_method = "reported_height_and_floors"

    mean_storey_height = height / n_floors
    if not 2.0 <= mean_storey_height <= 6.0:
        raise ValueError(
            f"Building {building_id!r}: height/floors gives an implausible "
            f"{mean_storey_height:.2f} m mean storey height"
        )

    raw_lower_use = _property(properties, aliases, "ground_floor_use")
    lower_use = None
    zoning_reason = "single zone: no explicit distinct ground-floor use"
    if raw_lower_use not in (None, ""):
        mapped_lower, lower_defaulted = _canonical_use(raw_lower_use, use_map, default_end_use)
        if lower_defaulted:
            assumptions.append(f"unmapped ground-floor use {raw_lower_use!r}; two-zone split suppressed")
            zoning_reason = "single zone: ground-floor use was not recognized"
        elif mapped_lower == end_use:
            zoning_reason = "single zone: ground-floor and primary uses are identical"
        elif n_floors < 2:
            zoning_reason = "single zone: a one-storey building cannot use the upper/lower split"
        else:
            lower_use = mapped_lower
            zoning_reason = "two zones: explicit distinct ground-floor use"

    props = {
        "id": building_id,
        "Name": building_name,
        "End Use": end_use,
        "Envelope": choice.envelope,
        "Height": height,
        "Floors": n_floors,
        "Heating System": str(
            _property(properties, aliases, "heating_system")
            or defaults.get("heating_system", "IdealLoad")
        ),
        "Cooling System": str(
            _property(properties, aliases, "cooling_system")
            or defaults.get("cooling_system", "IdealLoad")
        ),
        "Solar technologies": str(
            _property(properties, aliases, "solar_technologies")
            or defaults.get("solar_technologies", "")
        ),
        "ExtWallCoeff": _positive_number(
            1.0
            if _property(properties, aliases, "ext_wall_coeff") in (None, "")
            else _property(properties, aliases, "ext_wall_coeff"),
            "ext_wall_coeff",
            building_id,
        ),
        "VolCoeff": _positive_number(
            1.0
            if _property(properties, aliases, "volume_coeff") in (None, "")
            else _property(properties, aliases, "volume_coeff"),
            "volume_coeff",
            building_id,
        ),
    }
    if lower_use is not None:
        props["Upper End Use"] = end_use
        props["Lower End Use"] = lower_use

    normalised_feature = {
        "type": "Feature",
        "properties": props,
        "geometry": feature.get("geometry"),
    }
    geometry = building_geometry_from_feature(normalised_feature)
    confidence = "high"
    if choice.used_fallback or use_defaulted or dimension_method == "default_floors_and_height":
        confidence = "low"
    elif assumptions:
        confidence = "medium"

    report = {
        "building_id": building_id,
        "building_name": building_name,
        "source_feature_index": feature_index,
        "input_construction_year": "" if year is None else year,
        "input_use": "" if raw_use is None else raw_use,
        "input_building_type": "" if raw_type is None else raw_type,
        "input_region": "" if raw_region is None else raw_region,
        "input_climate_zone": "" if raw_climate is None else raw_climate,
        "assigned_envelope": choice.envelope,
        "archetype_rule_id": choice.rule_id,
        "archetype_source": choice.source,
        "source_archetype": choice.source_archetype,
        "assigned_primary_end_use": end_use,
        "zone_count": len(geometry.zones),
        "zoning_reason": zoning_reason,
        "n_floors": n_floors,
        "height_m": height,
        "dimension_method": dimension_method,
        "confidence": confidence,
        "assumptions": "; ".join(assumptions),
    }
    return geometry, report


def generate_cadastral_inputs(
    source_path: str | Path,
    rules_path: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    """Generate normalized simulation inputs and an audit trail.

    ``output_directory`` must not already exist.  It receives a ``geometry``
    subdirectory containing the three engine input tables, plus
    ``preprocessing_report.csv`` and ``preprocessing_manifest.json``.
    """

    source_path = Path(source_path).resolve()
    rules_path = Path(rules_path).resolve()
    output_directory = Path(output_directory).resolve()
    if output_directory.exists():
        raise FileExistsError(f"Refusing to overwrite existing output {output_directory}")
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if not rules_path.is_file():
        raise FileNotFoundError(rules_path)

    source = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(source, dict) or source.get("type") != "FeatureCollection":
        raise ValueError(f"{source_path}: expected a GeoJSON FeatureCollection")
    features = source.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError(f"{source_path}: FeatureCollection must contain features")
    crs_assumption = _crs_assumption(source)

    configuration = _load_configuration(rules_path)
    aliases = _aliases(configuration)
    geometries: list[BuildingGeometry] = []
    reports: list[dict[str, Any]] = []
    for feature_index, feature in enumerate(features, start=1):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError(f"Feature {feature_index}: expected a GeoJSON Feature")
        geometry, report = _make_feature(feature, feature_index, configuration, aliases)
        geometries.append(geometry)
        reports.append(report)

    ids = [geometry.building_id for geometry in geometries]
    names = [geometry.name for geometry in geometries]
    if len(ids) != len(set(ids)):
        raise ValueError("Cadastral input contains duplicate building identifiers")
    if len(names) != len(set(names)):
        raise ValueError("Cadastral input contains duplicate building names")

    geometry_directory = output_directory / "geometry"
    write_district_tables(geometries, geometry_directory)

    report_path = output_directory / "preprocessing_report.csv"
    with report_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(reports[0]))
        writer.writeheader()
        writer.writerows(reports)

    manifest = {
        "name": "DT-Prototype cadastral preprocessor",
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "source_geojson": str(source_path),
        "rules_catalogue": str(rules_path),
        "source_hash_sha256": _hash(source_path),
        "rules_hash_sha256": _hash(rules_path),
        "building_count": len(geometries),
        "single_zone_count": sum(len(geometry.zones) == 1 for geometry in geometries),
        "two_zone_count": sum(len(geometry.zones) == 2 for geometry in geometries),
        "low_confidence_count": sum(report["confidence"] == "low" for report in reports),
        "archetype_sources": sorted({report["archetype_source"] for report in reports}),
        "global_assumptions": [item for item in [crs_assumption] if item],
        "known_limitations": [
            "No automatic party-wall detection; every footprint edge is an external wall.",
            "Flat roofs are used by the DT-Prototype geometry contract.",
            "Window area is supplied by the selected envelope archetype's WWR, not cadastral geometry.",
            "The two-zone representation is an upper-use/ground-floor-use split, not core/perimeter zoning.",
        ],
        "outputs": {
            "geometry": str(geometry_directory),
            "report": str(report_path),
        },
    }
    manifest_path = output_directory / "preprocessing_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
