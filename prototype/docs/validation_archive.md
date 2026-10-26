# Optional full validation archive

The lean source distribution includes all calculation code, tests, example
inputs, monthly reference fixtures, workbooks and selected validation summaries.
The original full evidence remains unchanged in the development project.

`DT_Prototype_validation_archive.zip` is supplied separately beside this upload
folder. It contains the complete original tracked `reports/` tree and a byte-hash
manifest. It is optional for normal simulations, inverse examples and the full
automated test suite. To distribute it publicly, attach it separately to a GitHub
Release; keep it outside the repository's tracked working files.

After obtaining it, extract the archive to a local `validation_archive/` folder
under the project root. That folder is ignored by Git. The full baseline is then
`validation_archive/reports/shared_energy/`. Example complete reproduction:

```powershell
python runners/run_energy_carriers.py --config configs/example.json --energy-config configs/energy_example.json --engine all --output outputs/reproduction
python scripts/verify_reproduction.py --reference validation_archive/reports/shared_energy --candidate outputs/reproduction --allow-code-changes --output outputs/reproduction_check.json
```

Workbook summaries and cached checks remain in the lean repository. The detailed
`native_excel_comparison.csv` and original run figures are in this separate
archive. A successful source test run does not claim a new native Excel run or
measured-building validation.

Historical report links below identify the files moved out of the upload folder.
Paths are relative to the development project and to the extracted archive.

## Archived file inventory

<a id="reports-adiabatic-boundaries-20261015-assessment-verification-json"></a>
- `reports/adiabatic_boundaries_20261015/assessment_verification.json` (3,263 bytes)

<a id="reports-adiabatic-boundaries-20261015-before-hashes-json"></a>
- `reports/adiabatic_boundaries_20261015/before_hashes.json` (24,694 bytes)

<a id="reports-adiabatic-boundaries-20261015-code-snapshot-json"></a>
- `reports/adiabatic_boundaries_20261015/code_snapshot.json` (20,780 bytes)

<a id="reports-adiabatic-boundaries-20261015-preservation-json"></a>
- `reports/adiabatic_boundaries_20261015/preservation.json` (3,280 bytes)

<a id="reports-adiabatic-boundaries-20261015-release-verification-json"></a>
- `reports/adiabatic_boundaries_20261015/release_verification.json` (11,924 bytes)

<a id="reports-adiabatic-boundaries-20261015-reproduction-comparison-json"></a>
- `reports/adiabatic_boundaries_20261015/reproduction_comparison.json` (99,984 bytes)

<a id="reports-adiabatic-boundaries-20261015-test-results-xml"></a>
- `reports/adiabatic_boundaries_20261015/test_results.xml` (45,456 bytes)

<a id="reports-adiabatic-boundaries-20261015-verify-preservation-py"></a>
- `reports/adiabatic_boundaries_20261015/verify_preservation.py` (2,609 bytes)

<a id="reports-asset-quantities-20261021-assessment-verification-json"></a>
- `reports/asset_quantities_20261021/assessment_verification.json` (3,755 bytes)

<a id="reports-asset-quantities-20261021-authoring-assumptions-png"></a>
- `reports/asset_quantities_20261021/authoring/assumptions.png` (110,556 bytes)

<a id="reports-asset-quantities-20261021-authoring-build-workbook-mjs"></a>
- `reports/asset_quantities_20261021/authoring/build_workbook.mjs` (11,807 bytes)

<a id="reports-asset-quantities-20261021-authoring-catalogue-png"></a>
- `reports/asset_quantities_20261021/authoring/catalogue.png` (199,809 bytes)

<a id="reports-asset-quantities-20261021-authoring-inputs-png"></a>
- `reports/asset_quantities_20261021/authoring/inputs.png` (80,328 bytes)

<a id="reports-asset-quantities-20261021-authoring-prepare-workbook-py"></a>
- `reports/asset_quantities_20261021/authoring/prepare_workbook.py` (805 bytes)

<a id="reports-asset-quantities-20261021-authoring-results-png"></a>
- `reports/asset_quantities_20261021/authoring/results.png` (69,890 bytes)

<a id="reports-asset-quantities-20261021-authoring-sources-png"></a>
- `reports/asset_quantities_20261021/authoring/sources.png` (188,289 bytes)

<a id="reports-asset-quantities-20261021-authoring-workbook-source-json"></a>
- `reports/asset_quantities_20261021/authoring/workbook_source.json` (24,959 bytes)

<a id="reports-asset-quantities-20261021-authoring-workbook-verification-json"></a>
- `reports/asset_quantities_20261021/authoring/workbook_verification.json` (467 bytes)

<a id="reports-asset-quantities-20261021-before-hashes-json"></a>
- `reports/asset_quantities_20261021/before_hashes.json` (25,443 bytes)

<a id="reports-asset-quantities-20261021-building-quantity-summary-csv"></a>
- `reports/asset_quantities_20261021/building_quantity_summary.csv` (1,294 bytes)

<a id="reports-asset-quantities-20261021-code-snapshot-json"></a>
- `reports/asset_quantities_20261021/code_snapshot.json` (21,495 bytes)

<a id="reports-asset-quantities-20261021-direct-example-csv"></a>
- `reports/asset_quantities_20261021/direct_example.csv` (1,947 bytes)

<a id="reports-asset-quantities-20261021-quantity-comparison-csv"></a>
- `reports/asset_quantities_20261021/quantity_comparison.csv` (6,378 bytes)

<a id="reports-asset-quantities-20261021-quantity-verification-json"></a>
- `reports/asset_quantities_20261021/quantity_verification.json` (1,120 bytes)

<a id="reports-asset-quantities-20261021-release-verification-json"></a>
- `reports/asset_quantities_20261021/release_verification.json` (12,333 bytes)

<a id="reports-asset-quantities-20261021-reproduction-comparison-json"></a>
- `reports/asset_quantities_20261021/reproduction_comparison.json` (100,613 bytes)

<a id="reports-asset-quantities-20261021-test-results-xml"></a>
- `reports/asset_quantities_20261021/test_results.xml` (51,494 bytes)

<a id="reports-asset-quantities-20261021-verify-quantities-py"></a>
- `reports/asset_quantities_20261021/verify_quantities.py` (6,282 bytes)

<a id="reports-code-audit-20261015-assessment-verification-json"></a>
- `reports/code_audit_20261015/assessment_verification.json` (3,263 bytes)

<a id="reports-code-audit-20261015-code-snapshot-json"></a>
- `reports/code_audit_20261015/code_snapshot.json` (20,058 bytes)

<a id="reports-code-audit-20261015-execution-summary-json"></a>
- `reports/code_audit_20261015/execution_summary.json` (1,095 bytes)

<a id="reports-code-audit-20261015-reproduction-comparison-json"></a>
- `reports/code_audit_20261015/reproduction_comparison.json` (97,705 bytes)

<a id="reports-code-audit-20261015-test-results-xml"></a>
- `reports/code_audit_20261015/test_results.xml` (42,084 bytes)

<a id="reports-code-audit-20261015-workbook-preservation-json"></a>
- `reports/code_audit_20261015/workbook_preservation.json` (900 bytes)

<a id="reports-inverse-models-20261021-assessment-verification-json"></a>
- `reports/inverse_models_20261021/assessment_verification.json` (5,128 bytes)

<a id="reports-inverse-models-20261021-before-hashes-json"></a>
- `reports/inverse_models_20261021/before_hashes.json` (32,258 bytes)

<a id="reports-inverse-models-20261021-case-study-metrics-csv"></a>
- `reports/inverse_models_20261021/case_study_metrics.csv` (56,934 bytes)

<a id="reports-inverse-models-20261021-code-snapshot-json"></a>
- `reports/inverse_models_20261021/code_snapshot.json` (16,558 bytes)

<a id="reports-inverse-models-20261021-inverse-tests-xml"></a>
- `reports/inverse_models_20261021/inverse_tests.xml` (3,804 bytes)

<a id="reports-inverse-models-20261021-model-statuses-csv"></a>
- `reports/inverse_models_20261021/model_statuses.csv` (40,581 bytes)

<a id="reports-inverse-models-20261021-monthly-hourly-adapter-comparison-csv"></a>
- `reports/inverse_models_20261021/monthly_hourly_adapter_comparison.csv` (86,489 bytes)

<a id="reports-inverse-models-20261021-prepare-examples-py"></a>
- `reports/inverse_models_20261021/prepare_examples.py` (3,741 bytes)

