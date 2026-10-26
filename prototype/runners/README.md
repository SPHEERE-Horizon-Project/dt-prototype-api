# Component runners

Each runner name matches its software component. Run commands from the project
root after installing the package. Each command requires a new output directory.

For setup and a complete sequence covering both execution modes, see
[the operational guide](../docs/running_forward_and_inverse.md). The current
[reliability implementation](../docs/reliability_improvements_20261023.md) identifies
verified behavior and remaining limits.

`run_preflight.py --config configs/pipeline_example.json` checks inputs without
solving/fitting; `--kind inverse` accepts an inverse configuration. See
[preflight instructions](../docs/input_preflight.md).
`run_measured_validation.py` assesses an existing inverse run against an explicit
holdout policy; see [measured-data validation](../docs/measured_data_validation.md).

`run_pipeline.py` adds optional orchestration around the existing energy and
Assessment workflows. Its separate JSON configuration defaults assessment to
disabled; enabled runs can select LCC/LCA/MCI, check an auto/direct inventory,
and join externally computed asset totals. It can reuse completed compatible
energy runs. See the [pipeline guide and commands](../docs/pipeline.md).
No standalone calculation backend is invoked.

`run_inverse_models.py --config configs/inverse_5p_example.json --output outputs/my_inverse`
fits or evaluates simulated/measured series through monthly 5P, OpenDSM billing,
or OpenDSM hourly backends. The pipeline also accepts `mode=inverse`, or optional
`analysis.enabled=true` after forward simulation. See the
[inverse-model guide](../docs/inverse_models.md) for contracts, isolated OpenDSM
setup, saved models, diagnostics and examples.

| Runner | Component | Main selector |
|---|---|---|
| `run_dynamic_rc.py` | `Dynamic_RC` | `--model 5R1C` or `--model 7R2C` |
| `run_monthly_ss.py` | `Monthly_SS` | semi-stationary monthly calculation |
| `run_monthly_ss_simplified.py` | `Monthly_SS_simplified` | `--zone-mode sum`, `collapsed`, or `both` |
| `run_monthly_ss_vbdd.py` | `Monthly_SS_VBDD` | `--solar direct` or `temperature_linear`; monthly or fixed utilisation |
| `run_energy_carriers.py` | `Energy_carriers` | run one named solver or all four with `--engine` |

The supporting `run_assessment.py` runner validates and aggregates externally
calculated LCC, LCA and MCI asset results. It may join annual operational results
from an `Energy_carriers` output directory, but it does not change any solver.

The supporting `run_asset_quantities.py` resolves auto/direct asset quantities
before the external assessment step. It accepts a data catalogue, JSON or Excel
quantity inputs, optional shared project inputs and a new output directory.
It keeps asset inventories independent of thermal-solver selection.

The runners share configuration and input preprocessing. They keep distinct
thermal equations. When `--energy-config` is supplied to a thermal runner, its
thermal results also pass through `Energy_carriers`.

```powershell
python runners/run_dynamic_rc.py --config configs/example_tabular.json --output outputs/Dynamic_RC --model 5R1C
python runners/run_monthly_ss.py --config configs/example_tabular.json --output outputs/Monthly_SS
python runners/run_monthly_ss_simplified.py --config configs/example_tabular.json --output outputs/Monthly_SS_simplified --zone-mode both
python runners/run_monthly_ss_vbdd.py --config configs/example_tabular.json --output outputs/Monthly_SS_VBDD
python runners/run_energy_carriers.py --config configs/example.json --energy-config configs/energy_example.json --engine all --output outputs/Energy_carriers
python runners/run_assessment.py --asset-results configs/asset_results_example.csv --energy-results outputs/Energy_carriers --output outputs/Assessment
python runners/run_asset_quantities.py --inputs configs/asset_quantities_example.json --catalogue configs/asset_catalogue.json --config configs/example.json --output outputs/asset_quantities
```

The same component names are available as selectors for the shared-energy
runner: `Dynamic_RC`, `Monthly_SS`, `Monthly_SS_simplified`, and
`Monthly_SS_VBDD`. The `all` selector runs all four thermal components through
`Energy_carriers`.

The cadastral input preprocessor is a separate utility, not a thermal solver:

```powershell
python runners/generate_cadastral_inputs.py --input data/raw/city.geojson --rules configs/city_archetype_rules.json --output data/processed/city/v001
```

See the [architecture diagram](../docs/architecture.md),
[shared carrier guide](../docs/shared_energy_layer.md),
[asset assessment integration](../docs/assessment_integration.md),
[workbook instructions](../docs/workbook_instructions.md) and
[data contract](../docs/data_contracts.md).
