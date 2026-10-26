# Input contracts and validation before execution

The optional `run_preflight.py` command validates inputs without invoking a
thermal solver or fitting an inverse model. Existing runners and valid input
files retain their behavior. Preflight expands physical weather and schedules,
so a large district may still take time and memory to validate.

Run from the project root with the main environment and `PYTHONPATH=src`:

```powershell
python runners/run_preflight.py --config configs/pipeline_example.json --report outputs/checks/forward.json
python runners/run_preflight.py --kind project --config configs/example_tabular.json
python runners/run_preflight.py --kind energy --config configs/energy_example.json
python runners/run_preflight.py --kind inverse --config configs/inverse_5p_example.json
```

The JSON report collects independent schema, path, library, domain and
preprocessing errors. Exit **0** means checked inputs passed; **1** means input
validation failed. Report files are optional and cannot overwrite an existing
file. No output directory for a simulation is created. No packages are downloaded.
For OpenDSM selections, preflight launches a short import/version probe in the
configured worker interpreter, but does not fit a model.

For a forward run with inverse analysis enabled, the future energy results do
not exist yet. Their validation is explicitly **deferred** to the simulation
handoff. Other deferred items include fit convergence, native qualification and
prediction accuracy. A passed preflight is input readiness, not a guarantee that
every solve or fit will succeed. A saved-model preflight checks artifact hashes,
physical identity and clock. A reuse pipeline also checks energy provenance.

## Versioned machine-readable contracts

The [schema directory](../src/dt_prototype/schemas/v1/) ships JSON Schema 2020-12
documents for project, pipeline, energy, inverse, envelope, schedule and system
inputs, and parsed observation/weather CSV rows. Contract version **v1** covers
the existing `schema_version: "1.0"` formats; no migration is required. Legacy
library files keep their existing wrapper or plain-record forms and `_comment`
metadata. New unknown computational fields fail the preflight schema check.

Schema IDs are stable `urn:dt-prototype:input:v1:...` identifiers, resolved
locally; no network schema lookup is needed. JSON allows a UTF-8 BOM, but duplicate
keys and nonfinite numbers are rejected by the existing strict reader. Schemas
describe structural/numeric domains. Existing Python readers check calendar
validity, geometry references, temperature/time coverage, performance curves and
cross-record consistency. Those semantic checks cannot be replaced by a JSON
schema alone.

`observations-row.schema.json` and `weather-row.schema.json` describe **parsed**
CSV rows: numeric cells become numbers; missing energy/GHI cells become null;
identifiers and timestamps stay strings. The inverse CSV reader checks headers,
row widths and temporal semantics. Headers are case-sensitive. Energy is kWh per
explicit interval, temperatures are °C, and GHI is W/m² for an hourly interval.
Never supply kW under an energy header. IDs such as `001` remain strings.
Geometry table and assessment CSV contracts retain their native validators and
are specified in [data contracts](data_contracts.md) and
[assessment integration](assessment_integration.md); the new row schemas do not
claim to describe every CSV output or every geometry exchange format.

To deliberately change the schemas, edit
[build_input_schemas.py](../scripts/build_input_schemas.py), regenerate them and
run the contract tests. The generator never infers types from a particular
building's data. Tests check generated/shipped equality and the supplied valid
examples, as well as malformed-input rejection. Future incompatible changes
must receive a new schema version and an explicit migration plan.

## Boundaries

Preflight is an explicit separate step. It intentionally adds stricter checks
without silently modifying original scientific inputs or forcing a new
validation dependency into the isolated OpenDSM runtime. Optional disabled
assessment/analysis inputs retain the runner's deferred semantics. It does not
check external asset prices for realism or certify any normative calculation.
