# Hourly zero-coefficient regression fixture

This is **simulated**, not measured data. It retains the building 1 / Dynamic_RC
5R1C electricity-grid-import inputs from the five-building review rerun. The
underlying physical inputs are the supplied `configs/example.json` and
`configs/energy_example.json`, calendar year 2023, fixed UTC+1.

The observations and weather are copied without numerical changes from that
run's isolated hourly worker packet. The independent fixture makes CI runnable
without the original user's `outputs/` directory. It reproduces an hourly
model with zero selected coefficients for some hours: native OpenDSM 1.2.7
raises in metric validation; the version-guarded compatibility layer permits
the true zero count and preserves qualification warnings and reload behaviour.

`config.json` uses paths relative to this directory. Set `opendsm_python` to the
isolated environment before running it. This single-year fit has no holdout;
it verifies execution and serialization, not predictive accuracy.
