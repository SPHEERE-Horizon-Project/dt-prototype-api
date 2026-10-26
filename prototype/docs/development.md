# Development and web integration

> Lean GitHub distribution: monthly reference fixtures and selected summaries are included. For the complete hourly/Excel evidence and strict 318-table reproduction, follow [validation archive instructions](validation_archive.md).

Use the [operational guide](running_forward_and_inverse.md) for current forward,
inverse and assessment commands, and the [current implementation](reliability_improvements_20261023.md)
for reliability evidence. [Release/CI instructions](release_and_ci.md) cover the
full dependency lock and separate main/worker jobs. Dated audits remain historical.

## Reproduce a development environment

Run from the repository root using Python 3.12 for the audited dependency set:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-verified.txt -e '.[dev]'
python -m pytest -q -p no:cacheprovider
python -m dt_prototype.monthly_ss_simplified.model3.test_model3
python scripts/verify_assessments.py
```

If you explicitly set `--basetemp`, use a new disposable path whose parent
already exists: pytest deletes an existing temporary directory supplied through
that option. Do not point it at a completed run or source data.
`requirements-verified.txt` pins direct dependencies; it is not a complete
cross-platform lock. Record interpreter and resolved dependency versions in
release evidence.

A local Git repository now tracks the source, fixtures and accepted reports.
No remote was created. Retain LICENSE/THIRD_PARTY_NOTICES.md and use the
[release/CI procedure](release_and_ci.md). `.gitignore` excludes environments,
caches, generated runs and private measured inputs.

## Responsibilities and change boundaries

| Area | Owns | Required verification when changed |
|---|---|---|
| `common/project.py`, `common/input_validation.py` | Versioned shared configuration | Invalid values fail before computation; both geometry routes remain equivalent |
| `common/preprocessing/` | Geometry, schedules, weather and material/system libraries | Units, calendar alignment, serialisation and known reference inputs |
| `Dynamic_RC/` | 5R1C/7R2C time integration and systems | Both networks, ideal/plant cases, signs, latent/system balances and annual energy |
| `Monthly_SS/` | Monthly semi-stationary balance | Five-building monthly regression and limiting cases |
| `Monthly_SS_simplified/mapping/` | Conversion into simplified inputs | Conductance/gain preservation and explicit approximation warnings |
| `Monthly_SS_simplified/model3/` | Preserved independent simplified model | Byte-for-byte golden CSV regeneration; document any intentional baseline change |
| `Monthly_SS_simplified/five_parameter.py` | Independent energy-signature regression | Synthetic recovery, bounds, held-out validation, excluded data and source identity |
| `Monthly_SS_VBDD/` | Monthly loss/gain moments, variable bases, solar surrogates and collapse | QSS algebraic equivalence, independent-zone/collapse conservation, fixed/linear variants and 5P power diagnostics |
| `Energy_carriers/` | Shared systems, carriers, renewables and impacts | Analytical balances, curve/domain validation, dynamic/monthly aggregation, five-building comparison and source/input audit |
| `Assessment/` | External asset results, explicit sizing, aggregation and operational joins | Missing/invalid data, exact identities, consistent study/price bases, duplicate detection, MCI mass weighting and source provenance |
| `Inverse_models/` | Interval/meter contracts, 5P facade, isolated OpenDSM worker, saved models and common reporting | Holdout leakage, calendar/quality checks, model identity, worker failures, reload equivalence and real-library tests |
| `pipeline.py` | Forward/reuse/inverse dispatch and optional stages | Default behavior, disabled inputs, preflight, partial status and preservation of completed stages |
| `to_be_integrated/` | Standalone LCC, LCA and Circularity calculations | Source benchmark equivalence, missing factors/zero quantities, rate domains, sizing, MCI identity and CLI exports |
| `spreadsheets/`, `reports/workbooks/` | Final monthly formula companions and evidence | Workbook hashes, cached PASS states, retained native Excel numeric/perturbation/error evidence |
| `cli.py`, `Monthly_SS_simplified/` reporting | Run orchestration and output contracts | Failure isolation, manifest status, safe paths and output units/identity |

Do not modify reference outputs merely to make a failing test pass. First
decide whether the failure is an implementation defect, an input correction,
or an intentional change in physical assumptions. Record that decision and
its numerical effect. Keep useful thermal demand and delivered carrier energy
as separate quantities throughout comparisons and inverse modelling.

The current spreadsheet workflow is in [workbook instructions](workbook_instructions.md).
The cleaned release keeps the final workbooks and their complete native Excel
evidence, without construction previews or source-workbook copies. Changes to
solver/energy code require a fresh shared-energy reference run before refreshing
frozen workbook expectations; documentation-only changes do not alter solver hashes.

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
python -m pytest -q -p no:cacheprovider --junitxml=outputs/reproduction_checks/tests.xml
python -m dt_prototype.monthly_ss_simplified.model3.test_model3

python runners/run_energy_carriers.py --config configs/example.json --energy-config configs/energy_example.json --engine all --output outputs/reproduction_check
python scripts/verify_reproduction.py --reference validation_archive/reports/shared_energy --candidate outputs/reproduction_check --allow-code-changes
python scripts/audit_shared_energy_delivery.py --output outputs/reproduction_check --config configs/example.json --pytest-xml outputs/reproduction_checks/tests.xml
python scripts/verify_release.py --energy-results outputs/reproduction_check --expected-tests 506 --output outputs/reproduction_checks/release.json
```

