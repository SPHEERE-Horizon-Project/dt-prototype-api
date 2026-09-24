# Retained methodology (DT-Prototype terminology)

Historical run paths below refer to archived evidence. Current commands are in the root README.

# Scientific and integration decision log

## 1. Status vocabulary

- `DECIDED`: active project rule, supported by the root instructions or this
  intake decision.
- `PROPOSED`: recommended direction that must be confirmed or tested before it
  changes scientific results.
- `OPEN`: missing evidence or user/scientific choice; do not rely on it.
- `BLOCKING`: integration work that depends on the decision must not proceed.

This log records decisions before they are relied upon. It does not modify
either physics engine.

## 2. Decisions established during intake

### D-001 — Protect the received baselines

- **Status:** `DECIDED`
- **Decision:** Use root commit
  `5ad8c055373cec92b4d52625b12b223f21ef6a05` as the imported baseline.
  Preserve Model 3 `reference_outputs/` and the semi-stationary tests/output
  fixtures unchanged.
- **Evidence:** Both original suites pass; every imported CSV fixture
  regenerates byte-for-byte. Hashes are recorded in `source_inventory.md`.
- **Consequence:** Future equation or adapter changes require new regression
  tests and must not rewrite these fixtures.

### D-002 — Keep the physics implementations independent

- **Status:** `DECIDED`
- **Decision:** Adapters may share canonical schemas, unit conversions, and
  orchestration, but Model 3 and semi-stationary heat balances will not call a
  shared implementation merely to improve agreement.
- **Consequence:** Differences are diagnosed and classified, not tuned away.

### D-003 — Use verification terminology precisely

- **Status:** `DECIDED`
- **Decision:** Reproduction of fixtures is verification. Agreement between
  independent engines under matched assumptions is cross-model verification.
  Parameter estimation uses a declared calibration subset. Validation uses
  untouched observations or an independent reference. Other juxtaposition is
  comparison.
- **Consequence:** The supplied semi-stationary implementation is accepted as
  previously validated against benchmark studies. Its local five-case test is
  regression verification that protects that reference; comparison of Model 3
  against it is cross-model verification, not a substitute for Model 3
  empirical validation.

### D-004 — Validated reference, primary, and comparison engines

- **Status:** `DECIDED`
- **Decision:** The supplied ISO 13790 semi-stationary implementation is the
  validated scientific reference and the future production full-model engine.
  Model 3 remains an independent comparison and compatibility engine. Model 3
  system/carrier concepts may be applied downstream of either useful-load
  result through explicit adapters.
- **Reference-precedence rule:** When a physics choice is unresolved in project
  documentation but is embodied by the reference implementation, preserve that
  implementation's choice, record the exact behaviour and boundary, and explain
  the cases in which it is appropriate. Do not silently alter the reference to
  make Model 3 agree.
- **Consequence:** Model 3 is not deleted or silently converted into the new
  heat-balance implementation. A different convention requires an explicit
  scenario/method identifier and comparative evidence.

### D-005 — EPW preprocessing boundary

- **Status:** `DECIDED`; additional independent verification remains planned
- **Decision:** Reuse the received semi-stationary EPW preprocessing path as the
  single operational preprocessing source. Persist raw hash, metadata, hourly
  processed weather, and canonical monthly aggregates once per weather/site.
- **Evidence:** Raw field positions and all monthly dry-bulb/GHI aggregates
  passed independent intake checks. The reference implementation's solar and
  transposition conventions govern the first release; targeted independent
  checks will document their behaviour and guard against software errors.
- **Consequence:** Both engine adapters consume canonical weather derived from
  this one traceable artefact. Common consumption does not validate the
  preprocessor.

### D-006 — Two-zone independent simulation

- **Status:** `DECIDED`
- **Decision:** Preserve the semi-stationary independent upper/lower-zone mode
  and include both single-zone and two-zone cases in the comparison programme.
  Use the split when end uses or schedules genuinely differ and explicitly
  accept an adiabatic, uncoupled interface.
- **Rationale:** Four supplied five-case fixtures use the split. Removing it
  would destroy received behaviour. However, roof/ground allocation and
  nonlinear utilisation factors make its aggregate generally non-equivalent
  to a single-zone calculation.
- **Consequence:** Canonical schemas include `zone_id`. Compare upper and lower
  zones individually, verify reference aggregation, and compare the aggregate
  with an explicitly collapsed Model 3 case. The latter remains `APPROXIMATE`
  unless a documented transformation establishes equivalence.

### D-007 — Residual sign convention

- **Status:** `DECIDED`
- **Decision:** Use `residual_kWh = measured_kWh - predicted_kWh` everywhere.
- **Rationale:** This preserves Model 3's existing convention and makes positive
  residuals mean underprediction.

### D-008 — Calibration/validation separation

