# Shared input and output contracts

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

Both routes construct the same `BuildingGeometry` and then use the same envelope, schedule, system and weather preprocessing. JSON files hold the existing envelope, schedule and system definitions. The EPW remains the single weather source. Physical units and remaining field checks are defined in the retained readers; this contract does not claim comprehensive validation of every possible malformed source.

The loader rejects missing source files, missing explicit operating fields, invalid options, non-finite initial conditions and duplicate/empty IDs or names. Baseline physical inputs are not calibrated or overwritten.

### Supported calendar and controls

- `calendar_year` must be an integer non-leap year. The reader requires 8,760 ordered hourly records. EPW source years may vary for a typical meteorological year, but month/day/hour must run from January 1 hour 1 to December 31 hour 24. Timestamps use local standard time and the configured year determines schedule weekdays.
- `time_steps_per_hour` must be one of `1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60`. Weather is linearly interpolated and schedules are held within each hour. The final hour is extended with its last value. Interpolation does not create new measured weather observations.
- `azimuth_subdivisions` must be an integer from 1 to 360. The default remains 8. Bins use integer-degree labels consistently in generation and lookup.
- Season bounds must be integer days 1–365, inclusive. A start after the end wraps over New Year. Initial temperature is °C and initial specific humidity is a non-negative humidity ratio in kg/kg.
- Toggles are JSON `true`/`false`, never strings. Heating maximum power is non-negative W; cooling maximum power is non-positive W; `null` means unlimited. Sizing is `static` or `design_day`.
- Model names are `5R1C` or `7R2C` (legacy `1C`/`2C` aliases remain accepted in configuration). Simplified comparison mode is `legacy` or `seasonal_ahu`; zone mode is `sum`, `collapsed` or `both`. Unknown operating/dynamic setting names are rejected.

Missing/sentinel, non-finite or out-of-range values in EPW dry-bulb/dew-point temperature, pressure, humidity, irradiance or wind speed are rejected with a field and line number. No automatic gap filling is performed. The simulation contract restricts relative humidity to 0–100%, even though the [EnergyPlus EPW dictionary](https://bigladdersoftware.com/epx/docs/24-1/auxiliary-programs/energyplus-weather-file-epw-data-dictionary.html) permits values up to 110%. Unused sky-cover data are not used as a rejection criterion. This is targeted validation, not a complete EPW conformance validator.

## Mapping by tool

| Input | Dynamic | Monthly | Simplified |
|---|---|---|---|
| Geometry/envelope | RC network parameterisation | Monthly conductance and capacity | Mapped conductance, area/volume and nearest mass class |
| EPW | Hourly boundary | Monthly balance with prepared hourly gains | Monthly temperature, irradiation-derived gains and AHU conditions |
| Schedules | Time-varying loads and controls | Seasonal availability and gains | Monthly gains, annual-mean airflow and active setpoints |
| Zoning | One zone or independent two-zone execution | Same topology | Native single zone, explicit collapse, or independent-zone sum |
| Systems | Plant/carrier options where enabled | Useful sensible demand | Comparison outputs focus on useful sensible demand; legacy technical-system functions remain available |

Common inputs do not imply identical equations or temporal approximations. The spreadsheet consumes the simplified mapped input tables, not the raw common geometry or EPW sources. It therefore remains an independently recalculating companion to that input adapter.

## Common result contract

CLI `monthly.csv` includes `run_id`, `engine_id`, `building_id`, `building_name`, `scenario_id`, `weather_id`, `period_id`, `zone_count`, `representation`, and numeric `zone_heating_kWh`, `zone_cooling_kWh`, `ahu_heating_kWh`, `ahu_cooling_kWh`, `heating_kWh`, `cooling_kWh`.

Heating and cooling are positive useful sensible energy. Total demand is zone plus sensible AHU; heating and cooling signs are separated per zone before addition. Dynamic raw files retain their original signed power columns and technical-system results. Delivered/carrier energy is a distinct boundary.

The comparison workflow retains its richer monthly schemas, per-zone results and mapping manifests. `aggregate` alone is insufficient to establish comparability: use the variant and representation fields. Annual CSVs sum each actual building once. Run manifests record source/configuration hashes, resolved options, dependencies and failed buildings.

Detailed CLI files now use a bounded, portable building-ID name plus a hash instead of the display name. Read `manifest.json` → `building_outputs` to locate a building's detail file; failed buildings can have a listed filename without a completed file. Original IDs and names remain in tables. Mapped simplified directories use the same safe naming rule, and detailed/summary weather IDs share the EPW hash. Consumers of old display-name filenames must migrate to the manifest. `--model` is only accepted for dynamic runs; `--zone-mode` only for simplified runs.

Integration report `run_id` values must start with a letter/digit and contain 1–64 ASCII letters, digits, underscores or hyphens. Reserved Windows device names are rejected. Direct CLI `--output` remains an explicit filesystem path chosen by the caller.

5P measured-series contracts and calibration/validation rules remain in [the retained methodology](five_parameter_energy_signature.md). No measured energy was introduced by this refactor.