<a id="reports-inverse-models-20261021-probe-billing-py"></a>
- `reports/inverse_models_20261021/probe_billing.py` (889 bytes)

<a id="reports-inverse-models-20261021-release-verification-json"></a>
- `reports/inverse_models_20261021/release_verification.json` (13,247 bytes)

<a id="reports-inverse-models-20261021-reproduction-comparison-json"></a>
- `reports/inverse_models_20261021/reproduction_comparison.json` (102,022 bytes)

<a id="reports-inverse-models-20261021-synthetic-holdout-metrics-csv"></a>
- `reports/inverse_models_20261021/synthetic_holdout_metrics.csv` (1,404 bytes)

<a id="reports-inverse-models-20261021-synthetic-holdout-native-metrics-csv"></a>
- `reports/inverse_models_20261021/synthetic_holdout_native_metrics.csv` (2,416 bytes)

<a id="reports-inverse-models-20261021-test-results-xml"></a>
- `reports/inverse_models_20261021/test_results.xml` (59,750 bytes)

<a id="reports-inverse-models-20261021-validation-json"></a>
- `reports/inverse_models_20261021/validation.json` (109,495 bytes)

<a id="reports-inverse-models-20261021-verify-inverse-py"></a>
- `reports/inverse_models_20261021/verify_inverse.py` (8,687 bytes)

<a id="reports-pipeline-20261021-assessment-by-building-csv"></a>
- `reports/pipeline_20261021/assessment_by_building.csv` (353 bytes)

<a id="reports-pipeline-20261021-assessment-verification-json"></a>
- `reports/pipeline_20261021/assessment_verification.json` (3,755 bytes)

<a id="reports-pipeline-20261021-code-snapshot-json"></a>
- `reports/pipeline_20261021/code_snapshot.json` (11,243 bytes)

<a id="reports-pipeline-20261021-operational-comparison-csv"></a>
- `reports/pipeline_20261021/operational_comparison.csv` (110,618 bytes)

<a id="reports-pipeline-20261021-pipeline-tests-xml"></a>
- `reports/pipeline_20261021/pipeline_tests.xml` (4,776 bytes)

<a id="reports-pipeline-20261021-prepare-examples-py"></a>
- `reports/pipeline_20261021/prepare_examples.py` (1,957 bytes)

<a id="reports-pipeline-20261021-release-verification-json"></a>
- `reports/pipeline_20261021/release_verification.json` (12,417 bytes)

<a id="reports-pipeline-20261021-reproduction-comparison-json"></a>
- `reports/pipeline_20261021/reproduction_comparison.json` (100,752 bytes)

<a id="reports-pipeline-20261021-test-results-xml"></a>
- `reports/pipeline_20261021/test_results.xml` (56,020 bytes)

<a id="reports-pipeline-20261021-validation-json"></a>
- `reports/pipeline_20261021/validation.json` (1,246 bytes)

<a id="reports-pipeline-20261021-verify-pipeline-py"></a>
- `reports/pipeline_20261021/verify_pipeline.py` (6,048 bytes)

<a id="reports-release-verification-json"></a>
- `reports/release_verification.json` (11,267 bytes)

<a id="reports-reliability-improvements-20261023-configs-dynamic-json"></a>
- `reports/reliability_improvements_20261023/configs/dynamic.json` (1,232 bytes)

<a id="reports-reliability-improvements-20261023-verify-improvements-py"></a>
- `reports/reliability_improvements_20261023/verify_improvements.py` (6,270 bytes)

<a id="reports-reliability-review-20261022-assessment-verification-json"></a>
- `reports/reliability_review_20261022/assessment_verification.json` (5,128 bytes)

<a id="reports-reliability-review-20261022-baseline-tests-xml"></a>
- `reports/reliability_review_20261022/baseline_tests.xml` (59,750 bytes)

<a id="reports-reliability-review-20261022-before-hashes-json"></a>
- `reports/reliability_review_20261022/before_hashes.json` (38,053 bytes)

<a id="reports-reliability-review-20261022-configs-combined-pipeline-json"></a>
- `reports/reliability_review_20261022/configs/combined_pipeline.json` (1,406 bytes)

<a id="reports-reliability-review-20261022-configs-dynamic-json"></a>
- `reports/reliability_review_20261022/configs/dynamic.json` (1,230 bytes)

<a id="reports-reliability-review-20261022-configs-evaluate-json"></a>
- `reports/reliability_review_20261022/configs/evaluate.json` (1,237 bytes)

<a id="reports-reliability-review-20261022-configs-inverse-pipeline-json"></a>
- `reports/reliability_review_20261022/configs/inverse_pipeline.json` (198 bytes)

<a id="reports-reliability-review-20261022-configs-monthly-json"></a>
- `reports/reliability_review_20261022/configs/monthly.json` (864 bytes)

<a id="reports-reliability-review-20261022-configs-predict-json"></a>
- `reports/reliability_review_20261022/configs/predict.json` (1,236 bytes)

<a id="reports-reliability-review-20261022-configs-reuse-pipeline-json"></a>
- `reports/reliability_review_20261022/configs/reuse_pipeline.json` (1,298 bytes)

<a id="reports-reliability-review-20261022-configs-synthetic-json"></a>
- `reports/reliability_review_20261022/configs/synthetic.json` (1,560 bytes)

<a id="reports-reliability-review-20261022-configs-vbdd-inverse-json"></a>
- `reports/reliability_review_20261022/configs/vbdd_inverse.json` (432 bytes)

<a id="reports-reliability-review-20261022-defect-reproduction-xml"></a>
- `reports/reliability_review_20261022/defect_reproduction.xml` (40,168 bytes)

<a id="reports-reliability-review-20261022-documentation-inventory-json"></a>
- `reports/reliability_review_20261022/documentation_inventory.json` (8,001 bytes)

<a id="reports-reliability-review-20261022-focused-tests-xml"></a>
- `reports/reliability_review_20261022/focused_tests.xml` (6,678 bytes)

<a id="reports-reliability-review-20261022-portable-fixture-tests-xml"></a>
- `reports/reliability_review_20261022/portable_fixture_tests.xml` (3,937 bytes)

<a id="reports-reliability-review-20261022-prepare-runs-py"></a>
- `reports/reliability_review_20261022/prepare_runs.py` (2,429 bytes)

<a id="reports-reliability-review-20261022-release-verification-json"></a>
- `reports/reliability_review_20261022/release_verification.json` (13,340 bytes)

<a id="reports-reliability-review-20261022-reproduction-json"></a>
- `reports/reliability_review_20261022/reproduction.json` (103,748 bytes)

<a id="reports-reliability-review-20261022-test-results-xml"></a>
- `reports/reliability_review_20261022/test_results.xml` (63,138 bytes)

<a id="reports-reliability-review-20261022-validation-json"></a>
- `reports/reliability_review_20261022/validation.json` (29,601 bytes)

<a id="reports-reliability-review-20261022-verify-review-py"></a>
- `reports/reliability_review_20261022/verify_review.py` (9,369 bytes)

