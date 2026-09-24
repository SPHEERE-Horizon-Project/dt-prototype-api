"""Normalized CSV input for simulation-ready building geometry.

The adapter stores the same :class:`BuildingGeometry` information consumed by
the engines in three tables.  It intentionally stores derived heat-exchange
surfaces rather than polygon coordinates, so a tabular dataset can reproduce
a previously prepared GeoJSON case without performing geometry extraction.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

from .geometry import BuildingGeometry, SurfaceSpec, ZoneGeometry


TABLE_FILENAMES = ("buildings.csv", "zones.csv", "surfaces.csv")

BUILDING_FIELDS = (
    "building_id",
    "building_name",
    "envelope",
    "heating_system",
    "cooling_system",
    "solar_technologies",
    "n_floors",
    "height_m",
    "footprint_area_m2",
)
ZONE_FIELDS = (
    "building_id",
    "zone_id",
    "zone_name",
    "end_use",
    "n_floors",
    "net_floor_area_m2",
    "volume_m3",
)
SURFACE_FIELDS = (
    "building_id",
    "zone_id",
    "surface_index",
    "surface_type",
    "area_m2",
    "azimuth_deg",
    "tilt_deg",
)


def _read_rows(path: Path, required_fields: tuple[str, ...]) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = set(required_fields) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path}: table must contain at least one row")
    return rows


def _text(row: dict[str, str], field: str, source: Path, row_number: int) -> str:
    raw = row.get(field)
    value = "" if raw is None else str(raw).strip()
    if not value:
        raise ValueError(f"{source}:{row_number}: {field} must not be empty")
    return value


def _number(
    row: dict[str, str], field: str, source: Path, row_number: int, *, positive: bool = False
) -> float:
    raw = _text(row, field, source, row_number)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{source}:{row_number}: {field} must be numeric") from exc
    if not math.isfinite(value) or (positive and value <= 0):
        qualifier = "positive and finite" if positive else "finite"
        raise ValueError(f"{source}:{row_number}: {field} must be {qualifier}")
    return value


def _integer(
    row: dict[str, str], field: str, source: Path, row_number: int, *, minimum: int = 0
) -> int:
    value = _number(row, field, source, row_number)
    if not value.is_integer() or value < minimum:
        raise ValueError(f"{source}:{row_number}: {field} must be an integer >= {minimum}")
    return int(value)


def load_district_tables(directory: str | Path) -> list[BuildingGeometry]:
    """Load ``buildings.csv``, ``zones.csv`` and ``surfaces.csv``.

    Rows are joined by stable ``building_id`` and ``zone_id`` keys.  File row
    order is retained for buildings and zones; ``surface_index`` defines the
    surface order within each zone.  References, uniqueness and core numeric
    ranges are checked before any geometry objects are returned.
    """

    directory = Path(directory)
    building_path = directory / TABLE_FILENAMES[0]
    zone_path = directory / TABLE_FILENAMES[1]
    surface_path = directory / TABLE_FILENAMES[2]
    building_rows = _read_rows(building_path, BUILDING_FIELDS)
    zone_rows = _read_rows(zone_path, ZONE_FIELDS)
    surface_rows = _read_rows(surface_path, SURFACE_FIELDS)

    building_ids: set[str] = set()
    building_names: set[str] = set()
    zone_rows_by_building: dict[str, list[tuple[str, dict[str, str], int]]] = defaultdict(list)
    zone_keys: set[tuple[str, str]] = set()

    for row_number, row in enumerate(zone_rows, start=2):
        building_id = _text(row, "building_id", zone_path, row_number)
        zone_id = _text(row, "zone_id", zone_path, row_number)
        key = (building_id, zone_id)
        if key in zone_keys:
            raise ValueError(f"{zone_path}:{row_number}: duplicate zone key {key}")
        zone_keys.add(key)
        zone_rows_by_building[building_id].append((zone_id, row, row_number))

    surfaces_by_zone: dict[tuple[str, str], list[tuple[int, SurfaceSpec]]] = defaultdict(list)
    surface_keys: set[tuple[str, str, int]] = set()
    for row_number, row in enumerate(surface_rows, start=2):
        building_id = _text(row, "building_id", surface_path, row_number)
        zone_id = _text(row, "zone_id", surface_path, row_number)
        zone_key = (building_id, zone_id)
        if zone_key not in zone_keys:
            raise ValueError(f"{surface_path}:{row_number}: unknown zone key {zone_key}")
        surface_index = _integer(row, "surface_index", surface_path, row_number, minimum=0)
        surface_key = (building_id, zone_id, surface_index)
        if surface_key in surface_keys:
            raise ValueError(f"{surface_path}:{row_number}: duplicate surface key {surface_key}")
        surface_keys.add(surface_key)
        surfaces_by_zone[zone_key].append(
            (
                surface_index,
                SurfaceSpec(
                    surface_type=_text(row, "surface_type", surface_path, row_number),
                    area=_number(row, "area_m2", surface_path, row_number, positive=True),
                    azimuth=_number(row, "azimuth_deg", surface_path, row_number),
                    tilt=_number(row, "tilt_deg", surface_path, row_number),
                ),
            )
        )

    geometries: list[BuildingGeometry] = []
    for row_number, row in enumerate(building_rows, start=2):
        building_id = _text(row, "building_id", building_path, row_number)
        building_name = _text(row, "building_name", building_path, row_number)
        if building_id in building_ids:
            raise ValueError(f"{building_path}:{row_number}: duplicate building_id {building_id!r}")
        if building_name in building_names:
            raise ValueError(f"{building_path}:{row_number}: duplicate building_name {building_name!r}")
        building_ids.add(building_id)
        building_names.add(building_name)
        if building_id not in zone_rows_by_building:
            raise ValueError(f"{building_path}:{row_number}: building has no zones")

        zones: list[ZoneGeometry] = []
        for zone_id, zone_row, zone_row_number in zone_rows_by_building[building_id]:
            zone_key = (building_id, zone_id)
            ordered_surfaces = sorted(surfaces_by_zone.get(zone_key, []), key=lambda item: item[0])
            if not ordered_surfaces:
                raise ValueError(f"{zone_path}:{zone_row_number}: zone has no surfaces")
            zones.append(
                ZoneGeometry(
                    name=_text(zone_row, "zone_name", zone_path, zone_row_number),
                    zone_label=zone_id,
                    end_use=_text(zone_row, "end_use", zone_path, zone_row_number),
                    n_floors=_integer(
                        zone_row, "n_floors", zone_path, zone_row_number, minimum=1
                    ),
                    net_floor_area=_number(
                        zone_row,
                        "net_floor_area_m2",
                        zone_path,
                        zone_row_number,
                        positive=True,
                    ),
                    volume=_number(
                        zone_row, "volume_m3", zone_path, zone_row_number, positive=True
                    ),
                    surfaces=[surface for _, surface in ordered_surfaces],
                )
            )

        geometries.append(
            BuildingGeometry(
                name=building_name,
                building_id=building_id,
                envelope=_text(row, "envelope", building_path, row_number),
                heating_system=_text(row, "heating_system", building_path, row_number),
                cooling_system=_text(row, "cooling_system", building_path, row_number),
                solar_technologies=str(row.get("solar_technologies", "")).strip(),
                n_floors=_integer(row, "n_floors", building_path, row_number, minimum=1),
                height=_number(row, "height_m", building_path, row_number, positive=True),
                footprint_area=_number(
                    row, "footprint_area_m2", building_path, row_number, positive=True
                ),
                zones=zones,
            )
        )

    orphan_zone_buildings = set(zone_rows_by_building) - building_ids
    if orphan_zone_buildings:
        raise ValueError(f"{zone_path}: zones reference unknown buildings {sorted(orphan_zone_buildings)}")
    return geometries


def write_district_tables(
    geometries: BuildingGeometry | list[BuildingGeometry], directory: str | Path
) -> None:
    """Write canonical geometry objects to the three normalized CSV tables."""

    if isinstance(geometries, BuildingGeometry):
        geometries = [geometries]
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = [directory / filename for filename in TABLE_FILENAMES]
    if any(path.exists() for path in paths):
        existing = [path.name for path in paths if path.exists()]
        raise FileExistsError(f"Refusing to overwrite existing geometry tables: {existing}")

    with paths[0].open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=BUILDING_FIELDS)
        writer.writeheader()
        for geometry in geometries:
            writer.writerow(
                {
                    "building_id": geometry.building_id,
                    "building_name": geometry.name,
                    "envelope": geometry.envelope,
                    "heating_system": geometry.heating_system,
                    "cooling_system": geometry.cooling_system,
                    "solar_technologies": geometry.solar_technologies,
                    "n_floors": geometry.n_floors,
                    "height_m": repr(geometry.height),
                    "footprint_area_m2": repr(geometry.footprint_area),
                }
            )

    with paths[1].open("w", encoding="utf-8", newline="") as zone_stream, paths[
        2
    ].open("w", encoding="utf-8", newline="") as surface_stream:
        zone_writer = csv.DictWriter(zone_stream, fieldnames=ZONE_FIELDS)
        surface_writer = csv.DictWriter(surface_stream, fieldnames=SURFACE_FIELDS)
        zone_writer.writeheader()
        surface_writer.writeheader()
        for geometry in geometries:
            for zone in geometry.zones:
                zone_writer.writerow(
                    {
                        "building_id": geometry.building_id,
                        "zone_id": zone.zone_label,
                        "zone_name": zone.name,
                        "end_use": zone.end_use,
                        "n_floors": zone.n_floors,
                        "net_floor_area_m2": repr(zone.net_floor_area),
                        "volume_m3": repr(zone.volume),
                    }
                )
                for surface_index, surface in enumerate(zone.surfaces):
                    surface_writer.writerow(
                        {
                            "building_id": geometry.building_id,
                            "zone_id": zone.zone_label,
                            "surface_index": surface_index,
                            "surface_type": surface.surface_type,
                            "area_m2": repr(surface.area),
                            "azimuth_deg": repr(surface.azimuth),
                            "tilt_deg": repr(surface.tilt),
                        }
                    )
