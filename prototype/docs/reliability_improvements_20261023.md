# Reliability improvements — 23–24 October 2026

DT-Prototype **0.5.1** implements the agreed reliability actions from the
[previous review](reliability_review_20261022.md). The four thermal solvers,
shared carrier/renewable calculations, asset quantities and LCC/LCA/MCI
algorithms retain their previous numerical behavior. Physical calibration,
pooled statistical models and new portfolio orchestration remain separate,
as explicitly agreed. No measured data were supplied.

## Delivered changes

| Approved action | Implementation |
| --- | --- |
| Resolve the native hourly fit failure | Version-guarded, reversible worker-only metrics compatibility; actual zero coefficient counts retained, no invented coefficient or prediction fallback |
| Establish version control and automated checks | Local Git repository, byte-preserving attributes, generated/private exclusions, separate main and OpenDSM CI jobs, zero-skip evidence gate |
| Formal input contracts and early validation | Nine shipped JSON Schema 2020-12 contracts and `run_preflight.py`, reusing native semantic readers and consolidating independent issues |
| Prepare measured-data validation | Unfilled measured-input template, explicit holdout policy, `run_measured_validation.py`, synthetic data-contract tests and anti-misreporting checks |
| Portable release procedure | Main dependency closure lock, worker freeze, runtime capture, explicit platform matrix and source ZIP builder with commit/file/archive hashes |
| Keep modelling extensions separate | No physical calibration, pooling, new solver or portfolio redesign added |

The hourly compatibility fix permits `num_model_params=0` in the installed
metrics implementation while preserving native `n-p` calculations. It records
patch use and keeps affected models marked for review. It does not modify the
installed OpenDSM package or claim to correct/calibrate all native uncertainty.
See the [technical explanation](opendsm_compatibility.md).

## Verification

The full regression suite passes **503 tests plus three subtests**, with zero
failures, errors or skips. This includes 30 new tests covering schema consistency,
preflight, invalid inputs, acceptance policies, tampering checks, true-zero
metrics, a real former failure, qualification warnings and saved-model reload.
The existing independent LCC/LCA/Circularity tests remain included.

The final source ZIP (commit `f4b40721d5d64075c2ae0da342fa3af41ace7ce1`)
was extracted separately and its **868 files** verified against the included
hash manifest. The complete **503 tests plus three subtests** also pass from
that extracted copy, using the existing verified runtimes. This checks source
relocation, not a fresh dependency installation or another operating system.
See [portable verification](../reports/reliability_improvements_20261023/portable_verification.json).
Use a short extraction path on Windows; long roots can exceed legacy path limits.

The regenerated forward run contains **51 solver cases and 612 building-months**.
All **318 reference CSV tables reproduce exactly**, with maximum absolute
numeric difference **0**. Original calculation workbooks remain unchanged;
release checks reuse their cached/native Excel evidence rather than performing
a new Excel recalculation.

The dynamic five-building inverse comparison now completes **20/20 models**:
5P, billing, hourly nonsolar and hourly solar for each building. The earlier run
completed 16/20. All **52,680 previously available predictions are unchanged**;
the new run adds the formerly failed hourly variants for buildings 1 and 18.
Training metrics for the previously successful models are also preserved.
Native uncertainty remains missing throughout this supplied comparison, so
there is no numerical uncertainty accuracy claim.

The [evidence directory](../reports/reliability_improvements_20261023/) contains
the full JUnit result, forward reproduction, runtime versions, preflight reports,
assessment and release verification, and the machine-readable improvement audit.
The comparison is inspectable in
[model statuses](../reports/reliability_improvements_20261023/inverse_model_status.csv),
[monthly scores](../reports/reliability_improvements_20261023/inverse_monthly_scores.csv)
and [per-building plots](../reports/reliability_improvements_20261023/figures/).

![Monthly training fit comparison](../reports/reliability_improvements_20261023/figures/monthly_fit_comparison.png)

These are simulated single-year training fits. Native qualification, numerical
execution, held-out accuracy and empirical validation are different checks.
Measured-data acceptance is **pending real data**; simulated sources explicitly
cannot pass empirical validation. The example acceptance thresholds require
project-specific approval before viewing holdout results.

## Practical next steps

Use [preflight](input_preflight.md) before a long run and the
[forward/inverse guide](running_forward_and_inverse.md) for execution. When real
meter data become available, follow the
[measured-data instructions](measured_data_validation.md). Use
[release and CI instructions](release_and_ci.md) for dependency setup, local
tests, source archives and eventual hosted CI.

The local repository has no remote: CI is configured and its test commands are
verified locally, but no remote CI run or publication has been performed.
Windows 11 x64 / CPython 3.12.10 is the locally verified environment. Other
platform/runtime combinations need their own qualification. Dependency locks
are supplied; an offline wheelhouse is not included.
