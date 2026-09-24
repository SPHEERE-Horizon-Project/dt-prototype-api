# DT-Prototype decision log

## 2026-09-17: consolidation without changing scientific assumptions

1. One installed package and a single versioned input manifest serve three independent launchers. Separate physical solvers remain separate.
2. Case display names become Test building 1–5, in the requested order. IDs 1,18,19,20,21 are unchanged; they also influence deterministic stochastic-system inputs. Physical inputs and geometry remain unchanged.
3. The primary comparison remains useful sensible zone plus AHU demand, in positive kWh. Candidate-minus-reference differences use the reference denominator. Legacy Model 3 has a different AHU boundary and remains explicitly NOT_COMPARABLE for strict totals.
4. Independent lower/upper zones are retained, with no new inter-zone heat transfer. The collapsed alternative maps complete two-zone inputs into one equivalent case; it is not the removal of a zone. A native single-zone input needs no second-zone placeholders.
5. Retain the current 0.7-U ground treatment, solar transposition, gains, mass-class mapping, airflow averaging, seasons, initial state and emitter/system behaviour. No tuning or new scientific defaults were introduced to improve agreement.
6. Prepare simplified mapped inputs directly from common preprocessed inputs. Verify those intermediate values against the old monthly-output mapping; do not require a monthly heat-demand solve in simplified production runs.
7. Archive old completed runs and source copies. Reissue current reports with new labels. Do not rewrite golden Model 3 CSVs or historical manifests.
8. Remove obsolete project branding from active code, examples and user documentation. Preserve required copyright and licence attribution in the notices. Historical archive contents retain their original provenance.

## Retained scientific boundaries

The example uses the received Venice EPW, synthetic 2023 calendar and unchanged weather/solar conventions. Test building 5 has 36 m total height and 12 floors. Older results for a different geometry are not a benchmark for this case.

Exact standard edition/clause coverage, alternative ground methods, AHU availability semantics, production meter boundaries and carrier allocation, calibration/validation periods, environmental-factor geography/year, warm-up strategy and zone coupling remain open. The refactor does not select new values for them. No compliance, calibration or empirical-validation claim follows from preserved results.

The original integration decisions for 5P fitting, coefficient interpretation and mapping are retained in [integration decisions](integration_decisions.md), with current terminology.

## 2026-09-17: embed the complete Model 3 pipeline in integration

The separate active `third_party/model3_legacy` location was confusing because
Model 3 is required by simplified simulations. The complete pipeline now lives
in `src/dt_prototype/integration/model3/`, beside its adapter, mapping and
comparison workflow. `Model3Engine` imports that module directly.

The calculation source, example CSVs and golden reference CSVs were moved
without byte changes. Documentation and small command wrappers were adjusted
only so the pipeline runs as an installed subpackage. The former folder is
recoverably archived under `archive/previous_layout/third_party/`.

The source hash remains
`d0d4add1770f3e21cb9ae178f4ce8d206554a2ec9da1b63c8e50b55373e26f9c`.
Both simplified zone representations and all detailed five-building comparison
rows reproduce the previous numerical results exactly. Evidence is in
`outputs/20260917_model3_relocation_verification/verification.json`.

## 2026-09-17: unified launchers and tabular geometry

The three thin run scripts are grouped in `runners/` and have explicit engine
names. They remain independent selectors of the dynamic, monthly and Model 3
engines; grouping the wrappers does not merge their heat-balance equations.

The common geometry input now accepts either footprint-based GeoJSON or three
normalized CSV tables. The CSV contract records the simulation-ready building,
zone and surface values derived from GeoJSON. This avoids automatic polygon
extraction for direct tabular studies while retaining the GeoJSON route. Exact
geometry reconstruction and numerical output parity are protected by tests.