- **Status:** `DECIDED`
- **Decision:** Fit only rows explicitly labelled `calibration`; rows labelled
  `validation` remain untouched until out-of-sample evaluation. Quality flags
  and missing data are honoured. Baseline inputs are never overwritten;
  calibrated parameters are a separate overlay.
- **Evidence:** The received `Model 3.calibrate()` currently fits all rows,
  including validation rows. Preserve that behaviour only inside the legacy
  baseline; do not carry it into the integration regression module.

### D-009 — Regression-informed physical calibration

- **Status:** `DECIDED` at conceptual level; numerical formulation is open
- **Decision:** Fit identical 5P equations to measured delivered energy and to
  full-forward delivered energy at the same carrier/meter boundary. Use the
  difference in those statistical features as diagnostic information and, if
  selected, as a secondary calibration penalty. Do not substitute 5P
  coefficients directly for physical parameters.
- **Interpretation rules:**
  - slope informs the combination of effective heat transfer and delivery
    efficiency/COP only for a carrier serving that end use;
  - a change point is an emergent balance temperature, not a setpoint;
  - the base term is a mixture of non-weather-sensitive loads;
  - mixed carriers, variable efficiencies, schedules, gains, and PV/net-meter
    boundaries can invalidate simple physical mapping.
- **Consequence:** Monthly carrier residuals remain the primary objective;
  coefficient penalties and prior regularisation improve interpretability and
  identifiability without replacing the full time-series fit.

### D-010 — Visualization hierarchy

- **Status:** `DECIDED` at design level
- **Decision:** Use a long-form comparison dataset and a progressive visual
  hierarchy: portfolio construction × climate/condition matrix, coefficient
  dot/interval plots, slope scatter, change-point dumbbells, selected monthly
  small multiples, residual heatmaps, and a portfolio status panel.
- **Consequence:** Invalid boundaries and insufficient regimes remain visible.
  Regression confidence intervals are not drawn around deterministic forward
  points; input sensitivity is labelled separately from statistical
  uncertainty.

## 3. Reference choices and remaining open decisions

### D-011 — Exact the retained reference provenance and licence chain

- **Status:** `OPEN`; not blocking scientific integration, but `BLOCKING` for
  external redistribution or a traceable the retained reference-lineage claim
- **Observed:** Local modules name the retained reference components, and data comments describe
  a 1:1 database port. No upstream repository URL, commit/tag, package version,
  source snapshot, migration script, or upstream licence is present. The local
  package declares MIT but has no licence text file.
- **Required evidence:** Identify the exact the retained reference repository/package, commit or
  release, licence, database version, and porting script when available.
- **Proposed next action:** Recover these artefacts from the source of the
  imported folder and add immutable provenance records. A new the retained reference dynamic
  simulation comparison is not required; the semi-stationary implementation's
  prior benchmark validation is the relevant scientific evidence.

### D-012 — ISO 13790 edition and method variant

- **Status:** `OPEN`; not blocking adapters, but `BLOCKING` for compliance
  language and normative tolerances
- **Observed:** Source comments claim an ISO 13790 monthly QSS/5R1C method and
  ISO 13786/13370-related elements, but no edition, clause mapping, national
  annex, or deviations register is supplied.
- **Decision for integration:** The supplied validated implementation governs
  equation choices. Recover the exact ISO edition and monthly variant, then map
  equations, constants, season rules, and deviations for audit. Until then,
  describe the method as the supplied validated ISO 13790 semi-stationary
  implementation and make no formal compliance claim.

### D-013 — Ground heat-transfer treatment

- **Status:** `DECIDED` for the first integrated release
- **Observed:** Model 3 accepts a direct steady `H_ground_W_K`; the
  semi-stationary package multiplies ground-floor U by 0.7 and includes it in
  `UA_tot` against outdoor monthly temperature.
- **Decision:** Follow the reference implementation's ground-floor convention:
  a 0.7 multiplier on ground-floor U included in `UA_tot`. Expose its component
  as `H_ground_W_K`, record `ground_method_id`, and map Model 3's direct steady
  input to the same boundary for matched cases. Do not claim ISO 13370
  equivalence. Any alternative ground model is a separately identified future
  method/scenario, not a silent replacement.

### D-014 — Solar position, transposition, and shading convention

- **Status:** `DECIDED` for the first integrated release
- **Observed:** The received path replaces `pvlib` with internal solar geometry
  and isotropic-sky transposition, bins azimuths, uses constant window SHGC,
  includes opaque solar/long-wave terms, and omits urban mutual shading.
- **Decision:** Preserve and use this reference path: internal solar geometry,
  isotropic-sky transposition, eight vertical azimuth bins plus horizontal,
  current window/opaque/long-wave treatment, and no urban mutual shading.
  Record bin, albedo, tilt, azimuth, shading, and long-wave conventions in each
  weather manifest. Independently test timestamps, solar position,
  cardinal/horizontal POA, energy conservation, and selected reference cases as
  software verification; alternatives require a named method/scenario.

