"""GeoJSON urban geometry ingestion (FR-02, FR-06).

Migrated from ``reference_ubem.city.buildings_creation_from_geojson`` and
``reference_building._geometry_auxiliary_functions``, simplified under the 80/20
rule: building footprints (Polygon/MultiPolygon, projected CRS in metres) are
extruded by their height attribute into one vertical external wall per
footprint edge, a flat roof and a ground floor. Urban mutual shading is not
migrated (extension point).

Expected GeoJSON feature properties (as in the retained reference's example district):
``id``, ``Name``, ``End Use``, ``Envelope``, ``Height`` [m], ``Floors``,
optional ``ExtWallCoeff`` and ``VolCoeff`` correction factors.

**Two-zone buildings** (the retained reference's convention): when the optional ``Upper End
Use`` / ``Lower End Use`` properties are present and differ, the building is
split into two independent :class:`ZoneGeometry` — "upper" (all floors above
the ground floor) and "lower" (the ground floor) — following the retained reference's own
method (``reference_ubem.city.buildings_creation_from_geojson``): vertical walls
are split by floor height, the roof belongs only to the upper zone, the
ground floor only to the lower zone, and the two zones share no thermal
element at their interface (unmodeled/adiabatic, as in the retained reference). Otherwise a
building has exactly one zone, unchanged from the original single-zone
behaviour.
"""

from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class SurfaceSpec:
    """Geometric description of one heat-exchange surface (SI units).

    Attributes
    ----------
    surface_type : str
        One of ``ExtWall``, ``Roof``, ``GroundFloor``, ``IntWall``,
        ``IntCeiling``, ``IntFloor``.
    area : float
        Gross area [m2] (glazing fraction is applied later via the envelope
        window-to-wall ratio).
    azimuth : float
        Outward-normal compass azimuth [deg] (0 = North, 90 = East);
        meaningful for vertical surfaces only.
    tilt : float
        Tilt from horizontal [deg]: 90 vertical, 0 horizontal.
    """

    surface_type: str
    area: float
    azimuth: float = 0.0
    tilt: float = 90.0


