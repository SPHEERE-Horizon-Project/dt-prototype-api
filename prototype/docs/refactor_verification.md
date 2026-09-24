# Refactor verification — 2026-09-17

DT-Prototype reproduces the preserved results to floating-point precision after source consolidation and display-name changes.

| Check | Result |
|---|---|
| Full numeric regression | 86 comparisons; 19,642,320 numeric values |
| Maximum absolute numeric difference | 7.275957614183426e-11, in the compared column's original units |
| Regression tolerance | Absolute 1e-7, relative 1e-12; NaN patterns preserved |
| Compared scope | All hourly numeric columns of dynamic variants and diagnostics; all monthly QSS columns; detailed full/simplified mapped monthly outputs |
| Comparison report | 2,928 monthly and 244 annual rows, with renamed cases |
| Workbook vs Python | 156 monthly rows; heating difference <=5.83e-11 kWh, cooling <=1.46e-11 kWh |
| Duplicate QSS compatibility routes | Zero monthly sensible-energy difference |
| Final consolidated suite | 169 passed; repeated after final case-identifier cleanup, 108.11 seconds |
| Independent launchers | Six configurations, 60 monthly rows each; maximum difference 2.9104e-11 kWh |
| Workbook preservation | 9,534 formulas and 3,494 numeric input cells unchanged; sheet order, chart counts and freeze panes preserved |

Detailed evidence: `outputs/20260917_dt_prototype_regression_001/numeric_regression.csv` and `verification.json`. Numeric comparisons use the original stable identifiers; only display strings are translated. The frozen baseline is archived at `archive/previous_outputs/20260917_pre_refactor_baseline/`.

The original suites passed independently before migration. The consolidated retained suite passed 163 tests, and six shared-input tests passed separately. A final combined suite and all six independent launcher configurations are recorded alongside the current outputs. The shared-input tests include a simplified run with both detailed solvers deliberately disabled and a native single-zone input.

## How equivalence was protected

1. Archive original sources, golden outputs and completed runs.
2. Run the original tests and a fresh full baseline before editing calculations.
3. Consolidate readers/input files and duplicate monthly implementations, preserving each physical solver's equations.
4. Compare directly prepared simplified input quantities against the original reference-output mapping.
5. Run all five buildings with both dynamic networks, AHU modes, latent/system switches and sizing options; compare raw numerical columns, not just rounded annual totals.
6. Recalculate the relabelled spreadsheet and reconcile by building/zone/month.
7. Execute the three independent launchers from their own directories and compare their monthly output with the report.

Current documents replace superseded report editions; their unmodified originals remain in the archive. This preserves auditability without presenting redundant historical editions as current results. The root annual side-by-side table is relabelled, and the current full report includes its numerical reconciliation.

The remaining scientific model differences are unchanged. This is regression and cross-model verification, not empirical validation.

## Model 3 pipeline relocation

The required Model 3 pipeline was subsequently moved from the active
`third_party` folder into `src/dt_prototype/integration/model3/`. Its calculation
source, example inputs and golden CSVs are byte-identical. Simplified zone-sum,
collapsed and detailed comparison results have zero numerical difference from
the pre-relocation evidence. See
`outputs/20260917_model3_relocation_verification/verification.json`.
