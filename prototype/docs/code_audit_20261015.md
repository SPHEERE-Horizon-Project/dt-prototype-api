# DT-Prototype code audit — 15 October 2026

Historical evidence for the source state on this date. Current instructions and
later corrections are in the [22 October review](reliability_review_20261022.md)
and [operational guide](running_forward_and_inverse.md).

## Scope and outcome

The audit reviewed shared configuration and preprocessing, the four thermal
solver families, the system/carrier engine and adapters, runner/report
orchestration, external Assessment integration, standalone LCC/LCA/Circularity,
and release/reproduction tools. Review concentrated on calculation boundaries,
units, missing values, duplicated assets, numeric validity and reproducibility.
It combines source inspection, regression tests and a complete regeneration of
the supplied five-building comparison.

Confirmed defects were corrected in Assessment, standalone modules and
verification tools. Thermal and carrier equations were not changed. All 318
generated CSV/CSV.GZ files reproduce accepted numeric results exactly after the
documented folder-name migration and identity-based portfolio row alignment.
The expanded root suite passes **322 tests and three unittest subtests**.

This establishes regression consistency for the tested cases, without claiming
measured-building accuracy, normative conformity or exhaustive coverage of every
possible future input.

## Findings and corrections

| Area | Confirmed problem | Correction |
|---|---|---|
| Assessment identities | Missing cells could become literal `nan`/`None` text; CSV inference lost leading zeros | Normalize true missing cells before text conversion, preserve textual IDs and reject null/blank identities |
| Assessment numeric domain | Optional fields accepted infinity, booleans could become numbers, and sizing overflow evaded tolerance checks | Validate every supplied numeric field, reject booleans and require a finite sizing product |
| Study and price bases | One assessment could mix study horizons, currencies or price years; LCC could omit its price year | Require consistent scenario bases, integer price year and total monetary units matching currency |
| MCI and status | An asset could have multiple MCI stages; all-not-applicable groups became missing | One current MCI per asset, positive finite MCI mass and preservation of not-applicable status |
| Operational join | Duplicate cases doubled rows, absent currency became a placeholder, and failed source runs were accepted | Reject duplicate/invalid annual identities, require resolved currency and check source manifest completion when supplied |
| Assessment provenance | Configuration/code hashes and failed-run diagnostics were missing | Record source/configuration/code hashes and failure messages |
| Standalone LCA | Zero-quantity assets with missing factors passed the coverage gate but crashed while summing `None` | Unknown factors stay unknown; absent assets contribute zero, while non-zero missing factors block totals |
| LCC/LCA CLI | Renovation-only cases with no technology rows crashed constructing CSV headers | Export header-only detail tables while preserving renovation calculations |
| LCC rates and sizing | -100% market inflation divided by zero before validation; sizing products could overflow | Check rate domains before discounting and finite derived sizes before assessment |
| LCA catalog/export | Optional catalog changes were not hashed; detail CSV omitted asset IDs and sizing | Hash the catalog/resolved inputs and retain asset/category/sizing fields in detail output |
| Standalone Circularity | Repeated components/materials double-counted mass; null IDs could become literal text | Reject duplicate building component IDs and component/material pairs, missing identities and inconsistent component names |
| DHW source units | A prior update inferred kW for the benchmark without source support | Restore original unit quantity and per-unit factors; make future capacity sizing explicit |
| Reproduction numeric checks | Finite/infinite mismatches could pass; missing text could match a literal missing-marker string | Compare signed infinity/missing masks explicitly and preserve textual IDs |
| Reproduction naming | Retained folders and row sort order predated component renaming | Map exact known hashed folder aliases, reject collisions and align model-labelled portfolio tables by identity |
| Test discovery | Root pytest omitted standalone suites | Include LCC, LCA and Circularity test folders in root discovery |

The external asset tool still owns factor-unit compatibility, physical inventory
completeness, device selection and the suitability of each sizing factor.

## Numerical and execution evidence