<a id="reports-reproduction-verification-json"></a>
- `reports/reproduction_verification.json` (33,332 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-dynamic-5r1c-64f7f6b31419d901-energy-inputs-csv-gz"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Dynamic-5R1C-64f7f6b31419d901/energy_inputs.csv.gz` (226,026 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-dynamic-5r1c-64f7f6b31419d901-energy-intervals-csv-gz"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Dynamic-5R1C-64f7f6b31419d901/energy_intervals.csv.gz` (1,511,688 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-dynamic-5r1c-64f7f6b31419d901-energy-monthly-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Dynamic-5R1C-64f7f6b31419d901/energy_monthly.csv` (12,392 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-dynamic-5r1c-64f7f6b31419d901-metadata-json"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Dynamic-5R1C-64f7f6b31419d901/metadata.json` (834 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-dynamic-5r1c-64f7f6b31419d901-service-intervals-csv-gz"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Dynamic-5R1C-64f7f6b31419d901/service_intervals.csv.gz` (878,443 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-dynamic-7r2c-d4be1cdecd94554f-energy-inputs-csv-gz"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Dynamic-7R2C-d4be1cdecd94554f/energy_inputs.csv.gz` (226,405 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-dynamic-7r2c-d4be1cdecd94554f-energy-intervals-csv-gz"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Dynamic-7R2C-d4be1cdecd94554f/energy_intervals.csv.gz` (1,513,725 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-dynamic-7r2c-d4be1cdecd94554f-energy-monthly-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Dynamic-7R2C-d4be1cdecd94554f/energy_monthly.csv` (12,370 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-dynamic-7r2c-d4be1cdecd94554f-metadata-json"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Dynamic-7R2C-d4be1cdecd94554f/metadata.json` (834 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-dynamic-7r2c-d4be1cdecd94554f-service-intervals-csv-gz"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Dynamic-7R2C-d4be1cdecd94554f/service_intervals.csv.gz` (880,924 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-monthly-qss-43d11002a2ebfffa-energy-inputs-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Monthly-QSS-43d11002a2ebfffa/energy_inputs.csv` (2,437 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-monthly-qss-43d11002a2ebfffa-energy-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Monthly-QSS-43d11002a2ebfffa/energy_intervals.csv` (13,004 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-monthly-qss-43d11002a2ebfffa-energy-monthly-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Monthly-QSS-43d11002a2ebfffa/energy_monthly.csv` (12,275 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-monthly-qss-43d11002a2ebfffa-metadata-json"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Monthly-QSS-43d11002a2ebfffa/metadata.json` (825 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-monthly-qss-43d11002a2ebfffa-service-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Monthly-QSS-43d11002a2ebfffa/service_intervals.csv` (11,990 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-collapsed-2b3b8beedce40b8a-energy-inputs-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Simplified-collapsed-2b3b8beedce40b8a/energy_inputs.csv` (2,335 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-collapsed-2b3b8beedce40b8a-energy-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Simplified-collapsed-2b3b8beedce40b8a/energy_intervals.csv` (12,785 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-collapsed-2b3b8beedce40b8a-energy-monthly-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Simplified-collapsed-2b3b8beedce40b8a/energy_monthly.csv` (12,056 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-collapsed-2b3b8beedce40b8a-metadata-json"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Simplified-collapsed-2b3b8beedce40b8a/metadata.json` (843 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-collapsed-2b3b8beedce40b8a-service-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Simplified-collapsed-2b3b8beedce40b8a/service_intervals.csv` (11,551 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-zone-sum-d8320f8fc43d0d21-energy-inputs-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Simplified-zone-sum-d8320f8fc43d0d21/energy_inputs.csv` (2,332 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-zone-sum-d8320f8fc43d0d21-energy-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Simplified-zone-sum-d8320f8fc43d0d21/energy_intervals.csv` (12,827 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-zone-sum-d8320f8fc43d0d21-energy-monthly-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Simplified-zone-sum-d8320f8fc43d0d21/energy_monthly.csv` (12,098 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-zone-sum-d8320f8fc43d0d21-metadata-json"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Simplified-zone-sum-d8320f8fc43d0d21/metadata.json` (845 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-zone-sum-d8320f8fc43d0d21-service-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/Simplified-zone-sum-d8320f8fc43d0d21/service_intervals.csv` (11,503 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-fixed-collapsed-51a566feb597e35f-energy-inputs-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-fixed-collapsed-51a566feb597e35f/energy_inputs.csv` (2,392 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-fixed-collapsed-51a566feb597e35f-energy-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-fixed-collapsed-51a566feb597e35f/energy_intervals.csv` (12,913 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-fixed-collapsed-51a566feb597e35f-energy-monthly-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-fixed-collapsed-51a566feb597e35f/energy_monthly.csv` (12,184 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-fixed-collapsed-51a566feb597e35f-metadata-json"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-fixed-collapsed-51a566feb597e35f/metadata.json` (843 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-fixed-collapsed-51a566feb597e35f-service-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-fixed-collapsed-51a566feb597e35f/service_intervals.csv` (11,849 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-fixed-zone-sum-a8c7e5295b02972c-energy-inputs-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-fixed-zone-sum-a8c7e5295b02972c/energy_inputs.csv` (2,421 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-fixed-zone-sum-a8c7e5295b02972c-energy-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-fixed-zone-sum-a8c7e5295b02972c/energy_intervals.csv` (12,975 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-fixed-zone-sum-a8c7e5295b02972c-energy-monthly-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-fixed-zone-sum-a8c7e5295b02972c/energy_monthly.csv` (12,246 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-fixed-zone-sum-a8c7e5295b02972c-metadata-json"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-fixed-zone-sum-a8c7e5295b02972c/metadata.json` (845 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-fixed-zone-sum-a8c7e5295b02972c-service-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-fixed-zone-sum-a8c7e5295b02972c/service_intervals.csv` (11,999 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-linear-collapsed-82a6aace7797e65c-energy-inputs-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-linear-collapsed-82a6aace7797e65c/energy_inputs.csv` (2,435 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-linear-collapsed-82a6aace7797e65c-energy-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-linear-collapsed-82a6aace7797e65c/energy_intervals.csv` (12,996 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-linear-collapsed-82a6aace7797e65c-energy-monthly-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-linear-collapsed-82a6aace7797e65c/energy_monthly.csv` (12,267 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-linear-collapsed-82a6aace7797e65c-metadata-json"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-linear-collapsed-82a6aace7797e65c/metadata.json` (844 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-linear-collapsed-82a6aace7797e65c-service-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-linear-collapsed-82a6aace7797e65c/service_intervals.csv` (12,050 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-linear-zone-sum-5488d1dc81141d59-energy-inputs-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-linear-zone-sum-5488d1dc81141d59/energy_inputs.csv` (2,436 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-linear-zone-sum-5488d1dc81141d59-energy-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-linear-zone-sum-5488d1dc81141d59/energy_intervals.csv` (12,997 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-linear-zone-sum-5488d1dc81141d59-energy-monthly-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-linear-zone-sum-5488d1dc81141d59/energy_monthly.csv` (12,268 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-linear-zone-sum-5488d1dc81141d59-metadata-json"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-linear-zone-sum-5488d1dc81141d59/metadata.json` (846 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-linear-zone-sum-5488d1dc81141d59-service-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-linear-zone-sum-5488d1dc81141d59/service_intervals.csv` (12,008 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-monthly-collapsed-a74316a5e10e4775-energy-inputs-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-monthly-collapsed-a74316a5e10e4775/energy_inputs.csv` (2,436 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-monthly-collapsed-a74316a5e10e4775-energy-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-monthly-collapsed-a74316a5e10e4775/energy_intervals.csv` (13,022 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-monthly-collapsed-a74316a5e10e4775-energy-monthly-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-monthly-collapsed-a74316a5e10e4775/energy_monthly.csv` (12,293 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-monthly-collapsed-a74316a5e10e4775-metadata-json"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-monthly-collapsed-a74316a5e10e4775/metadata.json` (845 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-monthly-collapsed-a74316a5e10e4775-service-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-monthly-collapsed-a74316a5e10e4775/service_intervals.csv` (12,034 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-monthly-zone-sum-f552bb598b3e6d60-energy-inputs-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-monthly-zone-sum-f552bb598b3e6d60/energy_inputs.csv` (2,438 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-monthly-zone-sum-f552bb598b3e6d60-energy-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-monthly-zone-sum-f552bb598b3e6d60/energy_intervals.csv` (13,018 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-monthly-zone-sum-f552bb598b3e6d60-energy-monthly-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-monthly-zone-sum-f552bb598b3e6d60/energy_monthly.csv` (12,289 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-monthly-zone-sum-f552bb598b3e6d60-metadata-json"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-monthly-zone-sum-f552bb598b3e6d60/metadata.json` (847 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vb-monthly-zone-sum-f552bb598b3e6d60-service-intervals-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/VB-monthly-zone-sum-f552bb598b3e6d60/service_intervals.csv` (12,055 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-common-monthly-inputs-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/common_monthly_inputs.csv` (2,002 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-dynamic-5r1c-bf90214702263dcf-thermal-dynamic-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/dynamic_5R1C-bf90214702263dcf/thermal_dynamic.csv` (4,287,059 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-dynamic-7r2c-1b1c401c959ba91c-thermal-dynamic-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/dynamic_7R2C-1b1c401c959ba91c/thermal_dynamic.csv` (4,298,771 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-buildings-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/buildings.csv` (1,109 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-factors-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/factors.csv` (438 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-mapping-manifest-json"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/mapping_manifest.json` (2,846 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-metered-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/metered.csv` (109 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-scenarios-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/scenarios.csv` (448 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-systems-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/systems.csv` (557 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-timeseries-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/timeseries.csv` (2,473 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-buildings-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/buildings.csv` (1,060 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-factors-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/factors.csv` (438 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-mapping-manifest-json"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/mapping_manifest.json` (2,712 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-metered-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/metered.csv` (109 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-scenarios-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/scenarios.csv` (448 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-systems-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/systems.csv` (557 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-timeseries-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/timeseries.csv` (2,480 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-buildings-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/buildings.csv` (1,059 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-factors-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/factors.csv` (438 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-mapping-manifest-json"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/mapping_manifest.json` (2,712 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-metered-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/metered.csv` (109 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-scenarios-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/scenarios.csv` (448 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-systems-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/systems.csv` (557 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-timeseries-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/timeseries.csv` (2,478 bytes)

<a id="reports-shared-energy-cases-1-6b86b273ff34fce1-vbdd-temperature-linear-monthly-dd30913d684803e3-vb-solar-fit-csv"></a>
- `reports/shared_energy/cases/1-6b86b273ff34fce1/vbdd_temperature_linear_monthly_-dd30913d684803e3/vb_solar_fit.csv` (477 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-dynamic-5r1c-64f7f6b31419d901-energy-inputs-csv-gz"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Dynamic-5R1C-64f7f6b31419d901/energy_inputs.csv.gz` (252,308 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-dynamic-5r1c-64f7f6b31419d901-energy-intervals-csv-gz"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Dynamic-5R1C-64f7f6b31419d901/energy_intervals.csv.gz` (1,563,903 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-dynamic-5r1c-64f7f6b31419d901-energy-monthly-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Dynamic-5R1C-64f7f6b31419d901/energy_monthly.csv` (13,408 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-dynamic-5r1c-64f7f6b31419d901-metadata-json"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Dynamic-5R1C-64f7f6b31419d901/metadata.json` (872 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-dynamic-5r1c-64f7f6b31419d901-service-intervals-csv-gz"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Dynamic-5R1C-64f7f6b31419d901/service_intervals.csv.gz` (863,969 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-dynamic-7r2c-d4be1cdecd94554f-energy-inputs-csv-gz"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Dynamic-7R2C-d4be1cdecd94554f/energy_inputs.csv.gz` (251,976 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-dynamic-7r2c-d4be1cdecd94554f-energy-intervals-csv-gz"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Dynamic-7R2C-d4be1cdecd94554f/energy_intervals.csv.gz` (1,566,844 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-dynamic-7r2c-d4be1cdecd94554f-energy-monthly-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Dynamic-7R2C-d4be1cdecd94554f/energy_monthly.csv` (13,416 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-dynamic-7r2c-d4be1cdecd94554f-metadata-json"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Dynamic-7R2C-d4be1cdecd94554f/metadata.json` (872 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-dynamic-7r2c-d4be1cdecd94554f-service-intervals-csv-gz"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Dynamic-7R2C-d4be1cdecd94554f/service_intervals.csv.gz` (859,056 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-monthly-qss-43d11002a2ebfffa-energy-inputs-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Monthly-QSS-43d11002a2ebfffa/energy_inputs.csv` (2,604 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-monthly-qss-43d11002a2ebfffa-energy-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Monthly-QSS-43d11002a2ebfffa/energy_intervals.csv` (14,280 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-monthly-qss-43d11002a2ebfffa-energy-monthly-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Monthly-QSS-43d11002a2ebfffa/energy_monthly.csv` (13,551 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-monthly-qss-43d11002a2ebfffa-metadata-json"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Monthly-QSS-43d11002a2ebfffa/metadata.json` (862 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-monthly-qss-43d11002a2ebfffa-service-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Monthly-QSS-43d11002a2ebfffa/service_intervals.csv` (12,433 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-collapsed-2b3b8beedce40b8a-energy-inputs-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Simplified-collapsed-2b3b8beedce40b8a/energy_inputs.csv` (2,496 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-collapsed-2b3b8beedce40b8a-energy-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Simplified-collapsed-2b3b8beedce40b8a/energy_intervals.csv` (14,125 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-collapsed-2b3b8beedce40b8a-energy-monthly-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Simplified-collapsed-2b3b8beedce40b8a/energy_monthly.csv` (13,396 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-collapsed-2b3b8beedce40b8a-metadata-json"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Simplified-collapsed-2b3b8beedce40b8a/metadata.json` (880 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-collapsed-2b3b8beedce40b8a-service-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Simplified-collapsed-2b3b8beedce40b8a/service_intervals.csv` (11,919 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-zone-sum-d8320f8fc43d0d21-energy-inputs-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Simplified-zone-sum-d8320f8fc43d0d21/energy_inputs.csv` (2,499 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-zone-sum-d8320f8fc43d0d21-energy-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Simplified-zone-sum-d8320f8fc43d0d21/energy_intervals.csv` (14,127 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-zone-sum-d8320f8fc43d0d21-energy-monthly-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Simplified-zone-sum-d8320f8fc43d0d21/energy_monthly.csv` (13,398 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-zone-sum-d8320f8fc43d0d21-metadata-json"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Simplified-zone-sum-d8320f8fc43d0d21/metadata.json` (881 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-zone-sum-d8320f8fc43d0d21-service-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/Simplified-zone-sum-d8320f8fc43d0d21/service_intervals.csv` (11,953 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-fixed-collapsed-51a566feb597e35f-energy-inputs-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-fixed-collapsed-51a566feb597e35f/energy_inputs.csv` (2,576 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-fixed-collapsed-51a566feb597e35f-energy-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-fixed-collapsed-51a566feb597e35f/energy_intervals.csv` (14,198 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-fixed-collapsed-51a566feb597e35f-energy-monthly-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-fixed-collapsed-51a566feb597e35f/energy_monthly.csv` (13,469 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-fixed-collapsed-51a566feb597e35f-metadata-json"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-fixed-collapsed-51a566feb597e35f/metadata.json` (880 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-fixed-collapsed-51a566feb597e35f-service-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-fixed-collapsed-51a566feb597e35f/service_intervals.csv` (12,347 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-fixed-zone-sum-a8c7e5295b02972c-energy-inputs-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-fixed-zone-sum-a8c7e5295b02972c/energy_inputs.csv` (2,603 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-fixed-zone-sum-a8c7e5295b02972c-energy-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-fixed-zone-sum-a8c7e5295b02972c/energy_intervals.csv` (14,304 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-fixed-zone-sum-a8c7e5295b02972c-energy-monthly-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-fixed-zone-sum-a8c7e5295b02972c/energy_monthly.csv` (13,575 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-fixed-zone-sum-a8c7e5295b02972c-metadata-json"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-fixed-zone-sum-a8c7e5295b02972c/metadata.json` (882 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-fixed-zone-sum-a8c7e5295b02972c-service-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-fixed-zone-sum-a8c7e5295b02972c/service_intervals.csv` (12,452 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-linear-collapsed-82a6aace7797e65c-energy-inputs-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-linear-collapsed-82a6aace7797e65c/energy_inputs.csv` (2,605 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-linear-collapsed-82a6aace7797e65c-energy-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-linear-collapsed-82a6aace7797e65c/energy_intervals.csv` (14,342 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-linear-collapsed-82a6aace7797e65c-energy-monthly-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-linear-collapsed-82a6aace7797e65c/energy_monthly.csv` (13,613 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-linear-collapsed-82a6aace7797e65c-metadata-json"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-linear-collapsed-82a6aace7797e65c/metadata.json` (882 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-linear-collapsed-82a6aace7797e65c-service-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-linear-collapsed-82a6aace7797e65c/service_intervals.csv` (12,492 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-linear-zone-sum-5488d1dc81141d59-energy-inputs-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-linear-zone-sum-5488d1dc81141d59/energy_inputs.csv` (2,603 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-linear-zone-sum-5488d1dc81141d59-energy-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-linear-zone-sum-5488d1dc81141d59/energy_intervals.csv` (14,272 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-linear-zone-sum-5488d1dc81141d59-energy-monthly-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-linear-zone-sum-5488d1dc81141d59/energy_monthly.csv` (13,543 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-linear-zone-sum-5488d1dc81141d59-metadata-json"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-linear-zone-sum-5488d1dc81141d59/metadata.json` (884 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-linear-zone-sum-5488d1dc81141d59-service-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-linear-zone-sum-5488d1dc81141d59/service_intervals.csv` (12,481 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-monthly-collapsed-a74316a5e10e4775-energy-inputs-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-monthly-collapsed-a74316a5e10e4775/energy_inputs.csv` (2,601 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-monthly-collapsed-a74316a5e10e4775-energy-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-monthly-collapsed-a74316a5e10e4775/energy_intervals.csv` (14,273 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-monthly-collapsed-a74316a5e10e4775-energy-monthly-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-monthly-collapsed-a74316a5e10e4775/energy_monthly.csv` (13,544 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-monthly-collapsed-a74316a5e10e4775-metadata-json"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-monthly-collapsed-a74316a5e10e4775/metadata.json` (882 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-monthly-collapsed-a74316a5e10e4775-service-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-monthly-collapsed-a74316a5e10e4775/service_intervals.csv` (12,505 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-monthly-zone-sum-f552bb598b3e6d60-energy-inputs-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-monthly-zone-sum-f552bb598b3e6d60/energy_inputs.csv` (2,606 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-monthly-zone-sum-f552bb598b3e6d60-energy-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-monthly-zone-sum-f552bb598b3e6d60/energy_intervals.csv` (14,308 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-monthly-zone-sum-f552bb598b3e6d60-energy-monthly-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-monthly-zone-sum-f552bb598b3e6d60/energy_monthly.csv` (13,579 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-monthly-zone-sum-f552bb598b3e6d60-metadata-json"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-monthly-zone-sum-f552bb598b3e6d60/metadata.json` (884 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vb-monthly-zone-sum-f552bb598b3e6d60-service-intervals-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/VB-monthly-zone-sum-f552bb598b3e6d60/service_intervals.csv` (12,461 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-common-monthly-inputs-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/common_monthly_inputs.csv` (2,170 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-dynamic-5r1c-bf90214702263dcf-thermal-dynamic-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/dynamic_5R1C-bf90214702263dcf/thermal_dynamic.csv` (4,110,206 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-dynamic-7r2c-1b1c401c959ba91c-thermal-dynamic-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/dynamic_7R2C-1b1c401c959ba91c/thermal_dynamic.csv` (4,125,229 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-buildings-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/buildings.csv` (1,092 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-factors-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/factors.csv` (438 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-mapping-manifest-json"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/mapping_manifest.json` (2,829 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-metered-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/metered.csv` (109 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-scenarios-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/scenarios.csv` (448 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-systems-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/systems.csv` (557 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-timeseries-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/timeseries.csv` (2,481 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-buildings-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/buildings.csv` (1,076 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-factors-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/factors.csv` (438 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-mapping-manifest-json"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/mapping_manifest.json` (2,729 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-metered-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/metered.csv` (109 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-scenarios-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/scenarios.csv` (448 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-systems-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/systems.csv` (557 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-timeseries-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/timeseries.csv` (2,481 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-buildings-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/buildings.csv` (1,032 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-factors-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/factors.csv` (438 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-mapping-manifest-json"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/mapping_manifest.json` (2,684 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-metered-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/metered.csv` (109 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-scenarios-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/scenarios.csv` (448 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-systems-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/systems.csv` (557 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-timeseries-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/timeseries.csv` (2,475 bytes)

<a id="reports-shared-energy-cases-18-4ec9599fc203d176-vbdd-temperature-linear-monthly-dd30913d684803e3-vb-solar-fit-csv"></a>
- `reports/shared_energy/cases/18-4ec9599fc203d176/vbdd_temperature_linear_monthly_-dd30913d684803e3/vb_solar_fit.csv` (478 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-dynamic-5r1c-64f7f6b31419d901-energy-inputs-csv-gz"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Dynamic-5R1C-64f7f6b31419d901/energy_inputs.csv.gz` (186,091 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-dynamic-5r1c-64f7f6b31419d901-energy-intervals-csv-gz"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Dynamic-5R1C-64f7f6b31419d901/energy_intervals.csv.gz` (1,040,496 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-dynamic-5r1c-64f7f6b31419d901-energy-monthly-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Dynamic-5R1C-64f7f6b31419d901/energy_monthly.csv` (11,076 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-dynamic-5r1c-64f7f6b31419d901-metadata-json"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Dynamic-5R1C-64f7f6b31419d901/metadata.json` (836 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-dynamic-5r1c-64f7f6b31419d901-service-intervals-csv-gz"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Dynamic-5R1C-64f7f6b31419d901/service_intervals.csv.gz` (787,318 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-dynamic-7r2c-d4be1cdecd94554f-energy-inputs-csv-gz"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Dynamic-7R2C-d4be1cdecd94554f/energy_inputs.csv.gz` (184,843 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-dynamic-7r2c-d4be1cdecd94554f-energy-intervals-csv-gz"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Dynamic-7R2C-d4be1cdecd94554f/energy_intervals.csv.gz` (1,038,272 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-dynamic-7r2c-d4be1cdecd94554f-energy-monthly-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Dynamic-7R2C-d4be1cdecd94554f/energy_monthly.csv` (11,119 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-dynamic-7r2c-d4be1cdecd94554f-metadata-json"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Dynamic-7R2C-d4be1cdecd94554f/metadata.json` (836 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-dynamic-7r2c-d4be1cdecd94554f-service-intervals-csv-gz"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Dynamic-7R2C-d4be1cdecd94554f/service_intervals.csv.gz` (780,510 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-monthly-qss-43d11002a2ebfffa-energy-inputs-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Monthly-QSS-43d11002a2ebfffa/energy_inputs.csv` (2,251 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-monthly-qss-43d11002a2ebfffa-energy-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Monthly-QSS-43d11002a2ebfffa/energy_intervals.csv` (11,645 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-monthly-qss-43d11002a2ebfffa-energy-monthly-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Monthly-QSS-43d11002a2ebfffa/energy_monthly.csv` (10,916 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-monthly-qss-43d11002a2ebfffa-metadata-json"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Monthly-QSS-43d11002a2ebfffa/metadata.json` (825 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-monthly-qss-43d11002a2ebfffa-service-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Monthly-QSS-43d11002a2ebfffa/service_intervals.csv` (11,711 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-collapsed-2b3b8beedce40b8a-energy-inputs-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Simplified-collapsed-2b3b8beedce40b8a/energy_inputs.csv` (2,153 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-collapsed-2b3b8beedce40b8a-energy-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Simplified-collapsed-2b3b8beedce40b8a/energy_intervals.csv` (11,449 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-collapsed-2b3b8beedce40b8a-energy-monthly-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Simplified-collapsed-2b3b8beedce40b8a/energy_monthly.csv` (10,720 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-collapsed-2b3b8beedce40b8a-metadata-json"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Simplified-collapsed-2b3b8beedce40b8a/metadata.json` (843 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-collapsed-2b3b8beedce40b8a-service-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Simplified-collapsed-2b3b8beedce40b8a/service_intervals.csv` (11,254 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-zone-sum-d8320f8fc43d0d21-energy-inputs-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Simplified-zone-sum-d8320f8fc43d0d21/energy_inputs.csv` (2,156 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-zone-sum-d8320f8fc43d0d21-energy-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Simplified-zone-sum-d8320f8fc43d0d21/energy_intervals.csv` (11,409 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-zone-sum-d8320f8fc43d0d21-energy-monthly-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Simplified-zone-sum-d8320f8fc43d0d21/energy_monthly.csv` (10,680 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-zone-sum-d8320f8fc43d0d21-metadata-json"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Simplified-zone-sum-d8320f8fc43d0d21/metadata.json` (845 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-zone-sum-d8320f8fc43d0d21-service-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/Simplified-zone-sum-d8320f8fc43d0d21/service_intervals.csv` (11,246 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-fixed-collapsed-51a566feb597e35f-energy-inputs-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-fixed-collapsed-51a566feb597e35f/energy_inputs.csv` (2,226 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-fixed-collapsed-51a566feb597e35f-energy-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-fixed-collapsed-51a566feb597e35f/energy_intervals.csv` (11,605 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-fixed-collapsed-51a566feb597e35f-energy-monthly-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-fixed-collapsed-51a566feb597e35f/energy_monthly.csv` (10,876 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-fixed-collapsed-51a566feb597e35f-metadata-json"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-fixed-collapsed-51a566feb597e35f/metadata.json` (844 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-fixed-collapsed-51a566feb597e35f-service-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-fixed-collapsed-51a566feb597e35f/service_intervals.csv` (11,646 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-fixed-zone-sum-a8c7e5295b02972c-energy-inputs-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-fixed-zone-sum-a8c7e5295b02972c/energy_inputs.csv` (2,251 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-fixed-zone-sum-a8c7e5295b02972c-energy-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-fixed-zone-sum-a8c7e5295b02972c/energy_intervals.csv` (11,668 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-fixed-zone-sum-a8c7e5295b02972c-energy-monthly-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-fixed-zone-sum-a8c7e5295b02972c/energy_monthly.csv` (10,939 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-fixed-zone-sum-a8c7e5295b02972c-metadata-json"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-fixed-zone-sum-a8c7e5295b02972c/metadata.json` (845 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-fixed-zone-sum-a8c7e5295b02972c-service-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-fixed-zone-sum-a8c7e5295b02972c/service_intervals.csv` (11,757 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-linear-collapsed-82a6aace7797e65c-energy-inputs-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-linear-collapsed-82a6aace7797e65c/energy_inputs.csv` (2,258 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-linear-collapsed-82a6aace7797e65c-energy-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-linear-collapsed-82a6aace7797e65c/energy_intervals.csv` (11,675 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-linear-collapsed-82a6aace7797e65c-energy-monthly-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-linear-collapsed-82a6aace7797e65c/energy_monthly.csv` (10,946 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-linear-collapsed-82a6aace7797e65c-metadata-json"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-linear-collapsed-82a6aace7797e65c/metadata.json` (844 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-linear-collapsed-82a6aace7797e65c-service-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-linear-collapsed-82a6aace7797e65c/service_intervals.csv` (11,792 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-linear-zone-sum-5488d1dc81141d59-energy-inputs-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-linear-zone-sum-5488d1dc81141d59/energy_inputs.csv` (2,257 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-linear-zone-sum-5488d1dc81141d59-energy-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-linear-zone-sum-5488d1dc81141d59/energy_intervals.csv` (11,666 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-linear-zone-sum-5488d1dc81141d59-energy-monthly-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-linear-zone-sum-5488d1dc81141d59/energy_monthly.csv` (10,937 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-linear-zone-sum-5488d1dc81141d59-metadata-json"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-linear-zone-sum-5488d1dc81141d59/metadata.json` (846 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-linear-zone-sum-5488d1dc81141d59-service-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-linear-zone-sum-5488d1dc81141d59/service_intervals.csv` (11,774 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-monthly-collapsed-a74316a5e10e4775-energy-inputs-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-monthly-collapsed-a74316a5e10e4775/energy_inputs.csv` (2,256 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-monthly-collapsed-a74316a5e10e4775-energy-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-monthly-collapsed-a74316a5e10e4775/energy_intervals.csv` (11,732 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-monthly-collapsed-a74316a5e10e4775-energy-monthly-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-monthly-collapsed-a74316a5e10e4775/energy_monthly.csv` (11,003 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-monthly-collapsed-a74316a5e10e4775-metadata-json"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-monthly-collapsed-a74316a5e10e4775/metadata.json` (845 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-monthly-collapsed-a74316a5e10e4775-service-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-monthly-collapsed-a74316a5e10e4775/service_intervals.csv` (11,754 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-monthly-zone-sum-f552bb598b3e6d60-energy-inputs-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-monthly-zone-sum-f552bb598b3e6d60/energy_inputs.csv` (2,253 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-monthly-zone-sum-f552bb598b3e6d60-energy-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-monthly-zone-sum-f552bb598b3e6d60/energy_intervals.csv` (11,677 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-monthly-zone-sum-f552bb598b3e6d60-energy-monthly-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-monthly-zone-sum-f552bb598b3e6d60/energy_monthly.csv` (10,948 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-monthly-zone-sum-f552bb598b3e6d60-metadata-json"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-monthly-zone-sum-f552bb598b3e6d60/metadata.json` (847 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vb-monthly-zone-sum-f552bb598b3e6d60-service-intervals-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/VB-monthly-zone-sum-f552bb598b3e6d60/service_intervals.csv` (11,750 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-common-monthly-inputs-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/common_monthly_inputs.csv` (1,828 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-dynamic-5r1c-bf90214702263dcf-thermal-dynamic-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/dynamic_5R1C-bf90214702263dcf/thermal_dynamic.csv` (4,068,924 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-dynamic-7r2c-1b1c401c959ba91c-thermal-dynamic-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/dynamic_7R2C-1b1c401c959ba91c/thermal_dynamic.csv` (4,072,467 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-buildings-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/buildings.csv` (1,057 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-factors-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/factors.csv` (438 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-mapping-manifest-json"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/mapping_manifest.json` (2,794 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-metered-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/metered.csv` (109 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-scenarios-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/scenarios.csv` (448 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-systems-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/systems.csv` (557 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-timeseries-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/timeseries.csv` (2,476 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-buildings-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/buildings.csv` (1,054 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-factors-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/factors.csv` (438 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-mapping-manifest-json"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/mapping_manifest.json` (2,705 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-metered-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/metered.csv` (109 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-scenarios-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/scenarios.csv` (448 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-systems-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/systems.csv` (557 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-timeseries-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/timeseries.csv` (2,482 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-buildings-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/buildings.csv` (1,026 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-factors-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/factors.csv` (438 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-mapping-manifest-json"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/mapping_manifest.json` (2,680 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-metered-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/metered.csv` (109 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-scenarios-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/scenarios.csv` (448 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-systems-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/systems.csv` (557 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-timeseries-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/timeseries.csv` (2,475 bytes)

<a id="reports-shared-energy-cases-19-9400f1b21cb527d7-vbdd-temperature-linear-monthly-dd30913d684803e3-vb-solar-fit-csv"></a>
- `reports/shared_energy/cases/19-9400f1b21cb527d7/vbdd_temperature_linear_monthly_-dd30913d684803e3/vb_solar_fit.csv` (476 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-dynamic-5r1c-64f7f6b31419d901-energy-inputs-csv-gz"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Dynamic-5R1C-64f7f6b31419d901/energy_inputs.csv.gz` (222,166 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-dynamic-5r1c-64f7f6b31419d901-energy-intervals-csv-gz"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Dynamic-5R1C-64f7f6b31419d901/energy_intervals.csv.gz` (1,380,338 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-dynamic-5r1c-64f7f6b31419d901-energy-monthly-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Dynamic-5R1C-64f7f6b31419d901/energy_monthly.csv` (13,361 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-dynamic-5r1c-64f7f6b31419d901-metadata-json"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Dynamic-5R1C-64f7f6b31419d901/metadata.json` (891 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-dynamic-5r1c-64f7f6b31419d901-service-intervals-csv-gz"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Dynamic-5R1C-64f7f6b31419d901/service_intervals.csv.gz` (733,630 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-dynamic-7r2c-d4be1cdecd94554f-energy-inputs-csv-gz"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Dynamic-7R2C-d4be1cdecd94554f/energy_inputs.csv.gz` (220,367 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-dynamic-7r2c-d4be1cdecd94554f-energy-intervals-csv-gz"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Dynamic-7R2C-d4be1cdecd94554f/energy_intervals.csv.gz` (1,374,815 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-dynamic-7r2c-d4be1cdecd94554f-energy-monthly-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Dynamic-7R2C-d4be1cdecd94554f/energy_monthly.csv` (13,349 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-dynamic-7r2c-d4be1cdecd94554f-metadata-json"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Dynamic-7R2C-d4be1cdecd94554f/metadata.json` (890 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-dynamic-7r2c-d4be1cdecd94554f-service-intervals-csv-gz"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Dynamic-7R2C-d4be1cdecd94554f/service_intervals.csv.gz` (725,189 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-monthly-qss-43d11002a2ebfffa-energy-inputs-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Monthly-QSS-43d11002a2ebfffa/energy_inputs.csv` (2,418 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-monthly-qss-43d11002a2ebfffa-energy-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Monthly-QSS-43d11002a2ebfffa/energy_intervals.csv` (13,668 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-monthly-qss-43d11002a2ebfffa-energy-monthly-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Monthly-QSS-43d11002a2ebfffa/energy_monthly.csv` (12,939 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-monthly-qss-43d11002a2ebfffa-metadata-json"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Monthly-QSS-43d11002a2ebfffa/metadata.json` (862 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-monthly-qss-43d11002a2ebfffa-service-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Monthly-QSS-43d11002a2ebfffa/service_intervals.csv` (11,946 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-collapsed-2b3b8beedce40b8a-energy-inputs-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Simplified-collapsed-2b3b8beedce40b8a/energy_inputs.csv` (2,345 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-collapsed-2b3b8beedce40b8a-energy-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Simplified-collapsed-2b3b8beedce40b8a/energy_intervals.csv` (13,512 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-collapsed-2b3b8beedce40b8a-energy-monthly-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Simplified-collapsed-2b3b8beedce40b8a/energy_monthly.csv` (12,783 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-collapsed-2b3b8beedce40b8a-metadata-json"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Simplified-collapsed-2b3b8beedce40b8a/metadata.json` (880 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-collapsed-2b3b8beedce40b8a-service-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Simplified-collapsed-2b3b8beedce40b8a/service_intervals.csv` (11,553 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-zone-sum-d8320f8fc43d0d21-energy-inputs-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Simplified-zone-sum-d8320f8fc43d0d21/energy_inputs.csv` (2,348 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-zone-sum-d8320f8fc43d0d21-energy-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Simplified-zone-sum-d8320f8fc43d0d21/energy_intervals.csv` (13,527 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-zone-sum-d8320f8fc43d0d21-energy-monthly-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Simplified-zone-sum-d8320f8fc43d0d21/energy_monthly.csv` (12,798 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-zone-sum-d8320f8fc43d0d21-metadata-json"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Simplified-zone-sum-d8320f8fc43d0d21/metadata.json` (882 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-zone-sum-d8320f8fc43d0d21-service-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/Simplified-zone-sum-d8320f8fc43d0d21/service_intervals.csv` (11,582 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-fixed-collapsed-51a566feb597e35f-energy-inputs-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-fixed-collapsed-51a566feb597e35f/energy_inputs.csv` (2,370 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-fixed-collapsed-51a566feb597e35f-energy-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-fixed-collapsed-51a566feb597e35f/energy_intervals.csv` (13,488 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-fixed-collapsed-51a566feb597e35f-energy-monthly-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-fixed-collapsed-51a566feb597e35f/energy_monthly.csv` (12,759 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-fixed-collapsed-51a566feb597e35f-metadata-json"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-fixed-collapsed-51a566feb597e35f/metadata.json` (881 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-fixed-collapsed-51a566feb597e35f-service-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-fixed-collapsed-51a566feb597e35f/service_intervals.csv` (11,749 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-fixed-zone-sum-a8c7e5295b02972c-energy-inputs-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-fixed-zone-sum-a8c7e5295b02972c/energy_inputs.csv` (2,372 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-fixed-zone-sum-a8c7e5295b02972c-energy-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-fixed-zone-sum-a8c7e5295b02972c/energy_intervals.csv` (13,533 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-fixed-zone-sum-a8c7e5295b02972c-energy-monthly-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-fixed-zone-sum-a8c7e5295b02972c/energy_monthly.csv` (12,804 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-fixed-zone-sum-a8c7e5295b02972c-metadata-json"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-fixed-zone-sum-a8c7e5295b02972c/metadata.json` (881 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-fixed-zone-sum-a8c7e5295b02972c-service-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-fixed-zone-sum-a8c7e5295b02972c/service_intervals.csv` (11,735 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-linear-collapsed-82a6aace7797e65c-energy-inputs-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-linear-collapsed-82a6aace7797e65c/energy_inputs.csv` (2,414 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-linear-collapsed-82a6aace7797e65c-energy-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-linear-collapsed-82a6aace7797e65c/energy_intervals.csv` (13,596 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-linear-collapsed-82a6aace7797e65c-energy-monthly-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-linear-collapsed-82a6aace7797e65c/energy_monthly.csv` (12,867 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-linear-collapsed-82a6aace7797e65c-metadata-json"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-linear-collapsed-82a6aace7797e65c/metadata.json` (880 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-linear-collapsed-82a6aace7797e65c-service-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-linear-collapsed-82a6aace7797e65c/service_intervals.csv` (11,948 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-linear-zone-sum-5488d1dc81141d59-energy-inputs-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-linear-zone-sum-5488d1dc81141d59/energy_inputs.csv` (2,416 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-linear-zone-sum-5488d1dc81141d59-energy-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-linear-zone-sum-5488d1dc81141d59/energy_intervals.csv` (13,600 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-linear-zone-sum-5488d1dc81141d59-energy-monthly-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-linear-zone-sum-5488d1dc81141d59/energy_monthly.csv` (12,871 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-linear-zone-sum-5488d1dc81141d59-metadata-json"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-linear-zone-sum-5488d1dc81141d59/metadata.json` (882 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-linear-zone-sum-5488d1dc81141d59-service-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-linear-zone-sum-5488d1dc81141d59/service_intervals.csv` (11,987 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-monthly-collapsed-a74316a5e10e4775-energy-inputs-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-monthly-collapsed-a74316a5e10e4775/energy_inputs.csv` (2,414 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-monthly-collapsed-a74316a5e10e4775-energy-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-monthly-collapsed-a74316a5e10e4775/energy_intervals.csv` (13,644 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-monthly-collapsed-a74316a5e10e4775-energy-monthly-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-monthly-collapsed-a74316a5e10e4775/energy_monthly.csv` (12,915 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-monthly-collapsed-a74316a5e10e4775-metadata-json"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-monthly-collapsed-a74316a5e10e4775/metadata.json` (882 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-monthly-collapsed-a74316a5e10e4775-service-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-monthly-collapsed-a74316a5e10e4775/service_intervals.csv` (12,010 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-monthly-zone-sum-f552bb598b3e6d60-energy-inputs-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-monthly-zone-sum-f552bb598b3e6d60/energy_inputs.csv` (2,413 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-monthly-zone-sum-f552bb598b3e6d60-energy-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-monthly-zone-sum-f552bb598b3e6d60/energy_intervals.csv` (13,630 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-monthly-zone-sum-f552bb598b3e6d60-energy-monthly-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-monthly-zone-sum-f552bb598b3e6d60/energy_monthly.csv` (12,901 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-monthly-zone-sum-f552bb598b3e6d60-metadata-json"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-monthly-zone-sum-f552bb598b3e6d60/metadata.json` (883 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vb-monthly-zone-sum-f552bb598b3e6d60-service-intervals-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/VB-monthly-zone-sum-f552bb598b3e6d60/service_intervals.csv` (11,913 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-common-monthly-inputs-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/common_monthly_inputs.csv` (2,018 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-dynamic-5r1c-bf90214702263dcf-thermal-dynamic-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/dynamic_5R1C-bf90214702263dcf/thermal_dynamic.csv` (4,066,917 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-dynamic-7r2c-1b1c401c959ba91c-thermal-dynamic-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/dynamic_7R2C-1b1c401c959ba91c/thermal_dynamic.csv` (4,068,033 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-buildings-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/buildings.csv` (1,059 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-factors-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/factors.csv` (438 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-mapping-manifest-json"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/mapping_manifest.json` (2,794 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-metered-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/metered.csv` (109 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-scenarios-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/scenarios.csv` (448 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-systems-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/systems.csv` (557 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-timeseries-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/timeseries.csv` (2,474 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-buildings-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/buildings.csv` (1,043 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-factors-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/factors.csv` (438 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-mapping-manifest-json"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/mapping_manifest.json` (2,697 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-metered-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/metered.csv` (109 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-scenarios-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/scenarios.csv` (448 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-systems-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/systems.csv` (557 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-lower-8c6fb1e9e37a1aea-timeseries-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/lower-8c6fb1e9e37a1aea/timeseries.csv` (2,474 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-buildings-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/buildings.csv` (1,047 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-factors-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/factors.csv` (438 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-mapping-manifest-json"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/mapping_manifest.json` (2,698 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-metered-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/metered.csv` (109 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-scenarios-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/scenarios.csv` (448 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-systems-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/systems.csv` (557 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-upper-aee6105582920237-timeseries-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/upper-aee6105582920237/timeseries.csv` (2,472 bytes)

<a id="reports-shared-energy-cases-20-f5ca38f748a1d6ea-vbdd-temperature-linear-monthly-dd30913d684803e3-vb-solar-fit-csv"></a>
- `reports/shared_energy/cases/20-f5ca38f748a1d6ea/vbdd_temperature_linear_monthly_-dd30913d684803e3/vb_solar_fit.csv` (477 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-dynamic-5r1c-64f7f6b31419d901-energy-inputs-csv-gz"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Dynamic-5R1C-64f7f6b31419d901/energy_inputs.csv.gz` (191,628 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-dynamic-5r1c-64f7f6b31419d901-energy-intervals-csv-gz"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Dynamic-5R1C-64f7f6b31419d901/energy_intervals.csv.gz` (1,323,741 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-dynamic-5r1c-64f7f6b31419d901-energy-monthly-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Dynamic-5R1C-64f7f6b31419d901/energy_monthly.csv` (12,389 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-dynamic-5r1c-64f7f6b31419d901-metadata-json"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Dynamic-5R1C-64f7f6b31419d901/metadata.json` (830 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-dynamic-5r1c-64f7f6b31419d901-service-intervals-csv-gz"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Dynamic-5R1C-64f7f6b31419d901/service_intervals.csv.gz` (710,214 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-dynamic-7r2c-d4be1cdecd94554f-energy-inputs-csv-gz"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Dynamic-7R2C-d4be1cdecd94554f/energy_inputs.csv.gz` (191,652 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-dynamic-7r2c-d4be1cdecd94554f-energy-intervals-csv-gz"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Dynamic-7R2C-d4be1cdecd94554f/energy_intervals.csv.gz` (1,323,399 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-dynamic-7r2c-d4be1cdecd94554f-energy-monthly-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Dynamic-7R2C-d4be1cdecd94554f/energy_monthly.csv` (12,346 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-dynamic-7r2c-d4be1cdecd94554f-metadata-json"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Dynamic-7R2C-d4be1cdecd94554f/metadata.json` (830 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-dynamic-7r2c-d4be1cdecd94554f-service-intervals-csv-gz"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Dynamic-7R2C-d4be1cdecd94554f/service_intervals.csv.gz` (710,290 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-monthly-qss-43d11002a2ebfffa-energy-inputs-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Monthly-QSS-43d11002a2ebfffa/energy_inputs.csv` (2,413 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-monthly-qss-43d11002a2ebfffa-energy-intervals-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Monthly-QSS-43d11002a2ebfffa/energy_intervals.csv` (12,983 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-monthly-qss-43d11002a2ebfffa-energy-monthly-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Monthly-QSS-43d11002a2ebfffa/energy_monthly.csv` (12,254 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-monthly-qss-43d11002a2ebfffa-metadata-json"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Monthly-QSS-43d11002a2ebfffa/metadata.json` (820 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-monthly-qss-43d11002a2ebfffa-service-intervals-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Monthly-QSS-43d11002a2ebfffa/service_intervals.csv` (11,926 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-simplified-zone-sum-d8320f8fc43d0d21-energy-inputs-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Simplified-zone-sum-d8320f8fc43d0d21/energy_inputs.csv` (2,343 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-simplified-zone-sum-d8320f8fc43d0d21-energy-intervals-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Simplified-zone-sum-d8320f8fc43d0d21/energy_intervals.csv` (12,834 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-simplified-zone-sum-d8320f8fc43d0d21-energy-monthly-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Simplified-zone-sum-d8320f8fc43d0d21/energy_monthly.csv` (12,105 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-simplified-zone-sum-d8320f8fc43d0d21-metadata-json"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Simplified-zone-sum-d8320f8fc43d0d21/metadata.json` (841 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-simplified-zone-sum-d8320f8fc43d0d21-service-intervals-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/Simplified-zone-sum-d8320f8fc43d0d21/service_intervals.csv` (11,516 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-fixed-zone-sum-a8c7e5295b02972c-energy-inputs-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-fixed-zone-sum-a8c7e5295b02972c/energy_inputs.csv` (2,362 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-fixed-zone-sum-a8c7e5295b02972c-energy-intervals-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-fixed-zone-sum-a8c7e5295b02972c/energy_intervals.csv` (12,868 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-fixed-zone-sum-a8c7e5295b02972c-energy-monthly-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-fixed-zone-sum-a8c7e5295b02972c/energy_monthly.csv` (12,139 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-fixed-zone-sum-a8c7e5295b02972c-metadata-json"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-fixed-zone-sum-a8c7e5295b02972c/metadata.json` (841 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-fixed-zone-sum-a8c7e5295b02972c-service-intervals-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-fixed-zone-sum-a8c7e5295b02972c/service_intervals.csv` (11,631 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-linear-zone-sum-5488d1dc81141d59-energy-inputs-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-linear-zone-sum-5488d1dc81141d59/energy_inputs.csv` (2,416 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-linear-zone-sum-5488d1dc81141d59-energy-intervals-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-linear-zone-sum-5488d1dc81141d59/energy_intervals.csv` (12,969 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-linear-zone-sum-5488d1dc81141d59-energy-monthly-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-linear-zone-sum-5488d1dc81141d59/energy_monthly.csv` (12,240 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-linear-zone-sum-5488d1dc81141d59-metadata-json"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-linear-zone-sum-5488d1dc81141d59/metadata.json` (842 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-linear-zone-sum-5488d1dc81141d59-service-intervals-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-linear-zone-sum-5488d1dc81141d59/service_intervals.csv` (11,860 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-monthly-zone-sum-f552bb598b3e6d60-energy-inputs-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-monthly-zone-sum-f552bb598b3e6d60/energy_inputs.csv` (2,418 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-monthly-zone-sum-f552bb598b3e6d60-energy-intervals-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-monthly-zone-sum-f552bb598b3e6d60/energy_intervals.csv` (13,013 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-monthly-zone-sum-f552bb598b3e6d60-energy-monthly-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-monthly-zone-sum-f552bb598b3e6d60/energy_monthly.csv` (12,284 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-monthly-zone-sum-f552bb598b3e6d60-metadata-json"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-monthly-zone-sum-f552bb598b3e6d60/metadata.json` (842 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vb-monthly-zone-sum-f552bb598b3e6d60-service-intervals-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/VB-monthly-zone-sum-f552bb598b3e6d60/service_intervals.csv` (11,887 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-common-monthly-inputs-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/common_monthly_inputs.csv` (2,013 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-dynamic-5r1c-bf90214702263dcf-thermal-dynamic-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/dynamic_5R1C-bf90214702263dcf/thermal_dynamic.csv` (1,517,274 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-dynamic-7r2c-1b1c401c959ba91c-thermal-dynamic-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/dynamic_7R2C-1b1c401c959ba91c/thermal_dynamic.csv` (1,520,630 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-buildings-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/buildings.csv` (1,065 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-factors-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/factors.csv` (438 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-mapping-manifest-json"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/mapping_manifest.json` (2,711 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-metered-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/metered.csv` (109 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-scenarios-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/scenarios.csv` (448 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-systems-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/systems.csv` (557 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-simplified-direct-monthly-balanc-1e9d48f4d6a307d6-mapped-collapsed-821f983459b6cfc9-timeseries-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/simplified_direct_monthly_balanc-1e9d48f4d6a307d6/mapped/collapsed-821f983459b6cfc9/timeseries.csv` (2,480 bytes)

<a id="reports-shared-energy-cases-21-6f4b6612125fb3a0-vbdd-temperature-linear-monthly-dd30913d684803e3-vb-solar-fit-csv"></a>
- `reports/shared_energy/cases/21-6f4b6612125fb3a0/vbdd_temperature_linear_monthly_-dd30913d684803e3/vb_solar_fit.csv` (223 bytes)

<a id="reports-shared-energy-differences-vs-qss-csv"></a>
- `reports/shared_energy/differences_vs_qss.csv` (114,437 bytes)

<a id="reports-shared-energy-dynamic-monthly-aggregation-csv"></a>
- `reports/shared_energy/dynamic_monthly_aggregation.csv` (205,161 bytes)

<a id="reports-shared-energy-figures-1-6b86b273ff34fce1-monthly-png"></a>
- `reports/shared_energy/figures/1-6b86b273ff34fce1_monthly.png` (202,322 bytes)

<a id="reports-shared-energy-figures-18-4ec9599fc203d176-monthly-png"></a>
- `reports/shared_energy/figures/18-4ec9599fc203d176_monthly.png` (291,891 bytes)

<a id="reports-shared-energy-figures-19-9400f1b21cb527d7-monthly-png"></a>
- `reports/shared_energy/figures/19-9400f1b21cb527d7_monthly.png` (155,560 bytes)

<a id="reports-shared-energy-figures-20-f5ca38f748a1d6ea-monthly-png"></a>
- `reports/shared_energy/figures/20-f5ca38f748a1d6ea_monthly.png` (298,089 bytes)

<a id="reports-shared-energy-figures-21-6f4b6612125fb3a0-monthly-png"></a>
- `reports/shared_energy/figures/21-6f4b6612125fb3a0_monthly.png` (158,662 bytes)

<a id="reports-shared-energy-pv-matching-diagnostics-csv"></a>
- `reports/shared_energy/pv_matching_diagnostics.csv` (92,486 bytes)

<a id="reports-shared-energy-zone-service-monthly-csv"></a>
- `reports/shared_energy/zone_service_monthly.csv` (823,377 bytes)

<a id="reports-workbooks-native-excel-comparison-csv"></a>
- `reports/workbooks/native_excel_comparison.csv` (8,215,420 bytes)

## Local development material

Some historical documents refer to workspace backup snapshots, local execution
outputs or separately supplied literature. These are not required to run or test
the software and are not included in this publication or the reports-only
validation ZIP. The historical references remain as descriptions of the
development process and the source literature used for the equations.
