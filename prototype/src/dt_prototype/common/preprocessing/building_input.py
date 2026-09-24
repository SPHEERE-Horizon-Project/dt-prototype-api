"""Assembly and serialisation of simulation-ready building inputs (FR-08).

This module is the explicit preprocessing → simulation handoff: it combines
geometry (FR-06), envelope archetypes (FR-07) and end-use schedules (FR-05)
into one :class:`BuildingInput` per building, fully serialisable to JSON, and
writes the processed weather to CSV. The simulation layer consumes only these
artefacts — the pipeline is inspectable at every stage (NFR-03).
"""

from __future__ import annotations

import dataclasses
import json
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from dt_prototype.common.preprocessing.dhw_stochastic import stochastic_dhw_profile

from dt_prototype.common.preprocessing.archetypes import (
    EnvelopeArchetype,
    load_envelope_archetypes,
)
from dt_prototype.common.preprocessing.geometry import (
    BuildingGeometry,
    ZoneGeometry,
    load_district_geojson,
)
from dt_prototype.common.preprocessing.tabular_geometry import load_district_tables
from dt_prototype.common.preprocessing.schedules import EndUseSchedule, load_end_use_schedules
from dt_prototype.common.preprocessing.system_templates import load_system_templates
from dt_prototype.common.preprocessing.weather import WeatherData, process_epw


@dataclass
class ZoneInput:
    """Complete, simulation-ready description of one thermal zone.

    Pairs a :class:`~dt_prototype.common.preprocessing.geometry.ZoneGeometry` with the
    envelope archetype and end-use schedule resolved for it. A
    :class:`BuildingInput` holds one or two of these (see the two-zone
    convention documented in ``preprocessing.geometry``).
    """

    geometry: ZoneGeometry
    envelope: EnvelopeArchetype
    schedule: EndUseSchedule

    @property
    def name(self) -> str:
        """Zone name (from geometry)."""
        return self.geometry.name


