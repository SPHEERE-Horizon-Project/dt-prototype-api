# DT-Prototype architecture and refactoring process

The process was: preserve sources and results; run the original suites; consolidate only duplicated infrastructure; expose independent entry points; rerun every benchmark option; compare numerical outputs; reissue current reports; archive superseded copies.

```text
configs/example*.json + data/examples/
                  |
    GeoJSON or normalized CSV adapter
                  |
          canonical geometry + common inputs
          /         |          \
 dynamic RC     monthly QSS    prepared monthly inputs
 5R1C/7R2C                        |
                         independent Model 3
          \         |          /
           common monthly/annual reporting
```

Model 3 now has one cohesive integration location:

```text
src/dt_prototype/integration/
    model3/                 complete simulation/calibration pipeline
        model3.py           preserved calculation source
        example_data/       standalone pipeline example
        reference_outputs/  immutable golden results
    engines/model3.py       common-result adapter
    mapping/                shared-input to Model 3 translation
    workflow.py             portfolio comparison orchestration
```

The adapter and mapping code are separate from the preserved calculation
module because they have different responsibilities, but both are now in the
same integration package. Normal simplified simulations import the embedded
Model 3 module directly; they do not locate or dynamically load a separate
`third_party` file. The stable `model3_legacy` result identifier is retained
only for compatibility with completed run manifests and comparison tables.

## Ownership

| Location | Responsibility |
|---|---|
| `src/dt_prototype/common/` | Input configuration, geometry, weather, envelopes, schedules, systems and constants |
| `src/dt_prototype/dynamic/` | Dynamic networks, zone/system execution, existing diagnostics and visualisation |
| `src/dt_prototype/monthly/` | One retained semi-stationary implementation and static parameterisation |
| `src/dt_prototype/integration/` | Mapping, Model 3 adapter, comparisons, weather audits and 5P reporting |
| `src/dt_prototype/integration/model3/` | Complete preserved Model 3 simulation/calibration pipeline and unmodified golden outputs |
| `runners/` | Three thin, independently executable engine launchers and one usage guide |
| `tests/` | Separate engine suites plus common-input and independent-execution checks |
| `outputs/` | Traceable run directories, never silently reused |

## Removed from the active tree

- The integration folder's duplicate monthly package.
- Duplicate preprocessing modules and constants in the monthly distribution.
- The dynamic folder's duplicate monthly heat-balance implementation; its compatibility route now uses the retained monthly solver.
- Per-tool copies of production weather, geometry, envelopes, schedules and systems.
- One duplicate five-building monthly regression and one skipped test depending on an unavailable external fixture.
- Old packaging, superseded instructions, notebooks with obsolete imports and historical result copies. Originals are retained under `archive/`.
- Three separate root launcher folders; their renamed scripts now live together under `runners/`.

The dynamic and monthly thermal calculations were not merged merely to force agreement. Model 3 remains a separate heat-balance implementation. Shared static parameterisation supplies the simplified tool with conductances, capacity, gains, weather and operations; it does not run either detailed heating/cooling solver. A test deliberately blocks both solvers and confirms that simplified execution succeeds.

Each launcher selects its own solver and uses the same configuration contract and manifest. GeoJSON and normalized CSV files both become the same canonical geometry before engine execution. No output from a previous tool run is required. The comparison workflow intentionally executes multiple engines, while the ordinary single-tool commands do not.

This distribution contains computation and command-line orchestration. Scientific changes, meter integration, complete schemas, an HTTP service, web interface and portfolio scaling remain separate work. See [development guidance](development.md).
