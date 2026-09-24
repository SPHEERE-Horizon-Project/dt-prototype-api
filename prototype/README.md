# DT-Prototype

Three independently runnable building-energy tools, one shared input contract:

| Tool | Calculation | Independent launcher |
|---|---|---|
| Dynamic RC | Hourly 5R1C or 7R2C; optional latent loads and technical systems | `runners/run_dynamic.py` |
| Monthly semi-stationary | Monthly sensible zone and AHU demand | `runners/run_monthly.py` |
| Simplified | Independent Model 3 balance; native single-zone, Simplified single-zone collapsed, or zone-sum calculation | `runners/run_simplified.py` |

## Install and run

Use Python 3.10 or later from the project root. The September 2026 audit used Python 3.12.14. Create an environment on each machine; virtual environments are not part of the delivered software.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-verified.txt -e '.[dev]'
python runners/run_dynamic.py --config configs/example_tabular.json --output outputs/my_dynamic --model 5R1C
python runners/run_monthly.py --config configs/example_tabular.json --output outputs/my_monthly
python runners/run_simplified.py --config configs/example_tabular.json --output outputs/my_simplified --zone-mode sum
python -m dt_prototype.integration.model3 --outputs outputs/my_model3_standalone
```

Each command runs independently. Use a fresh output directory every time. Alternatively use `python -m dt_prototype dynamic|monthly|simplified` with the same flags. The launchers are collected in one [runners folder](runners/README.md) and select separate engines from the installed package.

The pinned verification environment requires a Python version supported by those dependency releases. The package's Python 3.10 minimum is not a claim that this exact pinned set runs on 3.10. Use Python 3.12 to reproduce the audit.

All tools accept the same configuration. [example_tabular.json](configs/example_tabular.json) uses normalized CSV geometry; [example.json](configs/example.json) uses the equivalent GeoJSON. Input paths resolve relative to the configuration file. The authoritative physical data are in `data/examples/`; do not maintain separate copies per engine. Each run writes `monthly.csv`, `annual.csv`, detailed results, input hashes, resolved options and a manifest. A failed building is reported while other buildings continue; a failed run returns a nonzero exit code.

The tabular adapter joins [buildings.csv](data/examples/tabular_geometry/buildings.csv), [zones.csv](data/examples/tabular_geometry/zones.csv), and [surfaces.csv](data/examples/tabular_geometry/surfaces.csv) through stable IDs. These tables contain the exact simulation-ready geometry derived from the example GeoJSON, including one or two zones and every heat-exchange surface. They avoid polygon processing while preserving the same engine inputs. The GeoJSON route remains available when footprint geometry is the source. See [input contracts](docs/data_contracts.md).

For a worked procedure covering a new dataset, reuse of stored weather and libraries, versioned portfolio growth, validation and GeoJSON conversion, see [creating and extending a building dataset](docs/input_dataset_tutorial.md).

For simplified calculations, `--zone-mode collapsed` is the **Simplified single-zone collapsed** representation: it combines the full two-zone inputs before one solve. `sum` solves each zone then adds demands. `both` saves both in detailed results and reports the zone sum in the headline monthly/annual files. A native single-zone input requires no second-zone fields.

## Current results

- [September 2026 code audit and verification](docs/audit_20260919.md), including fixes, tests, workbook reconciliation and measured fit timings.
- [Development and web integration guide](docs/development.md), including responsibilities, checks and current deployment limits.
- [Refactor verification and process](docs/refactor_verification.md).
- [Historical annual comparison, relabelled](annual_side_by_side_outputs.md).
- [Simplified spreadsheet](spreadsheets/DT_Prototype_Simplified.xlsx). Its inputs are the mapped monthly representation; it does not directly read the common geometry or EPW sources.
- [Zone terminology and one-zone verification](docs/zone_representation.md).
- [Architecture and removed duplication](docs/architecture.md), [input contracts](docs/data_contracts.md), [scientific decisions](docs/decision_log.md), [source inventory](docs/source_inventory.md).
- [Code-lineage comparison with the imported EUReCA snapshot](docs/code_lineage_comparison.md).

The five case names are Test building 1–5. Stable IDs remain 1, 18, 19, 20 and 21 so joins and deterministic system calculations are preserved. Buildings 1–4 have two independent zones; building 5 has one.

Historical reports, archived sources and `.venv-comparison` mentioned in retained documents are not included in this folder. Reproduce evidence with the commands below. This distribution supplies Python engines and command-line tools; it does not yet include an HTTP service or web interface.

## Verification

```powershell
python -m pytest -q -p no:cacheprovider --basetemp outputs/test_temp_new
python scripts/compare_tools.py --run-id NEW_COMPARISON
python scripts/compare_tools.py --worker dynamic --diagnostic --output outputs/NEW_DIAGNOSTICS
```

The reproduction sequence and workbook requirements are in the [development guide](docs/development.md). The independent Model 3 source, standalone pipeline and golden reference CSVs are together in `src/dt_prototype/integration/model3/`; its common-output adapter is `src/dt_prototype/integration/engines/model3.py`. Earlier sources and superseded reports may be retained separately under `archive/`; active execution does not import them. Required attribution remains in LICENSE and THIRD_PARTY_NOTICES.md.

For a compact GitHub repository, keep `src/`, `configs/`, `data/examples/`, `runners/`, `tests/`, the relevant `docs/` and verification scripts, plus the root package, licence and notice files. Generated `outputs/`, `archive/`, virtual environments, caches, `scripts/node_modules/` and installed-package metadata are not required for execution. Keep `src/dt_prototype/integration/model3/reference_outputs/` because those immutable files protect the Model 3 baseline. Keep the spreadsheet only if workbook delivery is part of the repository scope. The detailed keep/omit list is in [repository contents](docs/repository_contents.md).

These runs verify software preservation and compare models. They do not establish measured-data accuracy or normative compliance.