@dataclass
class ZoneGeometry:
    """Geometric description of one thermal zone within a building.

    A building has one :class:`ZoneGeometry` (``zone_label="single"``), or
    two — ``"upper"``/``"lower"`` — when the source declares separate uses
    (see the module docstring). The tabular adapter records these zones
    directly. Everything genuinely per-zone lives here; fields that
    stay the same for both zones of a building (envelope, systems, total
    height/floors, footprint area) stay on :class:`BuildingGeometry`.
    """

    name: str
    zone_label: str  # "single" | "upper" | "lower"
    end_use: str
    n_floors: int
    net_floor_area: float  # [m2]
    volume: float  # [m3]
    surfaces: list[SurfaceSpec] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Plain-dict representation for JSON serialisation (FR-08)."""
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ZoneGeometry":
        """Rebuild from :meth:`to_dict` output."""
        data = dict(data)
        data["surfaces"] = [SurfaceSpec(**s) for s in data["surfaces"]]
        return cls(**data)


@dataclass(init=False)
class BuildingGeometry:
    """Simulation-ready geometric description of one building.

    Produced from a GeoJSON feature, reconstructed from normalized CSV tables,
    or built manually for single-building studies (FR-01). Holds one or two
    :class:`ZoneGeometry` in ``zones`` (see the module docstring for the
    two-zone convention); ``end_use``, ``net_floor_area``, ``volume`` and
    ``surfaces`` are derived from ``zones`` for backward compatibility with
    single-zone callers — ``footprint_area``, ``n_floors`` and ``height``
    stay real, building-wide fields (the retained reference computes them once per building
    and reuses the same value for every zone, so they must NOT be re-derived
    as a sum over zones).
    """

    name: str
    building_id: str
    envelope: str
    heating_system: str = "IdealLoad"
    cooling_system: str = "IdealLoad"
    solar_technologies: str = ""  # e.g. "PV", "ST", "PV,ST"
    n_floors: int = 1  # total floor count (both zones combined)
    height: float = 3.0  # [m] total building height
    footprint_area: float = 0.0  # [m2]
    zones: list[ZoneGeometry] = field(default_factory=list)

    def __init__(
        self,
        name: str,
        building_id: str,
        end_use: str | None = None,
        envelope: str = "",
        heating_system: str = "IdealLoad",
        cooling_system: str = "IdealLoad",
        solar_technologies: str = "",
        n_floors: int = 1,
        height: float = 3.0,
        footprint_area: float = 0.0,
        net_floor_area: float | None = None,
        volume: float | None = None,
        surfaces: list[SurfaceSpec] | None = None,
        zones: list[ZoneGeometry] | None = None,
    ) -> None:
        """Create a canonical zoned geometry from zoned or flat parameters.

        ``zones`` is the canonical representation used by the simulation.
        The flat ``end_use``/``net_floor_area``/``volume``/``surfaces``
        arguments retain the CURRENT-version parametric construction API and
        are normalised to one ``ZoneGeometry(zone_label="single")``.
        """
        self.name = str(name)
        self.building_id = str(building_id)
        self.envelope = str(envelope)
        self.heating_system = str(heating_system)
        self.cooling_system = str(cooling_system)
        self.solar_technologies = str(solar_technologies)
        self.n_floors = max(1, int(n_floors))
        self.height = float(height)
        self.footprint_area = float(footprint_area)

        if zones is not None:
            if not zones:
                raise ValueError(f"BuildingGeometry '{self.name}' must contain at least one zone")
            self.zones = list(zones)
            return

        if end_use is None:
            raise TypeError("end_use is required when zones is not provided")
        zone_nfa = (
            float(net_floor_area)
            if net_floor_area is not None
            else self.footprint_area * self.n_floors
        )
        zone_volume = (
            float(volume)
            if volume is not None
            else self.footprint_area * self.height
        )
        self.zones = [
            ZoneGeometry(
                name=self.name,
                zone_label="single",
                end_use=str(end_use),
                n_floors=self.n_floors,
                net_floor_area=zone_nfa,
                volume=zone_volume,
                surfaces=list(surfaces or []),
            )
        ]

    @property
    def end_use(self) -> str:
        """Primary (single, or upper) zone's end use."""
        return self.zones[0].end_use

    @property
    def net_floor_area(self) -> float:
        """Net floor area summed across zones [m2]."""
        return sum(z.net_floor_area for z in self.zones)

    @property
    def volume(self) -> float:
        """Volume summed across zones [m3]."""
        return sum(z.volume for z in self.zones)

    @property
    def surfaces(self) -> list[SurfaceSpec]:
        """All surfaces of the building, concatenated across zones."""
        return [s for z in self.zones for s in z.surfaces]

    def to_dict(self) -> dict:
        """Plain-dict representation for JSON serialisation (FR-08)."""
        return {
            "name": self.name,
            "building_id": self.building_id,
            "envelope": self.envelope,
            "heating_system": self.heating_system,
            "cooling_system": self.cooling_system,
            "solar_technologies": self.solar_technologies,
            "n_floors": self.n_floors,
            "height": self.height,
            "footprint_area": self.footprint_area,
            "zones": [z.to_dict() for z in self.zones],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BuildingGeometry":
        """Rebuild canonical zoned or legacy flat serialised geometry."""
        data = dict(data)
        if "zones" in data:
            data["zones"] = [ZoneGeometry.from_dict(z) for z in data["zones"]]
        else:
            data["surfaces"] = [SurfaceSpec(**s) for s in data.get("surfaces", [])]
        return cls(**data)


# ---------------------------------------------------------------------- #
# Polygon helpers (migrated from _geometry_auxiliary_functions, 2-D case)
# ---------------------------------------------------------------------- #
def ring_area(ring: list[list[float]]) -> float:
    """Signed shoelace area of a closed 2-D ring [m2] (positive if CCW)."""
    area = 0.0
    n = len(ring)
    for i in range(n - 1):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[i + 1][0], ring[i + 1][1]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def _ring_wall_segments(ring: list[list[float]], outward_left: bool) -> list[tuple[float, float]]:
    """Return ``(length, outward_azimuth)`` for each edge of a closed ring.

    ``outward_left`` selects which side of the edge the outward normal is on
    (depends on ring winding; holes face the opposite way from outer rings).
    """
    segments = []
    for i in range(len(ring) - 1):
        dx = ring[i + 1][0] - ring[i][0]
        dy = ring[i + 1][1] - ring[i][1]
        length = math.hypot(dx, dy)
        if length < 1e-6:
            continue
        # normal to the right of travel direction: (dy, -dx); left: (-dy, dx)
        nx, ny = (-dy, dx) if outward_left else (dy, -dx)
        azimuth = math.degrees(math.atan2(nx, ny)) % 360.0  # compass (0=N, 90=E)
        segments.append((length, azimuth))
    return segments


def _polygon_area_and_walls(
    polygon: list[list[list[float]]],
) -> tuple[float, list[tuple[float, float]]]:
    """Net area [m2] and wall segments of one GeoJSON polygon (outer + holes).

    Hole edges become external walls too (courtyard facades), as in the retained reference.
    """
    area = 0.0
    walls: list[tuple[float, float]] = []
    for k, ring in enumerate(polygon):
        signed = ring_area(ring)
        ccw = signed > 0
        if k == 0:  # outer ring
            area += abs(signed)
            # CCW outer ring: outward normal is right of travel
            walls += _ring_wall_segments(ring, outward_left=not ccw)
        else:  # hole: subtract area, outward normal points into the hole
            area -= abs(signed)
            walls += _ring_wall_segments(ring, outward_left=ccw)
    return area, walls


# ---------------------------------------------------------------------- #
# GeoJSON ingestion
# ---------------------------------------------------------------------- #
def _prop(props: dict, *names: str, default=None):
    """Look up a GeoJSON feature property, tolerating capitalisation drift.

    Exact matches win; otherwise the first case-insensitive match is used.
    Real-world district files disagree on casing for the same attribute
    (the retained reference's own example district writes ``"Solar Technologies"`` while its
    loader normalises to ``"Solar technologies"``), and a silent miss here
    would disable a whole subsystem — e.g. an unmatched solar attribute
    switches off PV and solar thermal without any error.
    """
    for name in names:
        if name in props:
            return props[name]
    lowered = {str(k).strip().lower(): v for k, v in props.items()}
    for name in names:
        key = name.strip().lower()
        if key in lowered:
            return lowered[key]
    return default


def _zone_surfaces(
    wall_segments: list[tuple[float, float]],
    footprint: float,
    zone_height: float,
    zone_n_floors: int,
    ext_wall_coeff: float,
    include_roof: bool,
    include_ground: bool,
) -> list[SurfaceSpec]:
    """One zone's surface list: external walls sized at ``zone_height``,
    roof/ground floor per ``include_roof``/``include_ground``, interstorey
    floors/ceilings and a partition-wall estimate sized at this zone's own
    floor count (mirrors the retained reference's per-zone internal-mass construction)."""
    surfaces = [
        SurfaceSpec("ExtWall", length * zone_height * ext_wall_coeff, azimuth=az, tilt=90.0)
        for length, az in wall_segments
    ]
    if include_roof:
        surfaces.append(SurfaceSpec("Roof", footprint, azimuth=0.0, tilt=0.0))
    if include_ground:
        surfaces.append(SurfaceSpec("GroundFloor", footprint, azimuth=0.0, tilt=0.0))
    if zone_n_floors > 1:
        interstorey = footprint * (zone_n_floors - 1)
        surfaces.append(SurfaceSpec("IntFloor", interstorey, tilt=0.0))
        surfaces.append(SurfaceSpec("IntCeiling", interstorey, tilt=0.0))
    # Simplified internal partition estimate: one m2 of partition per m2 of
    # this zone's own net floor area (extension point: replace with
    # survey/archetype data). Deliberately NOT the retained reference's `x 2.5` factor, for
    # both the single- and two-zone cases alike (pre-existing, documented
    # simplification — see VALIDATION_COMPARISON.md).
    surfaces.append(SurfaceSpec("IntWall", footprint * zone_n_floors, tilt=90.0))
    return surfaces


def building_geometry_from_feature(feature: dict) -> BuildingGeometry:
    """Convert one GeoJSON feature into a :class:`BuildingGeometry`.

    The footprint is extruded by ``Height``: one vertical external wall per
    footprint edge (grouped geometry, gross area = edge length x height x
    ExtWallCoeff), a flat roof and a ground floor of footprint area. Internal
    floors/ceilings are added between storeys; internal partition wall area is
    estimated as the net floor area (the retained reference-like simplification). When
    ``Upper End Use``/``Lower End Use`` declare a two-zone building (see the
    module docstring), the footprint is instead split into an "upper"
    zone (floors above the ground floor) and a "lower" zone (the ground
    floor), following the retained reference's own split.

    Parameters
    ----------
    feature : dict
        GeoJSON feature with the properties listed in the module docstring
        and a Polygon/MultiPolygon geometry in a projected CRS (metres).

    Returns
    -------
    BuildingGeometry
    """
    props = feature.get("properties", {})
    geom = feature.get("geometry", {})
    if geom.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError(
            f"Feature {props.get('Name', '?')}: geometry must be Polygon or MultiPolygon, "
            f"got {geom.get('type')}"
        )
    polygons = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]

    height = float(_prop(props, "Height", default=3.0))
    n_floors = max(1, int(_prop(props, "Floors", "Nfloors", default=1)))
    storey_height = height / n_floors
    if not 2.0 <= storey_height <= 6.0:
        warnings.warn(
            f"Building '{_prop(props, 'Name', 'id', default='building')}' has "
            f"an implausible mean storey height of {storey_height:.2f} m "
            f"(Height={height:g} m, Floors={n_floors}); check that Height is "
            "the total building height.",
            RuntimeWarning,
            stacklevel=2,
        )
    ext_wall_coeff = float(_prop(props, "ExtWallCoeff", default=1.0))
    vol_coeff = float(_prop(props, "VolCoeff", default=1.0))

    footprint = 0.0
    wall_segments: list[tuple[float, float]] = []
    for polygon in polygons:
        area, walls = _polygon_area_and_walls(polygon)
        footprint += area
        wall_segments += walls
    if footprint <= 0.0:
        raise ValueError(f"Feature {props.get('Name', '?')}: non-positive footprint area")

    name = str(_prop(props, "Name", "id", default="building"))
    upper_end_use = str(
        _prop(props, "Upper End Use") or _prop(props, "End Use", default="residential")
    )
    lower_end_use_raw = _prop(props, "Lower End Use")
    # Two-zone trigger, mirroring the retained reference (city.py): a distinct, non-empty
    # Lower End Use — and at least 2 floors, since a 1-floor building has no
    # floors left for an "upper" zone.
    is_two_zone = (
        lower_end_use_raw not in (None, "")
        and str(lower_end_use_raw) != upper_end_use
        and n_floors >= 2
    )

    if is_two_zone:
        floor_height = height / n_floors
        upper_floors = n_floors - 1
        zones = [
            ZoneGeometry(
                name=f"{name}_upper",
                zone_label="upper",
                end_use=upper_end_use,
                n_floors=upper_floors,
                net_floor_area=footprint * upper_floors,
                volume=footprint * floor_height * upper_floors * vol_coeff,
                surfaces=_zone_surfaces(
                    wall_segments, footprint, floor_height * upper_floors, upper_floors,
                    ext_wall_coeff, include_roof=True, include_ground=False,
                ),
            ),
            ZoneGeometry(
                name=f"{name}_lower",
                zone_label="lower",
                end_use=str(lower_end_use_raw),
                n_floors=1,
                net_floor_area=footprint,
                volume=footprint * floor_height * vol_coeff,
                surfaces=_zone_surfaces(
                    wall_segments, footprint, floor_height, 1,
                    ext_wall_coeff, include_roof=False, include_ground=True,
                ),
            ),
        ]
    else:
        zones = [
            ZoneGeometry(
                name=name,
                zone_label="single",
                end_use=str(_prop(props, "End Use", default="residential")),
                n_floors=n_floors,
                net_floor_area=footprint * n_floors,
                volume=footprint * height * vol_coeff,
                surfaces=_zone_surfaces(
                    wall_segments, footprint, height, n_floors,
                    ext_wall_coeff, include_roof=True, include_ground=True,
                ),
            ),
        ]

    return BuildingGeometry(
        name=name,
        building_id=str(_prop(props, "id", "Name", default="0")),
        envelope=str(_prop(props, "Envelope", default="")),
        heating_system=str(_prop(props, "Heating System", default="IdealLoad")),
        cooling_system=str(_prop(props, "Cooling System", default="IdealLoad")),
        solar_technologies=str(_prop(props, "Solar technologies", default="") or ""),
        n_floors=n_floors,
        height=height,
        footprint_area=footprint,
        zones=zones,
    )


