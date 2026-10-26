# Current repository layout

> Lean GitHub distribution: monthly reference fixtures and selected summaries are included. For the complete hourly/Excel evidence and strict 318-table reproduction, follow [validation archive instructions](validation_archive.md).

The current implementation retains dated validation evidence alongside the
accepted physical baseline. The user keeps a separate backup of the pre-cleanup
folder; subsequent inverse and assessment work has added supporting modules.

| Location | Retained purpose |
|---|---|
| `src/dt_prototype/` | Five main components, shared inputs, supporting `Assessment` and `Inverse_models`, and pipeline dispatch |
| `configs/`, `data/examples/` | Versioned runnable input fixtures |
| `runners/` | Thermal, energy, assessment, quantity, inverse, pipeline and cadastral launchers |
| `tests/`, standalone module `tests/` | Current regression suite; counts and latest evidence are in the root README |
| `spreadsheets/` | Final `Monthly_SS`, `Monthly_SS_simplified` and `Monthly_SS_VBDD` energy workbooks |
| `reports/shared_energy/` | Authoritative five-building results and comparison report |
| `reports/workbooks/` | Native Excel numeric/preservation evidence |
| `reports/reliability_improvements_20261023/` | Current reliability improvements and validation evidence, completed 24 October |
| `reports/reliability_review_20261022/` | Previous review and its original reproduction evidence |
| `src/dt_prototype/schemas/v1/` | Versioned structural input contracts |
| `.github/workflows/`, `requirements-main-verified.lock.txt` | Separate CI jobs and verified main runtime closure |
| Other dated `reports/` folders | Historical implementation/validation evidence tied to its original source state |
| `docs/` | Current architecture, contracts, methods and development guidance |
| `scripts/` | Release/reproduction verification, schema generation, environment capture and source ZIP builder |
| `to_be_integrated/` | Independent LCC/LCA/Circularity calculators and the preserved supplied OpenDSM benchmark; the pipeline does not execute them |
| `src/dt_prototype/monthly_ss_simplified/model3/reference_outputs/` | Immutable embedded Model 3 golden results |

Generated `outputs/`, virtual environments and caches may exist locally and are
ignored by version control. They are not portable input fixtures. The fillable
quantity workbook is retained under `data/examples/asset_quantity_inputs.xlsx`.
Create new user runs under `outputs/`; keep accepted `reports/` evidence immutable.
New dated review folders record new validation rather than replacing old records.

The cleanup removed superseded Monthly_SS_VBDD runs, the pilot energy run, old migration
audits, scripts requiring deleted September outputs, compiled caches, workbook
previews/authored intermediates and the original thermal-only workbook copies.
The final workbooks already contain the preserved thermal calculation sheets.
See [cleanup record](cleanup_20261010.md) for the classification and verification.
