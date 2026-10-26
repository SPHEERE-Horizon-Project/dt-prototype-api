# Cadastral and archetype preprocessor

The cadastral preprocessor is the deliberately small layer between sparse
portfolio data and DT-Prototype's simulation-ready geometry contract. It is
suited to Level of Detail 1 studies: projected footprints are extruded, basic
attributes select reviewed envelope and schedule archetypes, and the result is
written as the same three normalized CSV files consumed by all four thermal solver families.

It does **not** create an EnergyPlus or OpenStudio model. That would duplicate
the role of tools such as `geogen`. It creates the smaller, engine-neutral
input needed by this repository and records every inference.

## Recommended division of responsibility

| Source | Use in this preprocessor | Do not infer from it |
|---|---|---|
| Cadastral/GIS data | Stable ID, projected footprint, height/storeys, construction year, declared use, location | Construction layers, schedules, HVAC efficiency |
| TABULA/EPISCOPE | Residential size/vintage classification, envelope and system reference values, retrofit variants | A statistically exact description of an individual building |
| URBEM | Italian use/region/climate/vintage reference-building selection; scorecard envelope, gains, ventilation and system assumptions | Geometry when a scorecard reports no value, or a mixed-use split absent from the source building |
| Local EPC/survey data | Override archetype values when building-specific evidence exists | Missing values disguised as zero |

TABULA describes exemplary buildings, not statistically representative
individual buildings. URBEM is more granular for Italy and covers residential,
office, school, catering and commercial categories, but its public scorecards
also expose missing fields. Consequently the safe precedence is:

1. building-specific surveyed/EPC value;
2. a uniquely matched URBEM archetype;
3. TABULA for residential stock where URBEM coverage or a required field is absent;
4. an explicit local default, marked low confidence.

Numerical TABULA or URBEM data should live in versioned envelope/schedule/system
libraries, not in the selection code. The JSON rule catalogue only maps
cadastral attributes to those library keys and preserves provenance.

## Minimal source contract

The source is a GeoJSON `FeatureCollection` whose Polygon/MultiPolygon
coordinates are in metres. Property names are configurable; common Italian
and English aliases are built in. The useful fields are:

| Field | Requirement | Fallback |
|---|---|---|
| Building ID | Required and unique | None |
| Footprint | Required, projected Polygon/MultiPolygon | None |
| Height/storeys | At least one is preferable | Infer one from the other using configured storey height; if both are absent use explicit defaults |
| Construction year | Strongly recommended | Catalogue default envelope, low confidence |
| Primary use | Strongly recommended | Catalogue default end use, low confidence |
| Region/climate zone/type | Needed for a specific URBEM match | Only wildcard rules may match when missing |
| Ground-floor use | Optional | One zone |

If the source already contains a reviewed `Envelope` assignment, it takes
precedence over catalogue inference and is identified as a building-specific
source property in the report. Existing `ExtWallCoeff` and `VolCoeff`
corrections are also preserved when present.

A geographic CRS such as EPSG:4326 is rejected because degree coordinates
would produce meaningless areas. If GeoJSON omits `crs`, coordinates are
assumed to be projected metres and that assumption is written to the manifest.

## Conservative zoning rule

The default is one zone, regardless of the number of storeys. A two-zone model
is generated only when all of the following are true:

- the source explicitly gives a ground-floor use;
- that use maps to a known schedule and differs from the primary use;
- the building has two or more storeys.

The two zones follow the repository's existing convention: `lower` is the
ground floor and `upper` contains every storey above it. This is appropriate
for a shop/restaurant ground floor below residential or office space. It is
not a core/perimeter or day/night split. An unknown, inferred or merely
probable mixed use stays single-zone.

## Rule catalogue

Start with
[`configs/cadastral_archetype_rules.example.json`](../configs/cadastral_archetype_rules.example.json).
Rules may filter on `year_min`, `year_max`, `end_uses`, `building_types`,
`regions` and `climate_zones`. Missing selector lists mean wildcard. The most
specific matching rule wins; `priority` resolves intentional precedence such
as a regional URBEM rule over a generic vintage rule. Equal-ranked matches are
rejected instead of silently choosing one.

