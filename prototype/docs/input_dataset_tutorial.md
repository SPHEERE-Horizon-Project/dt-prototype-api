# Creating and extending a DT-Prototype building dataset

This tutorial shows how to create a new building dataset, reuse weather and
model libraries already stored in the project, and add buildings without
losing the provenance of earlier runs. It uses the normalized CSV geometry
route because it is direct, reviewable and suitable for incremental portfolio
growth. The GeoJSON route remains available when footprint polygons are the
authoritative source.

The examples describe model input preparation and software verification. A
successful run confirms that the files are internally consistent; it does not
validate the physical model against measured energy.

## 1. Organise the repository

Keep received material separate from simulation-ready data, and do not modify
the five-building files under `data/examples/`: they are regression fixtures.
A scalable layout is:

```text
data/
    raw/
        campus_a/
            surveys/
            drawings/
            original_footprints.geojson
    processed/
        shared/
            weather/
            libraries/
        campus_a/
            v001/
                geometry/
                    buildings.csv
                    zones.csv
                    surfaces.csv
                dataset_metadata.md
            v002/
                geometry/
                    buildings.csv
                    zones.csv
                    surfaces.csv
                dataset_metadata.md
    examples/                    protected verification data
configs/
    campus_a_v001.json
    campus_a_v002.json
```

The folder names are a recommended convention rather than a hard-coded
requirement. Configuration paths can point anywhere inside the project.
`dataset_metadata.md` should record the source, survey or issue date, units,
coordinate reference system where relevant, transformations, assumptions,
known gaps, author and a short change log. It belongs beside `geometry/`, not
inside it, so the geometry directory contains only the three input tables.

Once a dataset has supported a reported run, treat that version as immutable.
Additions and corrections go into `v002`, `v003`, and so on. Shared weather and
library files need not be copied into every version.

## 2. Choose the geometry route

| Route | Use it when | Stored geometry |
|---|---|---|
| Tabular | Areas, volumes, orientations and zoning are already known, or a compact portfolio database is wanted | Simulation-ready buildings, zones and surfaces |
| GeoJSON | Georeferenced footprint polygons are authoritative and automatic extrusion is appropriate | Polygon or multipolygon coordinates plus building properties |

Both routes produce the same internal `BuildingGeometry` objects before an
engine is selected. A tabular dataset cannot reconstruct the original polygon
coordinates; preserve the source GeoJSON under `data/raw/` if GIS traceability
matters.

