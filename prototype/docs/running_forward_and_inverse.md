# Running DT-Prototype: forward, inverse and optional assessment

> Lean GitHub distribution: monthly reference fixtures and selected summaries are included. For the complete hourly/Excel evidence and strict 318-table reproduction, follow [validation archive instructions](validation_archive.md).

This is the current operational guide, updated on 24 October 2026. Run commands
from `2026_09_23_DT-Prototype`. Existing output directories are protected: choose
a new name for each run and adjust downstream `results`/`model_dir` paths to match.
Keep accepted references under `reports/` unchanged.

For the full dependency lock, CI jobs and portable source recipe, see
[release and CI instructions](release_and_ci.md). Validate inputs first with
[preflight](input_preflight.md). When measured data become available, use the
[measured-data template and acceptance procedure](measured_data_validation.md).

## 1. Install or check the two environments

Python **3.12** is the verified interpreter. Main calculation dependencies are
pinned in `requirements-verified.txt`; OpenDSM has a separate dependency set.
The commands below use explicit interpreters, so PowerShell activation is optional.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-verified.txt -e '.[dev]'
.\.venv\Scripts\python.exe -m pip check

# Required only for OpenDSM billing/hourly:
python -m venv .venv-opendsm
.\.venv-opendsm\Scripts\python.exe -m pip install -r requirements-opendsm-verified.txt
.\.venv-opendsm\Scripts\python.exe -m pip check
```

For the remaining commands, `python` means the installed main environment's
interpreter; activate it or replace `python` with `.\.venv\Scripts\python.exe`.
For a source checkout using an already prepared Python environment, set
`$env:PYTHONPATH='src'` instead of installing the package. Run OpenDSM through the
inverse runner; `opendsm_python` selects its isolated worker. Installing OpenDSM
into the main pandas 3 environment is unsupported by the verified dependency sets.

The full OpenDSM freeze is tested on Windows/Python 3.12. Other platforms and
Python versions need their own dependency resolution and verification. The
package's broader Python declaration is not evidence that every combination
has been tested. No model downloads packages at execution time.

## 2. Choose the execution path

| Goal | Runner / setting | Required inputs |
| --- | --- | --- |
| Thermal demand | Individual thermal runner | Shared project JSON, geometry, EPW, schedules, envelope and systems libraries |
| Thermal plus delivered energy/renewables | `run_energy_carriers.py`, or forward pipeline | Shared project JSON plus energy JSON |
| Energy plus asset assessment | Forward pipeline, `assessment.enabled=true` | Above plus external whole-asset LCC/LCA/MCI results; optional resolved quantities |
| Fit measured/simulated energy | `run_inverse_models.py`, `operation=fit` | Explicit interval energy, weather, identity, quality and train/validation split |
| Use an existing fitted model | Same runner, `predict` or `evaluate` | Saved model directory and compatible interval/weather input; evaluate also needs observed targets |
| Inverse-only orchestration | Pipeline `mode=inverse` | `inverse_config`; no geometry or project energy calculation |
| Fit results immediately after forward simulation | Forward `analysis.enabled=true` | Inverse configuration with `source.type=energy_run` |

Forward solvers share input preparation and Energy_carriers. Inverse backends
share interval/meter inputs and reporting. Choosing an inverse backend does not
identify physical conductances, capacities or efficiencies automatically. Its
predicted meter energy must not be passed through conversion/PV matching again.

## 3. Run the four forward families

For all tested solver variants through the common energy layer:

```powershell
python runners/run_pipeline.py --config configs/pipeline_example.json --output outputs/my_forward
```

The default is forward mode with assessment and inverse analysis disabled.
Results are under `outputs/my_forward/energy`. The accepted all-engine example
has 51 building/model/representation cases and 612 building-months. The `all`
selector includes both RC networks and the standard monthly alternatives;
choose one family explicitly when comparing another parameter configuration.

For a single family with energy conversion:

```powershell
python runners/run_energy_carriers.py --config configs/example.json --energy-config configs/energy_example.json --engine Dynamic_RC --model 7R2C --output outputs/my_dynamic_energy
python runners/run_energy_carriers.py --config configs/example.json --energy-config configs/energy_example.json --engine Monthly_SS --output outputs/my_monthly_energy
python runners/run_energy_carriers.py --config configs/example.json --energy-config configs/energy_example.json --engine Monthly_SS_simplified --zone-mode both --output outputs/my_simplified_energy
python runners/run_energy_carriers.py --config configs/example.json --energy-config configs/energy_example.json --engine Monthly_SS_VBDD --solar direct --utilisation monthly_balance --output outputs/my_vbdd_energy
```

For thermal demand only, use the corresponding runner without `--energy-config`:

```powershell
python runners/run_dynamic_rc.py --config configs/example.json --model 5R1C --output outputs/my_dynamic_thermal
python runners/run_monthly_ss.py --config configs/example.json --output outputs/my_monthly_thermal
python runners/run_monthly_ss_simplified.py --config configs/example.json --zone-mode both --output outputs/my_simplified_thermal
python runners/run_monthly_ss_vbdd.py --config configs/example.json --output outputs/my_vbdd_thermal
```

Both geometry routes are supported: `example.json` uses GeoJSON and
`example_tabular.json` uses `buildings.csv`, `zones.csv`, `surfaces.csv`.
Input file paths resolve relative to their JSON configuration. Project JSON
requires `schema_version`, `inputs`, `operating`, `dynamic`, `simplified`;
`description` is optional. Unknown settings, duplicate keys and nonfinite JSON
numbers are rejected. UTF-8 with or without BOM is accepted for these JSON inputs.

The shared energy boundary requires dynamic `plants=false`, `latent=false`,
`pv_battery=false`, and simplified `comparison_mode=seasonal_ahu`. Otherwise
systems or renewables could be counted twice or the compared loads could differ.
See [data contracts](data_contracts.md) and [energy methods](shared_energy_layer.md).
The EPW simulation calendar remains a complete non-leap year in local standard time.

## 4. Add LCC, LCA or MCI results

The pipeline **imports and aggregates externally assessed whole-asset values**.
It does not invoke the standalone factor/cost calculators under `to_be_integrated/`.
Those remain available independently. Auto/direct quantities prepare an inventory
for external valuation; they do not change installed plant in the energy solver.

```powershell
python runners/run_asset_quantities.py --inputs configs/asset_quantities_example.json --catalogue configs/asset_catalogue.json --config configs/example.json --output outputs/my_quantities
python runners/run_pipeline.py --config configs/pipeline_assessment_example.json --output outputs/my_assessed_forward
```

The second command runs a new Monthly_SS calculation plus illustrative LCC/LCA/MCI
totals. To reuse the all-engine run from step 3, copy
`configs/pipeline_reuse_example.json` to another file **in `configs/`**, set
`energy.results` to `../outputs/my_forward/energy`, and execute that copy with a
new output directory. Retain matching project/energy configurations. Simulation
source changes require a fresh run; inverse/assessment orchestration changes do
not invalidate the physical simulation by themselves.

Use `assessment.modules` to select `LCC`, `LCA`, `MCI`; disable the stage or omit
it when unused. Match building/asset IDs, quantity units and study/price bases.
Assessment covers declared assets only. Do not add annual operating values to
lifetime totals without explicitly accounting for overlap and time basis.
See [assessment](assessment_integration.md), [quantities](asset_quantities.md)
and [pipeline contract](pipeline.md).

## 5. Fit inverse models

Runnables with supplied synthetic inputs:

```powershell
python runners/run_inverse_models.py --config configs/inverse_5p_example.json --output outputs/my_5p_fit
python runners/run_inverse_models.py --config configs/inverse_billing_example.json --output outputs/my_billing_fit
python runners/run_inverse_models.py --config configs/inverse_synthetic_example.json --output outputs/my_all_inverse_fit
python runners/run_pipeline.py --config configs/pipeline_inverse_example.json --output outputs/my_inverse_pipeline
```

The all-backend example includes 5P, billing, hourly nonsolar and hourly solar,
with 2022 training and warmer 2023 validation data. It is synthetic, not a measured
building dataset. `allow_disqualified=true` in research examples is explicit;
native warnings and disqualifications remain in the outputs.

To fit all monthly cases from the retained reference, use
`inverse_simulation_example.json`. To fit **your new forward run**, copy that
file within `configs/` and set `source.results=../outputs/my_forward/energy`.
For genuine dynamic hourly results, copy `inverse_dynamic_example.json` and make
the same path change. Monthly energy totals cannot supply hourly model training.
Optional `buildings` and `models` selectors must be lists of exact text IDs; a
requested but absent ID is an error. No substring matching or silent omission occurs.

To analyse immediately after forward simulation, use
`pipeline_forward_inverse_example.json`, or add `analysis.enabled=true` and
`analysis.config` to a forward configuration. The analysis source must be
`energy_run`; it receives the completed energy directory. Assessment and analysis
can both be enabled independently. A later failure preserves completed energy.

## 6. Prepare measured data and predict/evaluate

Observation CSV columns are `series_id,interval_start,interval_end,energy_kWh,split,quality`.
The first three are mandatory. Energy is interval **kWh**, not average power or
a cumulative register. Blank energy is permitted for prediction. Unknown columns
are rejected; exported `duration_h` is an optional checked value, not an override
of the timestamps. Temperature weather columns are `time,temperature_C`, with
optional `weather_id,ghi_Wm2`. Use a decimal point, comma delimiter and UTF-8.

For example, put actual data in `data/processed/my_meter/`, then create this
configuration in `configs/` after replacing the identities and paths:

```json
{
  "schema_version": "1.0",
  "operation": "fit",
  "clock": {"convention": "civil", "timezone": "Europe/Rome"},
  "source": {
    "type": "csv",
    "observations": "../data/processed/my_meter/observations.csv",
    "weather": "../data/processed/my_meter/weather.csv",
    "series": {
      "meter-001-import": {
        "source_type": "measured", "source_id": "meter-export-v001",
        "building_id": "001", "scenario_id": "as-operated",
        "carrier": "electricity", "meter_boundary_id": "electricity_grid_import",
        "weather_id": "default"
      }
    }
  },
  "models": ["5p_monthly"]
}
```

Each timestamp marks a half-open interval `[start,end)`. Preserve explicit offsets
at DST transitions; ambiguous/nonexistent naive local timestamps are rejected.
Use `standard` plus `Etc/GMT-1` for fixed UTC+1 data. Hourly weather must cover all
intervals. Monthly 5P requires complete calendar months; billing accepts actual
midnight bill boundaries; hourly accepts genuine hourly/subhourly energy.

Mark `split` as `train`, `validation`, `test`, `excluded`, or `predict`; mark
`quality` as `valid`, `missing`, or `excluded`. Date cutoff settings can replace
train/validation/test labels, but preserve explicit excluded/predict rows.
`validation_end` requires `train_end`, and a cutoff cannot cut an interval.
For 5P or billing derived from hourly data, assign whole-month splits. Holdout
targets never train the model. A validation label with no usable target is not
reported as an observed holdout. Additional buildings/meters use distinct series
metadata; they are fitted individually, not pooled.

Copy `inverse_prediction_example.json` within `configs/`, point `model_dir` at
`../outputs/my_all_inverse_fit`, and set source paths/identities to your intended
prediction dataset. For forecasting, blank `energy_kWh` and use `split=predict`.
For scoring, set `operation=evaluate` and supply eligible observed energy.
Both operations load saved models without refitting. Omitting `models` loads
each series' available artifacts; explicitly requested missing models fail visibly.
Identity and clock must match training. See [the full inverse contract](inverse_models.md).

## 7. Inspect results and verify a release

Start with the top-level pipeline `manifest.json`, then each stage's manifest
and report. Energy exports include `energy_monthly.csv`, `energy_annual.csv`,
service/carrier details and balance checks. Inverse exports include a report
with statuses and figure links, predictions, native/monthly metrics, common-support
comparisons, artifacts, native diagnostics and worker logs. A collapsed model
and independent-zone sum are alternatives, never additive portfolio entries.

Pipeline/inverse exit codes: **0 complete**, **2 partial/incomplete**, **1 failed**.
Processing success does not imply model qualification, measured accuracy or complete
asset coverage. Inspect missing/failed models and use the same physical boundary
and interval resolution when comparing scores. The supplied hourly grid-import
cases now complete for all five buildings with the recorded
[OpenDSM metrics compatibility fix](opendsm_compatibility.md). Affected fits
remain flagged for review; native uncertainty remains missing in these cases.

For a fresh review, choose unused output and evidence directories:

```powershell
python -m pytest -q -p no:cacheprovider --junitxml=outputs/my_checks/tests.xml
python -m dt_prototype.monthly_ss_simplified.model3.test_model3
python scripts/verify_assessments.py --output outputs/my_checks/assessments.json
python scripts/verify_reproduction.py --reference validation_archive/reports/shared_energy --candidate outputs/my_forward/energy --allow-code-changes --output outputs/my_checks/reproduction.json
python scripts/audit_shared_energy_delivery.py --output outputs/my_forward/energy --config configs/example.json --pytest-xml outputs/my_checks/tests.xml
python scripts/verify_release.py --energy-results outputs/my_forward/energy --expected-tests 506 --output outputs/my_checks/release.json
```

The current suite has 503 tests plus three subtests: 506 JUnit records, with the
OpenDSM environment installed. Optional native-worker tests skip when it is absent;
the full release check requires zero skips. The release command is for the supplied
all-engine baseline (612 months), not an arbitrary building dataset. Its default
source is historical and deliberately fails if current source hashes differ.
Pass a fresh baseline as shown; never rewrite historical manifests to bypass it.
The workbook checks compare hashes/cached results with retained native Excel
evidence; they do not perform a new Excel recalculation.

Current implementation: [findings and evidence](reliability_improvements_20261023.md).