Each rule records:

- `envelope`: exact key in the configured DT-Prototype envelope JSON;
- `source`: attribution displayed in the audit report;
- `source_archetype`: external TABULA/URBEM code;
- selection fields and optional integer `priority`.

The example contains executable mappings to the current demonstration
envelope keys but does not copy external numerical data. Replace its placeholder
TABULA identifiers and verify the mapped library entries before analytical use.

The existing archetype loader accepts either full material layers or a
U-value plus mass class. This makes it possible to translate reviewed URBEM
scorecard medians without inventing a stratigraphy:

```json
"ext_wall": {
  "u_value": 0.8,
  "mass_class": "Heavy",
  "absorptance": 0.6
}
```

Keep the original downloaded scorecard unchanged under `data/raw/`, create a
separate reviewed JSON entry under version control, and cite its scorecard code
in the rule. Do not parse a dash in a scorecard as zero. TABULA explicitly
requires visible attribution to “IEE Projects TABULA + EPISCOPE
(www.episcope.eu)”; the example rule catalogue retains that wording. URBEM
scorecards permit analysis, modelling and research with attribution while
requiring the original data to remain unaltered. Archive the downloaded source
unchanged and confirm redistribution terms before publishing a transformed
machine-readable library.

## Run

From an installed project environment:

```powershell
python runners/generate_cadastral_inputs.py `
  --input data/raw/city/buildings.geojson `
  --rules configs/city_archetype_rules.json `
  --output data/processed/city/v001
```

The command refuses to overwrite an existing output and creates:

```text
v001/
    geometry/
        buildings.csv
        zones.csv
        surfaces.csv
    preprocessing_report.csv
    preprocessing_manifest.json
```

Point `inputs.geometry` in a normal project configuration to `v001/geometry`
and set `inputs.geometry_format` to `tabular`. The report has one row per
building with the selected rule, source archetype, dimension method, zoning
reason, confidence and assumptions. The manifest hashes both source files and
summarizes zone counts and known limitations.

## Scale and next increments

The algorithm is linear in buildings plus footprint edges and has no geometry
engine dependency, so it is suitable for large portfolios. Before using it for
dense urban blocks, the highest-value next addition is party-wall detection:
the current geometry contract treats every footprint edge as external. Other
useful increments are a reviewed URBEM scorecard-to-library import tool,
building-level WWR overrides, and uncertainty ensembles that sample scorecard
quartiles rather than treating a median archetype as certain.

## Related open-source patterns

- [geogen](https://github.com/antoine-galataud/geogen) is a good model for a
  clean source adapter: it retrieves footprint, height and storeys from BDNB,
  extrudes them, and keeps geometry generation separate from constructions,
  occupancy and HVAC. This preprocessor adopts that separation but targets the
  smaller DT-Prototype tables instead of OpenStudio/IDF.
- [GIS-AWBEM](https://github.com/KIT-IAI/GIS-AWBEM) demonstrates a minimum
  district workflow using public GIS, schedules, EPW weather and TABULA
  U-values. Its explicit enrichment step is analogous to this catalogue.
- [City2TABULA](https://github.com/THD-Spatial-AI/city2tabula) is relevant when
  the source is CityGML/CityJSON at national or city scale; it extracts and
  normalizes geometric features before TABULA classification.
- [DistrictGenerator](https://github.com/RWTH-EBC/districtgenerator) uses a
  small TABULA-like input set including building type, construction year,
  storeys and mixed-use categories. Its explicit mixed-use codes support the
  same conservative principle used here: split only when mixed use is actually
  declared.

Primary data sources are the
[TABULA/EPISCOPE download page](https://episcope.eu/communication/download/)
and the [URBEM reference-building database](https://www.urbem.polimi.it/databasedifici/).
