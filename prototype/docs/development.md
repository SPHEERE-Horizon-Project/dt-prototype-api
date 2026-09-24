# Development and web integration

## Reproduce a development environment

Run from the repository root using Python 3.12 for the audited dependency set:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-verified.txt -e '.[dev]'
python -m pytest -q -p no:cacheprovider --basetemp outputs/tests_NEW
python -m dt_prototype.integration.model3.test_model3
```

Use a new `--basetemp`: pytest deletes an existing temporary directory supplied
through that option. Do not point it at a completed run or source data.
`requirements-verified.txt` pins direct dependencies; it is not a complete
cross-platform lock. Record interpreter and resolved dependency versions in
release evidence. The September audit environment is `.venv-audit` locally.

There is no Git metadata in the received folder. Initialize version control
as a deliberate project setup step and retain LICENSE/THIRD_PARTY_NOTICES.md.
The existing `.gitignore` excludes environments, caches and generated runs.

## Responsibilities and change boundaries

| Area | Owns | Required verification when changed |
|---|---|---|
| `common/project.py`, `common/input_validation.py` | Versioned shared configuration | Invalid values fail before computation; both geometry routes remain equivalent |
| `common/preprocessing/` | Geometry, schedules, weather and material/system libraries | Units, calendar alignment, serialisation and known reference inputs |
| `dynamic/` | 5R1C/7R2C time integration and systems | Both networks, ideal/plant cases, signs, latent/system balances and annual energy |
| `monthly/` | Monthly semi-stationary balance | Five-building monthly regression and limiting cases |
| `integration/mapping/` | Conversion into simplified inputs | Conductance/gain preservation and explicit approximation warnings |
| `integration/model3/` | Preserved independent simplified model | Byte-for-byte golden CSV regeneration; document any intentional baseline change |
| `integration/five_parameter.py` | Independent energy-signature regression | Synthetic recovery, bounds, held-out validation, excluded data and source identity |
| `cli.py`, `integration/` reporting | Run orchestration and output contracts | Failure isolation, manifest status, safe paths and output units/identity |

Do not modify reference outputs merely to make a failing test pass. First
decide whether the failure is an implementation defect, an input correction,
or an intentional change in physical assumptions. Record that decision and
its numerical effect. Keep useful thermal demand and delivered carrier energy
as separate quantities throughout comparisons and inverse modelling.

## Validate a new dataset

Follow [the dataset tutorial](input_dataset_tutorial.md) and
[the supported input contract](data_contracts.md). Preserve received data and
create a new processed dataset version for changes. The examples are regression
fixtures and should remain unchanged.

A preflight can load configuration and preprocess inputs without solving:

```python
from dt_prototype.common.project import ProjectInputs

project = ProjectInputs.load('configs/example_tabular.json')
district = project.preprocess()
print(district.building_names)
print(project.hashes())
```

This catches structural errors and unsupported controls. Review areas, volumes,
surface orientation, zoning, schedule units and envelope assignments against
their sources as well. A plausible number can still describe the wrong building.
Preprocessing errors currently stop the whole district; solver errors are
isolated per building by the common CLI.

## Run verification and inspect its outcome

```powershell
python scripts/compare_tools.py --run-id NEW_COMPARISON
python scripts/compare_tools.py --worker dynamic --diagnostic --output outputs/NEW_DIAGNOSTICS
python -m dt_prototype.integration verify-supplied-reference --outputs-root outputs --run-id NEW_SEASONAL --comparison-mode seasonal_ahu
python -m dt_prototype.integration build-5p-report --source-run-dir outputs/NEW_SEASONAL --outputs-root outputs --run-id NEW_5P
```

`compare_tools.py` exercises dynamic 5R1C/7R2C, basic/extended AHU, ideal loads,
plants with latent loads, design-day/static sizing, monthly paths and both
Model 3 mapping modes. The separate diagnostic command covers ideal loads
with latent balance and plants with sensible balance. The script's tests cover
engine directories; run the root pytest command as well to include shared-input
and CLI regression tests. Worker failures now propagate as nonzero process
exit codes. Inspect `manifest.json`, worker `failures.json`, and warnings.

All six standalone launcher variants were also checked in the audit using
`scripts/verify_entry_points.py`; that script requires a separately prepared
`monthly_comparison.csv` report and compares 60 building-month rows per variant.
It is a command-line consistency check, not independent physical validation.

### Spreadsheet verification

The workbook verifies mapped monthly simplified balances for 13 cases and 156
case-months. It does not parse EPWs or implement the inverse fitter. A building's
collapsed result and its individual zones are separate cases; do not sum all
13 annual rows to obtain a portfolio total.

```powershell
node scripts/check_workbook.mjs outputs/NEW_WORKBOOK_CHECK
```

This optional check requires Node.js and `@oai/artifact-tool` resolvable by the
script. In the Codex audit, `scripts/node_modules` is an ignored junction to the
bundled runtime dependencies. It is not a distributable project dependency.
On another machine, use an available compatible calculation engine or configure
that package explicitly. Importing values with openpyxl alone does not
recalculate formulas.

The checker recalculates without exporting or changing the original workbook,
scans all 13 sheets for formula error values, requires 156 PASS rows, writes
JSON evidence with the source hash, and exits nonzero on failure. It refuses to
overwrite existing evidence. Excel-native recalculation is a separate check;
the audit used the artifact-tool engine.

## Web-platform boundary

The current package has no HTTP service, authentication, upload handling, task
queue or browser interface. The computation layer can be integrated behind
those components. Keep engine selection explicit and use one schema/form for
common inputs; expose engine-specific options only where they apply.

For the next iteration:

1. Add a versioned request schema at the service boundary. Translate uploaded
   dataset IDs into server-managed paths. `ProjectInputs` currently accepts
   local filesystem paths and is not an upload authorization boundary.
2. Run simulations in separate worker processes with an isolated run directory.
   Keep CPU work off the HTTP request loop. Do not share mutable preprocessed
   objects across simultaneous jobs without testing that execution path.
3. Generate run identifiers on the server; bound dataset size, number of steps
   and inverse grid size. New output names prevent direct identifier path
   traversal but do not provide filesystem isolation or resource limits.
4. Return run status, failed building IDs and warnings. Use the manifest's
   `building_outputs` mapping rather than reconstructing detail filenames.
   Distinguish a partial portfolio from a complete one and a reviewed 5P fit
   from measured-data validation.
5. Benchmark representative 10/100/1,000-building datasets before introducing
   parallel execution or persistent preprocessing caches. Cache keys need
   input hashes, schema/code versions, calendar, timestep and azimuth settings.

Physical work remains separate: measured-data validation, independent solar
benchmarks, warm-up sensitivity, inter-zone coupling, ground modelling and
leap-year support. See [known findings](code_findings.md) for retained model
limitations. Scientific model changes should have their own evidence and review.