@dataclass(init=False)
class BuildingInput:
    """Complete, serialised, simulation-ready description of one building.

    The atomic unit of simulation (FR-01): geometry + one or two
    :class:`ZoneInput` (envelope + schedule per zone). Weather is shared
    across buildings and serialised separately.

    ``envelope``/``schedule`` are compatibility accessors returning the
    primary zone's (``zones[0]`` — the single zone, or the "upper" zone of a
    two-zone building) values, for code that is deliberately building-level
    (e.g. design-day sizing, the quasi-steady-state method).
    """

    geometry: BuildingGeometry
    zones: list[ZoneInput] = field(default_factory=list)

    def __init__(
        self,
        geometry: BuildingGeometry,
        envelope: EnvelopeArchetype | None = None,
        schedule: EndUseSchedule | None = None,
        zones: list[ZoneInput] | None = None,
    ) -> None:
        """Create a zoned building input, accepting CURRENT's flat API.

        Passing ``geometry, envelope, schedule`` constructs a single-zone
        input exactly as in the prior CURRENT version. Passing ``zones`` is
        the canonical one/two-zone form used by preprocessing and simulation.
        """
        self.geometry = geometry
        if zones is not None:
            if envelope is not None or schedule is not None:
                raise TypeError("pass either zones or envelope/schedule, not both")
            if not zones:
                raise ValueError(f"BuildingInput '{geometry.name}' must contain at least one zone")
            self.zones = list(zones)
            return
        if envelope is None or schedule is None:
            raise TypeError("envelope and schedule are required when zones is not provided")
        if len(geometry.zones) != 1:
            raise ValueError(
                f"Flat BuildingInput construction requires one geometry zone; "
                f"'{geometry.name}' has {len(geometry.zones)}"
            )
        self.zones = [ZoneInput(geometry.zones[0], envelope, schedule)]

    @property
    def name(self) -> str:
        """Building name (from geometry)."""
        return self.geometry.name

    @property
    def envelope(self) -> EnvelopeArchetype:
        """Envelope archetype (shared by every zone of the building)."""
        return self.zones[0].envelope

    @property
    def schedule(self) -> EndUseSchedule:
        """Primary (single, or upper) zone's end-use schedule."""
        return self.zones[0].schedule

    @classmethod
    def single_zone(
        cls, geometry: BuildingGeometry, envelope: EnvelopeArchetype, schedule: EndUseSchedule
    ) -> "BuildingInput":
        """Backward-compatible constructor for a single-zone building input
        (``geometry.zones`` must have exactly one entry)."""
        if len(geometry.zones) != 1:
            raise ValueError(
                f"BuildingInput.single_zone: '{geometry.name}' has {len(geometry.zones)} "
                "zones, expected exactly 1"
            )
        return cls(geometry=geometry, zones=[ZoneInput(geometry.zones[0], envelope, schedule)])

    def to_json(self, path: str | Path) -> None:
        """Serialise this building input to a single JSON file (FR-08)."""
        payload = {
            "geometry": self.geometry.to_dict(),
            "envelope": self.envelope.to_dict(),  # one shared copy across zones
            "schedules": [z.schedule.to_dict() for z in self.zones],
        }
        Path(path).write_text(json.dumps(payload), encoding="utf-8")

    @classmethod
    def from_json(cls, path: str | Path) -> "BuildingInput":
        """Load canonical zoned or legacy flat CURRENT serialisation."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        geometry = BuildingGeometry.from_dict(payload["geometry"])
        envelope = EnvelopeArchetype.from_dict(payload["envelope"])
        schedule_payloads = payload.get("schedules")
        if schedule_payloads is None:
            schedule_payloads = [payload["schedule"]]
        schedules = [EndUseSchedule.from_dict(s) for s in schedule_payloads]
        if len(schedules) != len(geometry.zones):
            raise ValueError(
                f"Serialised building '{geometry.name}' has {len(geometry.zones)} zones "
                f"but {len(schedules)} schedules"
            )
        zones = [
            ZoneInput(geometry=zg, envelope=envelope, schedule=sched)
            for zg, sched in zip(geometry.zones, schedules)
        ]
        return cls(geometry=geometry, zones=zones)


@dataclass
class DistrictInput:
    """A preprocessed district/portfolio: shared weather + one input per
    building (FR-02) + the shared HVAC template database.

    Returned by :func:`preprocess_geometries`, :func:`preprocess_district` or
    :func:`preprocess_tabular_district`.
    Run a pre-flight reference check with
    ``dt_prototype.dynamic.validation.validate_district`` before simulating.
    """

    weather: WeatherData
    buildings: list[BuildingInput] = field(default_factory=list)
    # HVAC system template database ("s1".."s39" → parameters), consumed by
    # the simulation runner when resolving configured system names
    system_templates: dict | None = None

    @property
    def building_names(self) -> list[str]:
        """Names of all buildings in the district."""
        return [b.name for b in self.buildings]


def assemble_building_input(
    geometry: BuildingGeometry,
    archetypes: dict[str, EnvelopeArchetype],
    schedules: dict[str, EndUseSchedule],
) -> BuildingInput:
    """Bind one building geometry to its envelope archetype and, per zone,
    its end-use schedule, by the names in the canonical geometry.

    Parameters
    ----------
    geometry : BuildingGeometry
        Parsed building geometry (``envelope`` selects the archetype, shared
        by every zone; each zone's own ``end_use`` selects its schedule).
    archetypes : dict
        Envelope archetype database (:func:`load_envelope_archetypes`).
    schedules : dict
        End-use schedule database (:func:`load_end_use_schedules`).

    Returns
    -------
    BuildingInput

    Raises
    ------
    KeyError
        If the referenced envelope or any zone's end use is not in the
        databases.
    """
    if geometry.envelope not in archetypes:
        raise KeyError(
            f"Building '{geometry.name}': envelope archetype '{geometry.envelope}' not found; "
            f"available: {sorted(archetypes)}"
        )
    envelope = archetypes[geometry.envelope]

    zones = []
    for zone_geometry in geometry.zones:
        if zone_geometry.end_use not in schedules:
            raise KeyError(
                f"Building '{geometry.name}' zone '{zone_geometry.name}' "
                f"({zone_geometry.zone_label}): end use '{zone_geometry.end_use}' not found; "
                f"available: {sorted(schedules)}"
            )
        schedule = schedules[zone_geometry.end_use]

        # EXTENDED: stochastic DHW draw-offs are zone-specific (they depend
        # on the absolute volume and number of dwellings), so the shared
        # end-use schedule is replaced by a per-zone copy here. The seed
        # derives from the building id AND the zone label, so a two-zone
        # building's upper/lower zones get distinct (not identical) draw
        # profiles despite potentially sharing the same schedule entry.
        if schedule.dhw_method == "stochastic" and schedule.dhw_volume_per_m2_day > 0.0:
            nfa = zone_geometry.net_floor_area
            n_units = max(1, int(round(nfa / 80.0)))  # ~one dwelling per 80 m2
            daily_total_m3 = schedule.dhw_volume_per_m2_day * nfa / 1000.0
            steps = max(1, len(schedule.heating_setpoint) // 8760)
            profile = stochastic_dhw_profile(
                daily_volume_m3=daily_total_m3 / n_units,
                n_units=n_units,
                time_steps_per_hour=steps,
                seed=zlib.crc32(f"{geometry.building_id}:{zone_geometry.zone_label}".encode()),
            )
            schedule = dataclasses.replace(schedule, dhw_volume_flow=profile / nfa)

        zones.append(ZoneInput(geometry=zone_geometry, envelope=envelope, schedule=schedule))

    return BuildingInput(geometry=geometry, zones=zones)


def preprocess_geometries(
    geometries: BuildingGeometry | list[BuildingGeometry],
    epw_path: str | Path,
    archetypes_path: str | Path,
    schedules_path: str | Path,
    systems_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    year: int = 2023,
    time_steps_per_hour: int = 1,
    azimuth_subdivisions: int = 8,
) -> DistrictInput:
    """Core preprocessing pipeline over already-built geometries
    (FR-05..FR-08).

    This is the single entry point behind every geometry route — the same call
    handles one building or ten thousand:

    - **GeoJSON route**: :func:`preprocess_district` parses the file and
      delegates here;
    - **tabular route**: :func:`preprocess_tabular_district` validates and
      joins normalized CSV files, then delegates here;
    - **direct route**: build :class:`BuildingGeometry` objects yourself
      (e.g. with ``geometry.simple_building_geometry``) and pass them in —
      no GeoJSON file needed (FR-01).

    Parameters
    ----------
    geometries : BuildingGeometry or list of BuildingGeometry
        One or more building geometries.
    epw_path : str or pathlib.Path
        EPW weather file.
    archetypes_path : str or pathlib.Path
        Envelope archetype JSON database.
    schedules_path : str or pathlib.Path
        End-use schedule JSON database.
    systems_path : str or pathlib.Path, optional
        HVAC system template JSON database (the retained reference ``Systems.xlsx``
        equivalent). Without it, only descriptive catalog names resolve and
        short template codes fall back to IdealLoad.
    output_dir : str or pathlib.Path, optional
        If given, writes ``weather.csv`` (+ ``weather.meta.json``),
        ``buildings/<name>.json`` and a copy of the system template database
        there, making the handoff inspectable (NFR-03).
    year : int
        Reference year for the time index and weekday pattern.
    time_steps_per_hour : int
        Temporal resolution (FR-12).
    azimuth_subdivisions : int
        Solar irradiance azimuth bins.

    Returns
    -------
    DistrictInput
    """
    if isinstance(geometries, BuildingGeometry):
        geometries = [geometries]
    weather = process_epw(
        epw_path,
        year=year,
        time_steps_per_hour=time_steps_per_hour,
        azimuth_subdivisions=azimuth_subdivisions,
    )
    archetypes = load_envelope_archetypes(archetypes_path)
    schedules = load_end_use_schedules(
        schedules_path, year=year, time_steps_per_hour=time_steps_per_hour
    )
    templates = load_system_templates(systems_path) if systems_path is not None else None
    buildings = [
        assemble_building_input(geometry, archetypes, schedules)
        for geometry in geometries
    ]

    if output_dir is not None:
        output_dir = Path(output_dir)
        (output_dir / "buildings").mkdir(parents=True, exist_ok=True)
        weather.to_csv(output_dir / "weather.csv")
        for b in buildings:
            b.to_json(output_dir / "buildings" / f"{b.name}.json")
        if templates is not None:
            (output_dir / "system_templates.json").write_text(
                json.dumps(templates, indent=2), encoding="utf-8"
            )

    return DistrictInput(weather=weather, buildings=buildings, system_templates=templates)


def preprocess_district(
    geojson_path: str | Path,
    epw_path: str | Path,
    archetypes_path: str | Path,
    schedules_path: str | Path,
    systems_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    year: int = 2023,
    time_steps_per_hour: int = 1,
    azimuth_subdivisions: int = 8,
) -> DistrictInput:
    """GeoJSON route of the preprocessing pipeline: parse the district file,
    then delegate to :func:`preprocess_geometries` (FR-05..FR-08, FR-06).

    Parameters
    ----------
    geojson_path : str or pathlib.Path
        District GeoJSON (projected CRS, metres).
    epw_path, archetypes_path, schedules_path, systems_path, output_dir,
    year, time_steps_per_hour, azimuth_subdivisions
        See :func:`preprocess_geometries`.

    Returns
    -------
    DistrictInput
    """
    return preprocess_geometries(
        load_district_geojson(geojson_path),
        epw_path=epw_path,
        archetypes_path=archetypes_path,
        schedules_path=schedules_path,
        systems_path=systems_path,
        output_dir=output_dir,
        year=year,
        time_steps_per_hour=time_steps_per_hour,
        azimuth_subdivisions=azimuth_subdivisions,
    )


def preprocess_tabular_district(
    geometry_directory: str | Path,
    epw_path: str | Path,
    archetypes_path: str | Path,
    schedules_path: str | Path,
    systems_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    year: int = 2023,
    time_steps_per_hour: int = 1,
    azimuth_subdivisions: int = 8,
) -> DistrictInput:
    """Tabular route using normalized building, zone and surface CSV files."""

    return preprocess_geometries(
        load_district_tables(geometry_directory),
        epw_path=epw_path,
        archetypes_path=archetypes_path,
        schedules_path=schedules_path,
        systems_path=systems_path,
        output_dir=output_dir,
        year=year,
        time_steps_per_hour=time_steps_per_hour,
        azimuth_subdivisions=azimuth_subdivisions,
    )
