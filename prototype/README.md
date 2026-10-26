# DT-Prototype 0.5.1

This is the lean GitHub publication copy. Start with [upload and setup instructions](UPLOAD_TO_GITHUB.md). Monthly reference fixtures and validation summaries are included; full hourly/Excel evidence is in the [optional validation archive](docs/validation_archive.md).

Start with the [forward/inverse run guide](docs/running_forward_and_inverse.md)
for setup, model selection, measured inputs, assessment settings and verification.
The [reliability improvements](docs/reliability_improvements_20261023.md), completed
24 October 2026, implement the agreed actions from the earlier review. See also
[preflight input checks](docs/input_preflight.md), [measured-data validation](docs/measured_data_validation.md)
and [version control, CI and releases](docs/release_and_ci.md).

DT-Prototype is organized around five named software components. Four calculate
thermal demand; `Energy_carriers` applies systems and renewables downstream.

| Component | Calculation | Launcher |
|---|---|---|
| `Dynamic_RC` | Dynamic_RC 5R1C or 7R2C | `runners/run_dynamic_rc.py` |
| `Monthly_SS` | Monthly semi-stationary/steady-state balance | `runners/run_monthly_ss.py` |
| `Monthly_SS_simplified` | Simplified semi-stationary monthly model, historically called Model 3, with integrated energy-signature inverse modelling | `runners/run_monthly_ss_simplified.py` |
| `Monthly_SS_VBDD` | Variable-base degree-day model from simplified semi-stationary equations | `runners/run_monthly_ss_vbdd.py` |
| `Energy_carriers` | Technical systems, carriers, renewables, grid exchange and impacts | `runners/run_energy_carriers.py` |

The supporting `Assessment` runner consumes externally aggregated LCC, LCA and
MCI results for physical assets, validates explicit sizing, and reports them
beside solver-specific annual outputs without changing the five components.

The supporting `run_asset_quantities.py` prepares a shared inventory using
`auto` (estimate × factor) or `direct` (unchanged input), with m2, kW, kWh and
litres as defined in the [asset quantity guide](docs/asset_quantities.md).
It accepts JSON or the new fillable Excel input and does not resize the solvers.

The optional [pipeline runner](docs/pipeline.md) runs the existing energy chain
with external LCC/LCA/MCI aggregation enabled or disabled by a setting (default
disabled). It can also reuse a compatible completed energy run. Standalone
calculators are not invoked, and annual operation stays separate from lifetime
asset totals.

The supporting [inverse-model layer](docs/inverse_models.md) fits monthly 5P,
OpenDSM billing and OpenDSM hourly (solar/nonsolar) models to simulated or
measured energy. It supports saved-model prediction, held-out evaluation,
inverse-only execution and optional analysis after forward simulation.
OpenDSM runs in a separate pinned environment; the thermal solvers are unchanged.

The authoritative five-building result is the
[shared-energy comparison report](reports/shared_energy/comparison_report.md).
The three current formula workbooks are indexed by the
[workbook instructions](docs/workbook_instructions.md), with independent
[native Excel validation evidence](reports/workbooks/workbook_validation.md).

## Install and run

Use Python 3.12 to reproduce the verified environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-verified.txt -e '.[dev]'

python runners/run_energy_carriers.py `
  --config configs/example.json `
  --energy-config configs/energy_example.json `
  --engine all `
  --output outputs/my_energy_comparison