def simple_building_geometry(
    name: str,
    footprint_area: float,
    height: float,
    n_floors: int,
    end_use: str,
    envelope: str,
    aspect_ratio: float = 1.0,
    orientation: float = 0.0,
    heating_system: str = "IdealLoad",
    cooling_system: str = "IdealLoad",
    solar_technologies: str = "",
) -> BuildingGeometry:
    """Build a rectangular single-building geometry directly — the
    GeoJSON-free entry route for single-building studies (FR-01).

    Produces the same :class:`BuildingGeometry` a GeoJSON feature would
    (four external walls, flat roof, ground floor, interstorey and partition
    surfaces), so it plugs into ``preprocess_geometries`` unchanged.

    Parameters
    ----------
    name : str
        Building name (also the id).
    footprint_area : float
        Footprint area [m2].
    height : float
        Building height [m].
    n_floors : int
        Number of storeys.
    end_use : str
        Key into the end-use schedule database.
    envelope : str
        Key into the envelope archetype database.
    aspect_ratio : float
        Footprint length/width ratio (1 = square).
    orientation : float
        Compass rotation of the footprint [deg] (0 = long side facing N/S).
    heating_system, cooling_system : str
        System template code or catalog name.
    solar_technologies : str
        e.g. ``"PV"``, ``"ST"``, ``"PV,ST"``.

    Returns
    -------
    BuildingGeometry
    """
    if footprint_area <= 0.0 or height <= 0.0 or n_floors < 1:
        raise ValueError(
            f"Building '{name}': footprint_area and height must be positive, n_floors >= 1"
        )
    width = math.sqrt(footprint_area / aspect_ratio)
    length = footprint_area / width
    # rectangular ring (CCW) rotated by the orientation
    phi = math.radians(orientation)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    corners = [(0.0, 0.0), (length, 0.0), (length, width), (0.0, width)]
    ring = [[x * cos_p - y * sin_p, x * sin_p + y * cos_p] for x, y in corners]
    ring.append(ring[0])
    feature = {
        "type": "Feature",
        "properties": {
            "id": name,
            "Name": name,
            "End Use": end_use,
            "Envelope": envelope,
            "Height": height,
            "Floors": n_floors,
            "Heating System": heating_system,
            "Cooling System": cooling_system,
            "Solar technologies": solar_technologies,
        },
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }
    return building_geometry_from_feature(feature)


def load_district_geojson(path: str | Path) -> list[BuildingGeometry]:
    """Parse a district GeoJSON file into a list of building geometries (FR-06).

    Parameters
    ----------
    path : str or pathlib.Path
        GeoJSON FeatureCollection in a projected CRS (coordinates in metres).

    Returns
    -------
    list of BuildingGeometry
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("type") != "FeatureCollection":
        raise ValueError(f"{path}: expected a GeoJSON FeatureCollection")
    return [building_geometry_from_feature(f) for f in data.get("features", [])]