### D-015 — Effective heat-transfer boundary for coefficient comparison

- **Status:** `DECIDED` for boundary; numerical reduction must be documented
- **Decision:** Define the useful-load analytical bridge with
  `H_effective = H_transmission + H_ground + H_infiltration + H_ventilation_external`
  and store inclusion flags plus `heat_transfer_boundary_id`. Keep AHU coil
  load separate. Translate to delivered energy only with the declared
  efficiency/COP and carrier allocation.
- **Reason:** This is closest to the weather-dependent envelope/air-exchange
  response, but the semi-stationary AHU supply convention makes ventilation
  boundary selection nontrivial.
- **Application rule:** When the selected carrier meter includes AHU coil
  energy, add that separately in delivered-energy conversion and disclose it;
  do not fold it silently into envelope `H_effective`.

### D-016 — Useful versus delivered response and meter boundaries

- **Status:** `DECIDED` for model boundary; meter definitions remain `OPEN` and
  `BLOCKING` for real-data comparisons
- **Decision:** Keep full physics results on the reference implementation's
  useful sensible basis. Include separate AHU sensible output where present.
  Perform measured and forward-implied 5P fits on delivered carrier energy at
  a declared `meter_boundary_id`. Report the analytical physical slope on both
  useful and, where defensible, transformed delivered bases.
- **Required evidence:** For every real meter, document included end uses,
  import/export convention, shared systems, submeters, and carrier allocation.
  Missing or mismatched boundaries are `INVALID_CARRIER_BOUNDARY`, not omitted.

### D-017 — Actual calibration and validation periods

- **Status:** `OPEN`, `BLOCKING` for calibration runs
- **Decided rule:** Flags drive the split; validation never enters fitting.
- **Required decision:** Declare the real date periods, any rolling/fixed split,
  minimum regime coverage, treatment of commissioning/closure periods, and
  quality exclusions. Hash the selected rows in the run manifest.

### D-018 — 5P bounds, constraints, objective, and uncertainty

- **Status:** `DECIDED` for the lean post-processing verification module;
  project-specific production calibration bounds remain `OPEN`
- **Legacy evidence:** Heating CP 8–20 °C, cooling CP 14–26 °C, 0.5 K grid,
  `cooling_cp >= heating_cp`, unconstrained OLS coefficients, daily-energy SSE,
  no uncertainty.
- **Implemented verification decision:** Use one independent implementation for
  measured and forward-implied series. Fit monthly average daily energy with
  equal monthly weight, nonnegative base/heating/cooling coefficients, heating
  CP 8–20 °C, cooling CP 14–26 °C, a 0.5 K grid, and cooling CP not below
  heating CP. Require six calibration observations, two observations in each
  active regime, and a 5 K temperature span. Store formal/effective parameter
  counts, degrees of freedom, bound/regime warnings, and separate calibration
  and validation metrics. No coefficient uncertainty is claimed.
- **Configurability:** All numerical verification settings are explicit CLI/API
  configuration. Real-meter runs must declare their values and split before
  being used for physical calibration; robust loss and uncertainty remain open.

### D-019 — Negative and boundary regression coefficients

- **Status:** `DECIDED` for the current post-processor
- **Decision:** Do not silently clip an unconstrained result. Apply declared
  nonnegative bounds during fitting; report a bound hit. If a net-meter or PV
  boundary can legitimately produce a negative apparent base/slope, classify
  that boundary as unsupported by this physical-boundary fitter rather than
  interpreting the coefficient as a physical heat-transfer response. A future
  prediction-only relaxed-bound fitter would be a separate declared method.

### D-020 — Parameter identifiability rules

- **Status:** `DECIDED` for warnings in post-processing; still `BLOCKING` for
  automated physical calibration
- **Implemented rules:** Require observations on both sides of an estimated change
  point; require sufficient temperature span and positive degree of freedom;
  flag coefficient/change-point bound hits; do not calibrate multiple confounded
  physical parameters from one coefficient; treat mixed end-use carriers as
  heuristic unless submeter allocation is available. The verification warning
  thresholds are two observations per active regime and 5 K temperature span.
  High-correlation and uncertainty thresholds remain open before automated
  physical calibration.

### D-021 — Environmental factors

- **Status:** `OPEN`, `BLOCKING` for primary-energy and carbon comparisons
- **Observed:** Model 3 contains example factors with free-text sources; their
  values are not adequate as a project-wide versioned reference.
- **Required decision:** Geography, reporting year, average/marginal or other
  convention, import/export treatment, and authoritative versioned source for
  each carrier.

### D-022 — Physical calibration objective and parameter set