```

Each thermal solver can also run independently:

```powershell
python runners/run_dynamic_rc.py --config configs/example_tabular.json --output outputs/my_Dynamic_RC --model 5R1C
python runners/run_monthly_ss.py --config configs/example_tabular.json --output outputs/my_monthly
python runners/run_monthly_ss_simplified.py --config configs/example_tabular.json --output outputs/my_simplified --zone-mode both
python runners/run_monthly_ss_vbdd.py --config configs/example_tabular.json --output outputs/my_vbdd
```

External asset results can then be validated and aggregated independently:

```powershell
python runners/run_assessment.py --asset-results configs/asset_results_example.csv --energy-results outputs/my_energy_comparison --output outputs/my_assessment
```

To orchestrate energy and optional external assessment together:

```powershell
python runners/run_pipeline.py --config configs/pipeline_example.json --output outputs/pl_off
python runners/run_pipeline.py --config configs/pipeline_reuse_example.json --output outputs/pl_join
```

Output directories must be new. Thermal and energy runners use versioned inputs under
`configs/` and `data/examples/`. GeoJSON and normalized CSV geometry routes are
equivalent examples. The [input and result contracts](docs/data_contracts.md)
define units, identifiers, calendars, representations and missing-value rules.

Selected surfaces can now specify optional `boundary_condition=adiabatic` in
the shared geometry tables. Missing/blank values retain existing behaviour.
The [adiabatic surface guide](docs/adiabatic_boundaries.md) covers examples,
retained construction/mass, renewable separation and fully enclosed-zone limits.

The comparable shared-energy run uses useful sensible zone demand plus separate
net sensible AHU demand. Dynamic configuration must set `plants=false`,
`latent=false` and `pv_battery=false`; the common downstream layer then performs
conversion and renewable accounting once.

## Current release contents

- `src/dt_prototype/`: production package.
- `configs/`, `data/examples/`: reproducible example inputs.
- `runners/`: thin executable launchers.
- `tests/` and the standalone module test folders: 503 automated unit, regression and integration tests, plus three unittest subtests.
- `spreadsheets/`: the three final monthly verification workbooks.
- `reports/shared_energy/`: compact monthly/annual reference fixtures, comparison text and historical manifest.
- `reports/workbooks/`: native Excel summaries, workbook hashes and preservation evidence; full cell comparisons are archived separately.
- `reports/inverse_models_20261021/`: inverse-model implementation and validation evidence.
- `reports/reliability_review_20261022/`: current forward/inverse reliability review and reproducible evidence.
- `docs/`: current architecture, methods, contracts and extension guidance.
- `scripts/`: release/result verification utilities.
- `to_be_integrated/`: standalone LCC, LCA and Circularity code and verification workbooks.

The root [comparison_report.md](comparison_report.md) is the supplied historical
thermal comparison used as a regression fixture. The current full result is the
report under `reports/shared_energy/`.

## Verification

```powershell
python -m pytest -q -p no:cacheprovider --junitxml=outputs/my_checks/tests.xml
python -m dt_prototype.monthly_ss_simplified.model3.test_model3
# After a new all-engine pipeline run; 506 JUnit records include 3 subtests:
python scripts/audit_shared_energy_delivery.py --output outputs/pl_off/energy --config configs/example.json --pytest-xml outputs/my_checks/tests.xml
python scripts/verify_release.py --energy-results outputs/pl_off/energy --expected-tests 506 --output outputs/my_checks/release.json
python scripts/verify_assessments.py

# Optional: extract the validation archive first, then regenerate and compare all 318 tables:
python runners/run_energy_carriers.py --config configs/example.json --energy-config configs/energy_example.json --engine all --output outputs/reproduction_check
python scripts/verify_reproduction.py --reference validation_archive/reports/shared_energy --candidate outputs/reproduction_check --allow-code-changes
```

The current implementation passes 503 tests and three subtests, including the
standalone LCC, LCA and Circularity suites. See the
[implementation report](docs/reliability_improvements_20261023.md) for scope and evidence.
The earlier [22 October review](docs/reliability_review_20261022.md) records its
473-test baseline; its proposed reliability improvements are now implemented.
Earlier source states are recorded by the
[asset quantity implementation report](reports/asset_quantities_20261021/implementation_report.md)
for mode, Excel and five-building regression evidence. The earlier
[adiabatic boundary implementation report](reports/adiabatic_boundaries_20261015/implementation_report.md)
records the 25 new boundary checks and a fresh comparison of all 318 result
tables with zero numeric difference. The earlier
[15 October code audit](docs/code_audit_20261015.md) records the preceding
322-test source state. The frozen shared-energy release evidence retains
its original 273-test record. Native Excel passed 66,748
numeric comparisons and 530 identity, scenario, perturbation and save/reopen
checks, with zero failures or formula errors. The release verifier also checks
source/input hashes, result row counts, workbook hashes, cached PASS states and
local documentation links. The retained machine-readable
[release audit — full archive](docs/validation_archive.md#reports-release-verification-json) and
[fresh-run comparison — full archive](docs/validation_archive.md#reports-reproduction-verification-json) record historical
checks; that run compared 318 CSV/CSV.GZ files with zero numeric difference.

The release verifier defaults to the frozen historical run and deliberately
rejects different source hashes. Use `--energy-results` for a newly regenerated
baseline and declare its exact `--expected-tests` JUnit count. This preserves
historical evidence rather than relabelling it as a test of changed source.

Start with [architecture](docs/architecture.md),
[shared energy](docs/shared_energy_layer.md),
[asset assessment integration](docs/assessment_integration.md),
[Monthly_SS_VBDD methodology](docs/vbdd_methodology.md),
[workbook instructions](docs/workbook_instructions.md) and
[development guidance](docs/development.md).

These results establish software consistency and model-to-model comparisons.
They do not establish measured-building accuracy or ISO conformity. Required
licensing and attribution are in [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
