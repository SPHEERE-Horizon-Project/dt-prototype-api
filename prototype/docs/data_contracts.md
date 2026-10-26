# Shared input and output contracts

Versioned structural schemas and the optional validation-only command are
described in [input preflight](input_preflight.md). Existing Python readers
continue to enforce the semantic contracts below.

The separate [inverse-model contract](inverse_models.md) defines interval energy,
hourly weather, meter boundaries, measured/simulated provenance, train/validation
splits, timezone rules and saved statistical models. It does not require geometry
for measured-only execution or change the shared physical-input contract below.

For a worked example that starts with an empty dataset and develops a
versioned portfolio, see [creating and extending a building dataset](input_dataset_tutorial.md).

## Input schema 1.0

`dt_prototype.common.project.ProjectInputs` is the common input type. `configs/example.json` declares all paths and the retained example operating assumptions. Paths are resolved relative to the configuration file, allowing one configuration to be used from any launcher directory.

| Configuration group | Fields and meaning |
|---|---|
| `inputs` | `geometry`, `geometry_format`, `weather_epw`, `envelopes`, `schedules`, `systems`; explicit `calendar_year`, `time_steps_per_hour`, `azimuth_subdivisions` |
| `operating` | Heating/cooling day-of-year intervals, AHU mode, initial temperature and specific humidity |
| `dynamic` | RC network, latent and plant toggles, sizing, DHW tank and PV battery options |
| `simplified` | `comparison_mode` (`seasonal_ahu` or legacy); zone representation (`sum`, `collapsed`, `both`) |

`geometry_format` is `geojson` or `tabular`. GeoJSON holds footprint polygons plus stable building IDs, display names, envelope/end-use assignments and zoning. The tabular route points `geometry` to a directory containing three normalized UTF-8 CSV files:

| File | One row per | Required fields |
|---|---|---|
| `buildings.csv` | Building | `building_id`, `building_name`, envelope/system assignments, total floors, height and footprint area |
| `zones.csv` | Thermal zone | `building_id`, `zone_id`, `zone_name`, `end_use`, floors, net floor area and volume |
| `surfaces.csv` | Heat-exchange surface | `building_id`, `zone_id`, `surface_index`, type, area, azimuth and tilt |

The tabular tables are a simulation-ready geometry contract. They preserve the surfaces produced from an existing GeoJSON case, but do not preserve polygon coordinates or provide automatic footprint extraction. IDs form explicit joins; every building must have zones and every zone must have surfaces. The loader checks required columns, uniqueness, references, nonempty values and principal numeric ranges before simulation.

`surfaces.csv` also accepts optional `boundary_condition`: `auto` (missing or
blank CSV value) or `adiabatic`. `SurfaceSpec` uses the same optional field in
Python/serialized geometry; omitted old JSON fields default to `auto`. Other
values fail validation. `auto` preserves the original external/ground/internal
surface-type interpretation. `adiabatic` disables external transmission and
outdoor thermal forcing without changing physical construction/area/glazing.
Canonical writers include the field. No required columns or project schema
version change. Physical roof irradiance for renewable generation is separate
from thermal exposure. See [surface boundary contract and limits](adiabatic_boundaries.md).

Both routes construct the same `BuildingGeometry` and then use the same envelope, schedule, system and weather preprocessing. JSON files hold the existing envelope, schedule and system definitions. The EPW remains the single weather source. Physical units and remaining field checks are defined in the retained readers; this contract does not claim comprehensive validation of every possible malformed source.

The loader rejects missing source files, missing explicit operating fields, invalid options, non-finite initial conditions and duplicate/empty IDs or names. Baseline physical inputs are not calibrated or overwritten.

Project and energy JSON, geometry and the envelope/schedule/system library
readers accept UTF-8 with or without BOM and reject duplicate keys and nonfinite
JSON numbers. Shared project root, input, operating, dynamic and simplified
sections reject unknown setting names; `description` is optional at the root.
These checks do not make every library record a closed formal schema. See
[the run guide](running_forward_and_inverse.md) for current commands and
[the review](reliability_review_20261022.md) for validation scope.

### Supported calendar and controls