- **Status:** `PROPOSED`, `BLOCKING` for calibration implementation
- **Proposed objective:** On calibration rows only, minimise a documented sum of
  scaled monthly carrier residuals, optional measured-versus-forward-implied
  5P feature penalties, and prior-distance regularisation. Use a staged,
  identifiable parameter set: heat transfer/air exchange; gains/schedules;
  system efficiency; base end uses. Store all weights, priors, bounds, and
  random seeds.
- **Required choice:** Which physical parameters may vary by building, which
  are fixed/shared across a portfolio, objective weights, and optimiser.
- **Validation rule:** Select no weights or parameters using the untouched
  validation set; evaluate it only after calibration is frozen.

### D-023 — Reference-to-Model-3 comparison transformation

- **Status:** `DECIDED` for Stage 4 cross-model verification
- **Decision:** Generate Model 3 comparison inputs from the validated reference
  results through an explicit, per-case mapping manifest. Preserve period,
  outdoor temperature, non-ground transmission UA, the reference 0.7-U ground
  component, and monthly total gains directly or after a declared unit/channel
  conversion.
- **Declared approximations:**
  - map monthly reference infiltration plus external ventilation to one
    hours-weighted annual-mean Model 3 infiltration flow;
  - map reference surface-layer capacity to the nearest Model 3 mass class;
  - map active schedule setpoints to area-weighted constants;
  - prescribe reference total gains through Model 3's internal-gain channel,
    so solar/internal subcomponents are not equivalent;
  - map non-ground transmission as Model 3 opaque UA without preserving the
    opaque/window subdivision;
  - collapse independent zones only for the separate building-level Model 3
    comparison while retaining upper/lower cases individually.
- **Consequence:** Direct mappings receive `EQUIVALENT_AFTER_CONVERSION`
  tolerances. Schedule, air-exchange, mass, demand, and collapsed-zone results
  are `APPROXIMATE` and stay `REVIEW`; tolerances are not adjusted to hide
  differences. This transformation is for verification/comparison and does not
  replace production inputs.

### D-024 — Stage 2/4 verification artifact format

- **Status:** `DECIDED` as a reversible implementation detail
- **Decision:** Write current verification tables as numeric CSV plus JSON
  manifests because the imported environment has no locked Parquet engine.
- **Consequence:** The first release will add Parquet in the locked artifact
  environment without changing scientific columns or boundaries. Immutable
  run directories are already enforced and never overwritten.

### D-025 — Opt-in seasonal availability and separate AHU comparison

- **Status:** `DECIDED` by user direction on 2026-08-10
- **Decision:** Preserve the Model 3 legacy path and golden outputs unchanged,
  while adding an opt-in `seasonal_ahu` comparison mode. Map hourly heating
  and cooling availability to explicit monthly fractions. Resolve mechanical
  ventilation and infiltration separately, calculate the zone-side
  ventilation term against AHU supply temperature, and report an independently
  calculated monthly sensible AHU coil component.
- **Boundary rule:** `useful_heating_kWh` and `useful_cooling_kWh` in this mode
  equal zone sensible demand plus separately reported AHU sensible demand.
  `H_total_W_K` retains the external-air boundary; the AHU coil is not added to
  a zone balance that already contains the same external-air load.
- **Reference choice:** The enhanced cooling gain/loss ratio follows the
  validated semi-stationary definition (gains divided by cooling heat
  transfer). The reciprocal legacy definition remains untouched in legacy
  mode solely to preserve its recorded baseline.
- **Remaining approximations:** Monthly-mean rather than hourly AHU weather,
  annual-mean airflow, constant active setpoints, nearest Model 3 mass class,
  prescribed total gains, and collapsed aggregate two-zone cases. Individual
  upper/lower zone results remain the preferred scientific comparison.
- **Evidence:** Immutable run `20260810_stage4_seasonal_ahu_comparison_002`
  reduces the three food lower-zone heating differences to -2.3%, -0.6%, and
  -1.4%, and cooling differences to -3.8%, -1.9%, and -3.0%.

## 4. Gate before engine modification

Canonical schemas and adapters may now proceed using the validated
semi-stationary implementation as the scientific reference. Its equations
remain unchanged. Model 3's legacy equation path and golden fixtures remain
unchanged; D-025 documents the isolated opt-in comparison path.

The comparison suite must contain both:

1. single-zone, matched-weather and matched-boundary limiting cases with
   transparent intermediate quantities;
2. two-zone cases reporting each zone, the reference aggregate, and the
   explicitly collapsed Model 3 comparison.

No the retained reference dynamic rerun is required. D-011 and D-012 remain provenance and
compliance tasks, not adapter blockers. D-017 through D-022 must be resolved at
the stages where real-data calibration, regression interpretation,
environmental impacts, or automated physical calibration are introduced.