- The initial main suite passed its original 277 tests. The final suite passed
  322 tests, including standalone modules, plus three rate-domain subtests.
  Evidence: [JUnit report — full archive](validation_archive.md#reports-code-audit-20261015-test-results-xml).
  The JUnit file contains 325 test records because it includes the three
  unittest subtests. The [execution summary — full archive](validation_archive.md#reports-code-audit-20261015-execution-summary-json)
  also records energy-balance diagnostics and Assessment smoke-test counts.
- A fresh all-engine run generated 51 cases across all five buildings, including
  independent-zone sums and supported collapsed alternatives. All **318 result
  tables** match accepted values with maximum absolute difference **0.0**.
  Evidence: [full comparison — full archive](validation_archive.md#reports-code-audit-20261015-reproduction-comparison-json).
- Source differences against the frozen thermal run are the four added
  Assessment files, recorded explicitly. Old/current historical report hashes
  are also recorded; reconciled historical values and validation checks match.
- The standalone verifier passed 12 LCC and 14 LCA source-output checks and
  their 26 saved workbook checks. Maximum Python/source differences were about
  8.73e-10 EUR and 1.16e-10 in the LCA output units, within the agreed tolerance.
  Circularity worked examples remain 0.775 for the material and 0.49675 for the
  illustrative building.
  Evidence: [standalone verification — full archive](validation_archive.md#reports-code-audit-20261015-assessment-verification-json).
- Five DHW unit/note cells were corrected across LCC/LCA workbooks. A cell-by-cell
  check found **zero formula changes** and no other value changes. Artifact Tool
  formula-error scans returned zero matches; changed views were visually checked.
  Evidence: [workbook preservation — full archive](validation_archive.md#reports-code-audit-20261015-workbook-preservation-json).
- The updated Assessment CLI completed against the fresh energy results with
  the illustrative external CSV, producing 3 static aggregates and 132
  operational rows. This verifies the import/export workflow for that inventory;
  it is not an actual building LCA/LCC study.

Fresh runs remain under `outputs/code_audit_20261015_energy/` and
`outputs/code_audit_20261015_assessment/`. The accepted `reports/shared_energy/`
result remains the historical reference. Native Excel was not automated during
this audit. The earlier monthly energy workbook evidence is a separate record
checked by the release verifier.

## Repeating the checks

Use the project Python environment after installing the package and development
dependencies. From the prototype root:

```powershell
python -m pytest -q -p no:cacheprovider
python scripts/verify_assessments.py
python scripts/verify_release.py
python runners/run_energy_carriers.py --config configs/example.json --energy-config configs/energy_example.json --engine all --output outputs/my_audit_energy
python scripts/verify_reproduction.py --reference validation_archive/reports/shared_energy --candidate outputs/my_audit_energy --allow-code-changes
python runners/run_assessment.py --asset-results configs/asset_results_example.csv --energy-results outputs/my_audit_energy --output outputs/my_audit_assessment
```

Output directories must be new. `--allow-code-changes` discloses source
differences without relaxing result checks. The frozen reference predates
Assessment, so its addition must be acknowledged even when thermal/carrier
source matches the accepted run.

## Remaining limitations

[Remaining development gaps](code_findings.md) still apply: ground/solar/airflow
approximations, independent zones, monthly matching factors, initial conditions
and the sensible-only shared comparison boundary need further validation.

The source LCA formula at `ENERGY MODEL-DSS!T595` retains its documented text
literal defect. Python deliberately rejects that unsupported fuel-DHW branch;
this audit did not invent a replacement formula. LCC retains the documented
equal product-escalation/discount-base limitation of source row 533. Generalizing
either branch needs an explicit methodological decision.

Assessment completeness applies to declared rows. Omitted asset/indicator pairs
cannot be inferred. The source DHW quantity 26 remains an inherited benchmark,
not a verified device count or kW capacity for a new design. The operational
join does not imply whole-life discounting, grid-factor trajectories or automatic
physical-system sizing.
