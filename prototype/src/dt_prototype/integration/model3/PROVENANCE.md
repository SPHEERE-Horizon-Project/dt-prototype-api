# Embedded Model 3 baseline

This subpackage preserves the complete Model 3 simulation and calibration
pipeline as an independent comparison implementation. The DT-Prototype adapter
calls `model3.py` directly and does not rewrite its equations.

- Source module SHA-256:
  `d0d4add1770f3e21cb9ae178f4ce8d206554a2ec9da1b63c8e50b55373e26f9c`.
- `example_data/` and `reference_outputs/` support the embedded golden-output
  regression test.
- The imported material has no declared licence or upstream repository/commit.
  It is retained for local verification only; resolve redistribution rights
  before external release.