The test suite covers Dynamic_RC options, Monthly_SS, Monthly_SS_simplified mapping,
Monthly_SS_VBDD variants, schemas, independent entry points and analytical energy-layer
balances, downstream Assessment validation and all three standalone module suites.
It also covers inverse-only and combined execution, saved-model use and actual
OpenDSM workers when the separate environment is installed. Full release evidence
requires those tests to execute, rather than skip. Set `DT_OPENDSM_PYTHON` if the
worker interpreter is outside the default `.venv-opendsm/Scripts/python.exe` path.
The root pytest configuration discovers the standalone tests automatically.
`verify_release.py` checks the cleaned artifact layout, accepted hashes,
row counts, workbook identities/PASS states and documentation links. The optional
fresh all-engine run verifies the complete CLI workflow; `verify_reproduction.py`
then compares every retained CSV, including compressed case-level interval files,
using the project tolerance and exact text/category matching.

The accepted result folders predate the component naming migration. The
reproduction checker maps only exact known hashed old folder names to current
names and rejects collisions. Model-labelled portfolio tables are aligned by
identity because renamed labels have a different lexical sort order.
Interval-only tables retain chronological order. Old/current historical report
hashes are disclosed separately; reconciled values and validation checks must
still match. By default code hashes must also match. `--allow-code-changes`
records every changed source hash without relaxing numeric or category checks.
The frozen baseline predates the supporting Assessment package, so its current
reproduction requires that explicit flag.

`python scripts/verify_assessments.py` checks standalone Python against source
benchmarks and saved LCC/LCA workbook outputs. It does not automate native Excel.
See [the current review](reliability_review_20261022.md) for evidence and limitations.

### Spreadsheet verification

The three workbooks verify `Monthly_SS`, `Monthly_SS_simplified` and `Monthly_SS_VBDD` monthly thermal balances
through shared systems, carriers, renewables and impacts. They do not parse EPWs
or implement the inverse fitter. A building's collapsed result and its
individual-zone sum are alternatives.

```powershell
python scripts/verify_release.py --energy-results outputs/reproduction_check --expected-tests 506 --output outputs/reproduction_checks/release.json
```

The release checker does not recalculate Excel formulas. It verifies that the
final files match the hashes produced after native Excel recalculation and that
their saved baseline audit rows are all `PASS`. The retained report contains
66,748 native numeric comparisons plus perturbation, error-scan and save/reopen
evidence. Formula changes require a new native Excel validation run and new
versioned workbook evidence.

The command above assumes the fresh baseline and attached JUnit evidence from
the previous section. The historical default deliberately rejects current source
drift; it is not a standalone check of a newly changed checkout.

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
