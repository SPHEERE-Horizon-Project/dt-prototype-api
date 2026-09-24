# Retained methodology (DT-Prototype terminology)

Historical run paths below refer to archived evidence. Current commands are in the root README.

# Five-parameter energy-signature post-processing

## Purpose and boundary

The 5P module is an optional post-processor. It does not modify, import into,
or share equations with either forward-physics engine. It reads completed
monthly results or a canonical mixed simulated/measured CSV and creates a new
immutable report directory.

The fitted response is average daily energy:

```text
E_day = beta_base
      + beta_heating * max(0, T_heating_cp - T_outdoor)
      + beta_cooling * max(0, T_outdoor - T_cooling_cp)
```

The reported energy-signature plot uses monthly average power:

```text
P_average_kW = monthly_energy_kWh / (24 * days)
```

Therefore `beta_base_average_power_kW = beta_base_kWh_day / 24`, and the
heating/cooling slope units become `kW/K`. Month length does not distort the
plot.

For a measured-versus-simulated comparison, both series must use the same
carrier and `meter_boundary_id`. A useful-demand result is not directly
comparable with an electricity or fuel meter.

## Canonical monthly input

One row represents one source, building, scenario, carrier/boundary, and month.
Required columns are:

```text
source_type                 # simulated or measured
source_id                   # engine, meter, or dataset identifier
source_run_id
building_id
scenario_id
weather_id
period_id                   # YYYY-MM
carrier
meter_boundary_id
energy_kWh
days
outdoor_temp_C
calibration_validation_flag # calibration, validation, or excluded
data_quality_flag           # valid, ok, pass, or good are eligible
```

`interpretation_status` is optional. Missing values are never converted to
zero. Duplicate monthly keys are rejected. Only eligible `calibration` rows
enter parameter estimation; `validation` rows remain untouched until metrics
are calculated.

The audit adds explicit rejection of empty datasets, empty identity keys,
unknown source/split labels and non-finite configuration settings. Rows with
missing/non-finite energy or temperature, negative energy, an excluded split,
or an ineligible quality flag are excluded and counted. Invalid finite day
counts (outside 1–31) are structural errors. This module expects monthly,
non-negative consumption; net-export meters need a separately defined boundary.
The caller must verify period coverage, day counts and consistent units.

## Verification defaults

The first implementation uses the historical Model 3 search ranges as explicit,
overridable verification defaults:

- heating change point: 8 to 20 °C;
- cooling change point: 14 to 26 °C;
- grid step: 0.5 K;
- cooling change point not lower than the heating change point;
- non-negative base, heating, and cooling coefficients;
- at least six calibration observations;
- at least two observations in an active heating/cooling regime;
- at least 5 K calibration temperature span.

The three linear coefficients use the full-rank unconstrained least-squares
solution when all coefficients are positive, otherwise exact active-set
enumeration for the small non-negative least-squares problem. No SciPy or plotting dependency is
introduced. These defaults support software verification and the supplied five
buildings; real meter work must record project-specific bounds and split rules.

## Statistical indicators

The residual convention is always:

```text
residual = observed - predicted
```

Positive bias therefore means underprediction. For `n` observations, `p`
effective fitted parameters, observed mean `y_mean`, and residual `e`:

```text
RMSE       = sqrt(sum(e^2) / (n - p))
R2         = 1 - SSE / SST
adjR2      = 1 - (1 - R2) * (n - 1) / (n - p)
NMBE_pct   = 100 * sum(e) / ((n - p) * y_mean)
CV_RMSE_pct= 100 * RMSE / y_mean
NDBE_pct   = 100 * sum(e) / sum(observed)
```

NDBE means **net determination bias error**. Unlike NMBE, it has no fitted-
parameter correction and directly expresses net percentage error over the
evaluated observations. The distinction follows the Bonneville Power
Administration [*Regression for M&V Reference Guide*](https://www.bpa.gov/-/media/Aep/energy-efficiency/custom-project-protocols/3_bpa_mv_regression_reference_guide_v3_final.pdf).
The NMBE and CV(RMSE) forms are consistent with the declared `n-p` formulation
described in the NREL [*Evaluation of Automated Model Calibration
Techniques*](https://www1.eere.energy.gov/buildings/publications/pdfs/building_america/automated_model_calibration.pdf).
This project does not claim ASHRAE or M&V compliance from these calculations
alone.

Calibration metrics use the fitted series' effective parameter count. Untouched
validation metrics and direct simulated-signature-versus-measured metrics use
`p=0`, because no parameters are estimated on those observations.

## Output tables

Each post-processing run contains:

- `regression_parameters_metrics.csv`: one row per source/building/scenario/
  carrier/boundary. It contains all five parameters in daily-energy and
  average-power units, effective/formal parameter counts, regime observations,
  convergence status, warnings, and calibration/validation RMSE, R2, adjusted
  R2, NMBE, CV(RMSE), and NDBE.
- `regression_monthly_predictions.csv`: observed and predicted monthly energy,
  average power, residuals, and split-membership flags.
- `regression_simulated_measured_comparison.csv`: long-form parameter and
  internal-fit-statistic comparison for every exact simulated/measured boundary
  pair.
- `regression_simulated_signature_vs_measured_metrics.csv`: one row per exact
  simulated/measured pair, evaluating the simulated fitted curve directly
  against measured calibration and validation observations.
- `figures/*.svg`: one plot per building/scenario/carrier/boundary, overlaying
  source observations and fitted signatures. Circles are calibration points;
  outlined squares are validation points.
- `manifest.json`: input hash, settings, metric definitions, residual
  convention, counts, and output file inventory.

Manifest status is `complete`, `partial` (some series failed), or `failed`
(all series failed). A report can be written successfully while fits fail:
inspect the manifest and each series' `fit_status` and `warning_codes`.
`REVIEW` is a usable result with warnings, not a claim of validation. Empty
prediction exports retain their column headers. Figure filenames are bounded
and hashed, and the plot distinguishes source type, source ID and source run.

## Commands

Post-process a completed supplied-reference simulation:

```powershell
python -m dt_prototype.integration build-5p-report `
  --source-run-dir outputs/standalone_smoke_20260811_001 `
  --outputs-root outputs `
  --run-id five_parameter_reference_001
```

Process a canonical CSV containing simulated and/or measured data:

```powershell
python -m dt_prototype.integration build-5p-report `
  --input-csv data/processed/five_parameter_monthly_input.csv `
  --outputs-root outputs `
  --run-id five_parameter_measured_comparison_001
```

Change-point bounds and minimum sample/regime criteria are available as command-
line options. Every completed run is immutable and refuses overwriting.

## Supplied five-building verification

The reference-run adapter selects only `zone_id = null` building aggregates and
fits total useful sensible heating plus cooling for both engines. It labels the
series `carrier=useful_sensible` and
`meter_boundary_id=not_metered__useful_sensible_total`, with
`interpretation_status=HEURISTIC_ONLY`. These cases verify fitting and reporting;
they are not a substitute for a delivered-carrier comparison with measurements.
