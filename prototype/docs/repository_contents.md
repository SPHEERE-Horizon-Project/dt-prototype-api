# Repository contents for GitHub

## Keep for executable examples

- `src/dt_prototype/`: installed source package and all three engines;
- `pyproject.toml`: package metadata, dependencies and command entry point;
- `configs/`: shared GeoJSON and tabular example configurations;
- `data/examples/`: weather, geometry, archetype, schedule and system inputs;
- `runners/`: the three explicitly named independent launchers;
- `README.md`, `LICENSE` and `THIRD_PARTY_NOTICES.md`.

## Keep for a research-grade repository

- `tests/`: regression, integration, schema and cross-model checks;
- `src/dt_prototype/integration/model3/reference_outputs/`: immutable Model 3
  golden fixtures;
- `src/dt_prototype/integration/model3/example_data/` and its methodology and
  provenance documents;
- `docs/`: data contracts, scientific decisions, provenance and verification;
- `scripts/compare_tools.py` and the `scripts/verify_*.py` utilities;
- `requirements-verified.txt`: the dependency versions used for the recorded
  verification environment;
- `.gitignore`.

`AGENTS.md` is not used at runtime, but it records the intended scientific and
development rules and is useful when Codex or another development agent works
on the repository.

## Optional deliverables

- `spreadsheets/`: keep when the independently recalculating workbook is part
  of the published project;
- `annual_side_by_side_outputs.md`: keep when historical comparison context is
  useful;
- report-building and workbook-checking scripts: keep when published reports
  or workbook verification must be regenerated.

## Omit from normal GitHub versioning

- `outputs/`: generated runs and reports;
- `archive/`: recoverable superseded layouts and historical working copies;
- `.venv-comparison/` or any other virtual environment;
- `__pycache__/`, `.pytest_cache/`, `*.pyc` and `*.egg-info/`;
- `scripts/node_modules/`: reinstallable JavaScript dependencies.

The three former root launcher folders are no longer active. Their small
wrappers are retained only under `archive/previous_layout/launchers/`; the
active replacements are in `runners/`.