Use a non-leap calendar year and the supported timestep settings in the
[input contract](data_contracts.md#supported-calendar-and-controls). Leap-year
EPWs and a leap-year calendar are currently rejected. Check local-standard-time
and weekday assumptions when reusing typical-year weather for another year.

## 3. Create the three geometry tables

Save the files as UTF-8 comma-separated CSV with a header row, decimal points
and numeric values without unit text. Quote values that contain commas. Do not
replace an unknown value with zero: resolve it, document an explicit modelling
assumption, or leave the building out until the required input is available.

### 3.1 `buildings.csv`

One row describes each physical building.

| Column | Meaning and rule |
|---|---|
| `building_id` | Permanent, nonempty and unique identifier. Keep it unchanged between dataset versions. |
| `building_name` | Unique display name. |
| `envelope` | Exact key in the configured envelope library. |
| `heating_system` | System template code or supported catalogue name; use `IdealLoad` only when that boundary is intended. |
| `cooling_system` | System template code or supported catalogue name; use `IdealLoad` only when that boundary is intended. |
| `solar_technologies` | Empty, `PV`, `ST`, or `PV,ST` for the current implementation. |
| `n_floors` | Total building storeys, integer of at least one. |
| `height_m` | Total building height in metres, positive. |
| `footprint_area_m2` | Ground footprint area in square metres, positive. |

Example:

```csv
building_id,building_name,envelope,heating_system,cooling_system,solar_technologies,n_floors,height_m,footprint_area_m2
campus_a_001,Library,1981-1990,IdealLoad,IdealLoad,,1,3.0,100.0
```

Use identifiers such as `campus_a_001` when files may pass through spreadsheet
software; purely numeric identifiers with leading zeroes are easily altered.

### 3.2 `zones.csv`

Every building needs at least one zone. The pair `building_id,zone_id` is the
join key and must be unique.

| Column | Meaning and rule |
|---|---|
| `building_id` | Must exist in `buildings.csv`. |
| `zone_id` | Stable label within the building, normally `single`, `upper`, or `lower`. |
| `zone_name` | Readable zone name; keep it unique within the portfolio. |
| `end_use` | Exact key in the configured schedule library. |
| `n_floors` | Storeys represented by this zone, integer of at least one. |
| `net_floor_area_m2` | Conditioned net floor area in square metres, positive. |
| `volume_m3` | Conditioned air volume in cubic metres, positive. |

Single-zone example:

```csv
building_id,zone_id,zone_name,end_use,n_floors,net_floor_area_m2,volume_m3
campus_a_001,single,Library,services,1,100.0,300.0
```

The current engines support one zone or the established independent two-zone
representation. A two-zone building normally has `upper` and `lower` rows.
The building-level envelope and systems apply to both zones, while each zone
may reference a different end-use schedule. Inter-zone heat transfer is not
modelled in this representation.

### 3.3 `surfaces.csv`

Every zone needs at least one surface. The combination
`building_id,zone_id,surface_index` must be unique.

| Column | Meaning and rule |
|---|---|
| `building_id`, `zone_id` | Must identify a row in `zones.csv`. |
| `surface_index` | Integer starting at zero; controls stable surface ordering within the zone. |
| `surface_type` | `ExtWall`, `Roof`, `GroundFloor`, `IntWall`, `IntCeiling`, or `IntFloor`. |
| `area_m2` | Gross surface area in square metres, positive. Window area is derived from the envelope window-to-wall ratio and must not be added as a separate surface. |
| `azimuth_deg` | Outward-normal compass azimuth: 0 north, 90 east, 180 south, 270 west. |
| `tilt_deg` | Tilt from horizontal: 0 horizontal and 90 vertical. |

For the 10 m by 10 m, single-storey example:

```csv
building_id,zone_id,surface_index,surface_type,area_m2,azimuth_deg,tilt_deg
campus_a_001,single,0,ExtWall,30.0,0.0,90.0
campus_a_001,single,1,ExtWall,30.0,90.0,90.0
campus_a_001,single,2,ExtWall,30.0,180.0,90.0
campus_a_001,single,3,ExtWall,30.0,270.0,90.0
campus_a_001,single,4,Roof,100.0,0.0,0.0
campus_a_001,single,5,GroundFloor,100.0,0.0,0.0
campus_a_001,single,6,IntWall,100.0,0.0,90.0
```

Internal surfaces represent thermal mass. The 7R2C dynamic model requires at
least one external and one internal surface in every zone. For a multi-storey
single zone, `IntFloor` and `IntCeiling` commonly each use
`footprint area × (number of floors - 1)`. The retained preprocessing convention
estimates `IntWall` area as the zone net floor area; replace that estimate with
surveyed data when available and document the source.

For the established two-zone convention, the upper zone owns the roof and the
lower zone owns the ground floor. Both zones have their own external walls and
internal-mass surfaces. Do not add the interface between them as a heat-loss
surface: it is treated as unmodelled/adiabatic by the current implementation.

## 4. Check geometry consistency

Before configuring a run, check these relationships against the source data:

- each building ID and name is unique;
- each zone and surface refers to an existing parent key;
- the sum of zone floors is consistent with the building floor count;
- zone areas and volumes are consistent with the intended conditioned boundary;
- `height_m / n_floors` gives a credible mean storey height;
- roof and ground areas are consistent with the footprint where that assumption applies;
- external-wall areas use gross opaque-plus-window wall area;
- azimuths represent outward normals, not the direction of the wall line;
- each zone has the external and internal surfaces required by the selected RC model;
- areas, volumes and counts are not duplicated across zones.

These checks are scientific review items as well as data checks. The loader can
detect missing columns, invalid references, duplicate keys and basic numeric
errors, but it cannot determine whether a plausible number describes the right
physical boundary.

## 5. Reuse existing project data

The configuration links geometry to weather and three reusable libraries. A
new portfolio can therefore reuse existing data without copying it.

| Reusable input | Existing example | Reuse rule |
|---|---|---|
| Weather | `data/examples/ITA_Venezia-Tessera.161050_IGDG.epw` | Reuse only when the site and weather boundary are appropriate. One configuration currently assigns one EPW to the portfolio. Use separate configurations/runs for different weather sites. |
| Envelopes | `data/examples/archetypes.json` | Set `buildings.csv:envelope` to an existing exact key such as `1981-1990`. |
| Schedules | `data/examples/schedules.json` | Set `zones.csv:end_use` to an existing exact key such as `residential`, `food`, or `services`. |
| Systems | `data/examples/systems_templates.json` | Reference an existing system code or supported catalogue name in `buildings.csv`. |

Review the assumptions before reusing a record. A matching name does not prove
that an archetype, schedule, system or weather file is suitable for the new
building. If a required record does not exist, copy the relevant library to a
new versioned path and add a new named entry with its source and units. Do not
silently change a shared entry that has already supported completed runs.

## 6. Create the dataset configuration

Copy `configs/example_tabular.json` to a dataset-specific name and change the
paths. Paths are resolved relative to the configuration file. For the layout
above, the input section would resemble:

```json
"inputs": {
  "geometry": "../data/processed/campus_a/v001/geometry",
  "geometry_format": "tabular",
  "weather_epw": "../data/examples/ITA_Venezia-Tessera.161050_IGDG.epw",
  "envelopes": "../data/examples/archetypes.json",
  "schedules": "../data/examples/schedules.json",
  "systems": "../data/examples/systems_templates.json",
  "calendar_year": 2023,
  "time_steps_per_hour": 1,
  "azimuth_subdivisions": 8
}
```

These paths reuse the current project files. When reviewed shared libraries
are later established under `data/processed/shared/`, change the paths to those
versioned files without changing the geometry tables.

Retain and review the remaining groups from the example configuration:

- `operating`: heating and cooling day-of-year intervals, AHU mode and initial
  temperature/humidity;
- `dynamic`: RC model, latent and plant switches, sizing, DHW tank and battery;
- `simplified`: Model 3 comparison mode and zone representation.

These settings affect scientific meaning and should not be inherited merely
because the paths work. Record dataset-specific choices in the metadata and,
when they establish a project convention, in `docs/decision_log.md`.

## 7. Validate before simulation

From the project root, install the package and load the configuration:

```powershell
python -m pip install -e '.[dev]'
python -c "from dt_prototype.common.project import ProjectInputs; p=ProjectInputs.load('configs/campus_a_v001.json'); d=p.preprocess(); print([(b.geometry.building_id, b.name, len(b.zones)) for b in d.buildings])"
```

This checks the three-table joins, library references, input paths and weather
preprocessing. Review any warnings; a completed load is not a reason to ignore
an implausible storey height or an inappropriate library assignment.

Run each required representation into a new output directory:

```powershell
python runners/run_dynamic.py --config configs/campus_a_v001.json --output outputs/campus_a_v001_dynamic --model 5R1C
python runners/run_monthly.py --config configs/campus_a_v001.json --output outputs/campus_a_v001_monthly
python runners/run_simplified.py --config configs/campus_a_v001.json --output outputs/campus_a_v001_simplified --zone-mode sum
```

Check `manifest.json` for input hashes, resolved settings, status and failed
buildings. Then inspect `monthly.csv`, `annual.csv`, warnings and detailed
outputs for finite, nonnegative energy totals and the intended building IDs,
months, zones and representations.

## 8. Add buildings incrementally

Use this sequence whenever the repository grows:

1. Place original source material under `data/raw/<dataset_id>/` without
   modifying it.
2. Copy the last accepted processed version to a new version directory.
3. Append one unique building row, its zone rows and all referenced surface
   rows. Preserve every existing `building_id`.
4. Update the metadata with sources, assumptions and the exact change.
5. Create a new configuration pointing to the new version.
6. Load and preprocess the configuration, then run the relevant engines into
   fresh output directories.
7. Compare unchanged buildings with the prior dataset version. Their inputs
   and deterministic results should remain unchanged unless a shared input was
   deliberately revised.
8. Add a small regression test for the new building count, IDs, zone topology
   and any accepted reference result. Keep prior reference fixtures unchanged.

If a shared weather or library file changes, give that file a new versioned
name and identify all affected buildings. Such a change can alter previously
included results even when their geometry tables are untouched.

## 9. Import an existing GeoJSON dataset

Keep the received GeoJSON under `data/raw/`. It must be a FeatureCollection
with Polygon or MultiPolygon coordinates in a projected metre-based CRS. The
current reader uses properties including `id`, `Name`, `Envelope`, `End Use`,
`Height`, `Floors`, `Heating System`, `Cooling System` and optional solar and
upper/lower end-use fields.

It can be used directly with `geometry_format: "geojson"`, or converted once
to the normalized tables for review and incremental editing:

```python
from dt_prototype.common.preprocessing.geometry import load_district_geojson
from dt_prototype.common.preprocessing.tabular_geometry import write_district_tables

geometries = load_district_geojson("data/raw/campus_a/original_footprints.geojson")
write_district_tables(geometries, "data/processed/campus_a/v001/geometry")
```

The writer refuses to overwrite existing tables. Review the derived footprint,
wall orientations, floor areas, volumes and one/two-zone split before accepting
them as processed input.

## 10. Minimum acceptance checklist

A dataset is ready for comparative model runs when:

- raw sources and processed assumptions are traceable;
- geometry IDs and joins are unique and complete;
- units and conditioned boundaries are documented;
- envelope, schedule and system names resolve to reviewed library records;
- weather location, year convention and aggregation assumptions are declared;
- one-zone or two-zone representation is intentional;
- the configuration records all scientific switches explicitly;
- preprocessing and relevant automated tests pass;
- each engine writes a complete manifest with no unexplained failed building;
- changes from the preceding dataset version are reviewed building by building.

The formal field contract is in [data contracts](data_contracts.md). Model
differences should be described as comparison or cross-model verification.
Calibration requires a declared calibration subset, and validation requires
untouched observations or an independent reference case.