- `calendar_year` must be an integer non-leap year. The reader requires 8,760 ordered hourly records. EPW source years may vary for a typical meteorological year, but month/day/hour must run from January 1 hour 1 to December 31 hour 24. Timestamps use local standard time and the configured year determines schedule weekdays.
- `time_steps_per_hour` must be one of `1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60`. Weather is linearly interpolated and schedules are held within each hour. The final hour is extended with its last value. Interpolation does not create new measured weather observations.
- `azimuth_subdivisions` must be an integer from 1 to 360. The default remains 8. Bins use integer-degree labels consistently in generation and lookup.
- Season bounds must be integer days 1–365, inclusive. A start after the end wraps over New Year. Initial temperature is °C and initial specific humidity is a non-negative humidity ratio in kg/kg.
- Toggles are JSON `true`/`false`, never strings. Heating maximum power is non-negative W; cooling maximum power is non-positive W; `null` means unlimited. Sizing is `static` or `design_day`.
- Model names are `5R1C` or `7R2C` (legacy `1C`/`2C` aliases remain accepted in configuration). Monthly_SS_simplified comparison mode is `legacy` or `seasonal_ahu`; zone mode is `sum`, `collapsed` or `both`. Unknown operating/dynamic setting names are rejected.

Missing/sentinel, non-finite or out-of-range values in EPW dry-bulb/dew-point temperature, pressure, humidity, irradiance or wind speed are rejected with a field and line number. No automatic gap filling is performed. The simulation contract restricts relative humidity to 0–100%, even though the [EnergyPlus EPW dictionary](https://bigladdersoftware.com/epx/docs/24-1/auxiliary-programs/energyplus-weather-file-epw-data-dictionary.html) permits values up to 110%. Unused sky-cover data are not used as a rejection criterion. This is targeted validation, not a complete EPW conformance validator.

## Mapping by tool

| Input | Dynamic | Monthly | Monthly_SS_simplified |
|---|---|---|---|
| Geometry/envelope | RC network parameterisation | Monthly conductance and capacity | Mapped conductance, area/volume and nearest mass class |
| EPW | Hourly boundary | Monthly balance with prepared hourly gains | Monthly temperature, irradiation-derived gains and AHU conditions |
| Schedules | Time-varying loads and controls | Seasonal availability and gains | Monthly gains, annual-mean airflow and active setpoints |
| Zoning | One zone or independent two-zone execution | Same topology | Native single zone, explicit collapse, or independent-zone sum |
| Systems | Plant/carrier options where enabled | Useful sensible demand | Comparison outputs focus on useful sensible demand; legacy technical-system functions remain available |

Monthly_SS_VBDD uses the same geometry, envelope, weather and schedules to prepare monthly heat-loss moments, gains and capacity; its direct-monthly, temperature-linear-solar and fixed-utilisation modes are explicit alternatives. All four families can pass their useful sensible outputs to the optional shared energy layer below. Common inputs do not imply identical equations or temporal approximations. The verification workbooks consume prepared monthly inputs, not raw geometry or EPW files; see [workbook instructions](workbook_instructions.md).

## Common result contract

The optional [asset quantity contract](asset_quantities.md) is separate from
thermal and energy results. It accepts one catalogue plus auto/direct JSON or
Excel inputs, resolves a solver-independent inventory by assessment/building,
and exports `base_quantity`, effective `sizing_factor`, `assessed_quantity`,
unit, rule/source provenance and completeness status. Units are m2, kW, kWh
and L with explicit rating/volume bases. Direct inputs always use factor 1.
Neither the existing ProjectInputs schema nor thermal runner inputs change.
`Assessment --asset-quantities` is an optional strict join; no extra columns
are added to the existing external assessment result CSV contract.

CLI `monthly.csv` includes `run_id`, `engine_id`, `building_id`, `building_name`, `scenario_id`, `weather_id`, `period_id`, `zone_count`, `representation`, and numeric `zone_heating_kWh`, `zone_cooling_kWh`, `ahu_heating_kWh`, `ahu_cooling_kWh`, `heating_kWh`, `cooling_kWh`.

Heating and cooling are positive useful sensible energy. Total demand is zone plus sensible AHU; heating and cooling signs are separated per zone before addition. Dynamic raw files retain their original signed power columns and technical-system results. Delivered/carrier energy is a distinct boundary.

The comparison workflow retains its richer monthly schemas, per-zone results and mapping manifests. `aggregate` alone is insufficient to establish comparability: use the variant and representation fields. Annual CSVs sum each actual building once. Run manifests record source/configuration hashes, resolved options, dependencies and failed buildings.

Detailed CLI files now use a bounded, portable building-ID name plus a hash instead of the display name. Read `manifest.json` → `building_outputs` to locate a building's detail file; failed buildings can have a listed filename without a completed file. Original IDs and names remain in tables. Mapped simplified directories use the same safe naming rule, and detailed/summary weather IDs share the EPW hash. Consumers of old display-name filenames must migrate to the manifest. `--model` is only accepted for dynamic runs; `--zone-mode` only for simplified runs.

Integration report `run_id` values must start with a letter/digit and contain 1–64 ASCII letters, digits, underscores or hyphens. Reserved Windows device names are rejected. Direct CLI `--output` remains an explicit filesystem path chosen by the caller.

5P measured-series contracts and calibration/validation rules remain in [the retained methodology](five_parameter_energy_signature.md). No measured energy was introduced by this refactor.

## Optional energy configuration schema 1.0

The energy JSON is separate from `ProjectInputs`. `EnergyConfig.load` validates it before calculation. `schema_version`, `scenario_id`, `description`, `currency`, `technologies`, `buildings` and `carriers` identify the scenario. Unknown fields are rejected. The [example](../configs/energy_example.json) is explicit, and its factors/prices are illustrative.

| Object | Contract |
|---|---|
| Technology | One carrier; performance coefficients in ascending powers of outdoor °C (constant through degree five), temperature minimum/maximum and `clip` or `error` policy; strictly positive performance throughout its declared domain; distribution/emission/regulation efficiencies in (0,1]; nonnegative electric auxiliary kWh per generated kWh; source |
| Building services | Exactly `zone_heating`, `ahu_heating`, `zone_cooling`, `ahu_cooling`, `dhw`, each referencing an existing technology |
| Common ancillary assumptions | Fan W per m³/h and base auxiliary W, with provenance; preprocessor integrates schedules and interval durations |
| PV | Roof coverage, module kWp/m², performance ratio; monthly factor in [0,1], scalar or twelve January–December values; explicit `overlap` or `generation` basis; source |
| Solar thermal | Roof coverage, efficiency/loss coefficients, fluid temperature; monthly utilisation in [0,1], scalar or twelve values; source; available heat is at the DHW generator bus |
| Carrier factors | Import and export primary nonrenewable/renewable factors (kWh primary/kWh), carbon (kgCO2e/kWh), prices (currency/kWh), source. Each is scalar or twelve monthly values. Physical factors are nonnegative; signed prices are allowed. |

The supplied scenario uses electricity, natural gas, district heat and other fuel. The Python engine also accepts additional carrier identifiers matching `[a-z][a-z0-9_]*` when their full factor records and technology assignments are supplied; electricity must be present. Export is electricity only. Import burdens and export credits are separate outputs before netting; an export credit never reduces another carrier's physical demand. A multi-carrier technology requires an explicit calculation/schema extension. The delivered workbook layout is pinned to the four example carriers and must be regenerated/extended for a different carrier set.

## Energy interval input contract

`energy.calculate(inputs, config, building_id, resolution=...)` consumes one building/representation at a time. Identifiers remain metadata; zone sum and collapsed inputs must not share a calculation frame.

| Column | Unit / semantics |
|---|---|
| `time`, `period_id` | Unique ordered timezone-naive local-standard-time interval start; matching `YYYY-MM` period |
| `duration_h` | Positive interval hours; contiguous intervals, no gaps, overlaps or crossing a month boundary |
| `outdoor_temp_C` | Finite °C; duration-weighted mean for monthly aggregation |
| `zone_heating_kWh`, `ahu_heating_kWh`, `zone_cooling_kWh`, `ahu_cooling_kWh` | Nonnegative useful sensible energies; separate net sensible AHU boundary |
| `dhw_kWh` | Nonnegative useful DHW energy before downstream losses and solar offset |
| `appliances_kWh`, `fans_kWh`, `base_auxiliary_kWh` | Nonnegative electricity, independent of thermal internal-gain mappings |
| `pv_generation_kWh` | Available AC electricity before self-consumption/import/export accounting |
| `solar_thermal_available_kWh` | Available heat at DHW generator bus before monthly matching |

Every quantity is required and numeric; unused quantities are explicit zero. Missing, nonfinite, negative-demand or boolean numeric values fail validation. Monthly rows start on day one and cover the full calendar month. The standalone energy API accepts leap-month durations; the current whole-project EPW reader still restricts weather runs to non-leap years. These are different contracts.

## Energy outputs and aggregation

`energy_intervals.csv` (compressed for dynamic cases) contains inputs plus service delivered/auxiliary energy, gross and imported energy by carrier, solar use/curtailment, PV self-use, grid import/export, import impacts, export credits, net impacts and balance residuals. `service_intervals.csv` identifies service, technology and carrier and exposes performance, temperature-clipping flag, chain efficiency, required/generated heat, delivered energy, auxiliaries, downstream losses and conversion residual.

`energy_monthly.csv` / `energy_annual.csv` sum additive energy/impact/cost columns, stamped with building, model, representation and resolution. Period/year are aggregation keys. `service_monthly.csv` / `service_annual.csv` group by service, technology and carrier; effective performance is generated heat/delivered energy, undefined when no delivered energy is present. Do not fill that undefined ratio with a fictitious COP of zero.

`thermal_zone_*`, `zone_service_*` and `zone_ancillary_*` files preserve individual-zone evidence. Renewable meter accounting belongs to the building, so zone service allocations are not measured or separately simulated zone grid imports. `manifest.json` is authoritative for case identities and source/config/code hashes. `energy_config_resolved.json` records the explicit scenario. The energy CLI output contract differs from the thermal-only `monthly.csv` contract above.

The [workbook field map](workbook_instructions.md) links these quantities to Excel columns and calculation sheets. All 85 additive monthly energy/impact quantities in the reference run are independently recalculated; the frozen reference feeds checks only. Numeric comparison uses absolute error ≤ 1e-6 + 1e-9 × |reference| in each stated unit; identifiers/categories match exactly.

## External asset assessment contract

The [optional pipeline contract](pipeline.md) is a separate schema wrapping the
existing project/energy files. Its assessment setting defaults to false. When
enabled, it binds one assessment ID to the project and completed energy
provenance, selects modules, pins external inputs and optionally checks the
auto/direct inventory. It preserves this CSV contract and the legacy Assessment
runner. Processing status and declared coverage are recorded separately; annual
operation is never automatically added to full-study-period totals.

LCC, LCA and MCI use a separate long-form CSV after external asset assessment.
It records stable building/asset/category identifiers, scope action, explicit
`base_quantity`, `sizing_factor`, `assessed_quantity`, quantity unit and sizing
basis, followed by module, metric, life-cycle stage, value, unit, study metadata,
status and source. The validator requires `assessed_quantity = base_quantity ×
sizing_factor`. Reported values are already aggregated for that assessed asset
and are not multiplied again.

All supplied numeric fields must be finite; numeric booleans are rejected.
LCC needs an integer price year and total monetary unit matching its currency.
Study horizons and LCC price bases agree within an assessment/building. One asset
has one current MCI row. Required identities preserve leading zeros and reject
actual missing values. Operational joins require a resolved energy currency,
unique annual case identities and a completed source manifest when present.

Static asset results are stored once per assessment and building. Annual
operational results from `Energy_carriers` remain separated by model,
representation and resolution. Missing results remain unavailable rather than
becoming zero. The full fields, canonical asset mapping, aggregation rules and
runner outputs are defined in [asset assessment integration](assessment_integration.md).

Completeness applies to declared rows. Omitting an asset/metric combination does
not establish a whole-building assessment; external tools must explicitly emit
missing/not-applicable rows for their intended inventory.
