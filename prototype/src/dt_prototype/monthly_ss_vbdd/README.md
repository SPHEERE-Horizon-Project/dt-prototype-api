# Monthly_SS_VBDD

`Monthly_SS_VBDD` calculates monthly sensible heating and cooling using
variable-base degree days derived from simplified semi-stationary balance
equations. It shares inputs with `Monthly_SS` and
`Monthly_SS_simplified`, while keeping its own solar and utilisation options.
The original `energy_model/src/vbdd_energy` remains the service/renewable/LCC/LCA
spreadsheet-equivalence reference.

From the prototype root:

```powershell
python runners/run_monthly_ss_vbdd.py --config configs/example.json --output outputs/vbdd_direct
python runners/run_monthly_ss_vbdd.py --config configs/example.json --solar temperature_linear --output outputs/vbdd_linear
python runners/run_monthly_ss_vbdd.py --config configs/example.json --utilisation fixed --output outputs/vbdd_fixed
python runners/run_energy_carriers.py --config configs/example.json --energy-config configs/energy_example.json --engine Monthly_SS_VBDD --output outputs/vbdd_energy
```

Output directories must be new. `python -m
dt_prototype.monthly_ss_vbdd.cli` is also available after installation. Use the
shared `--energy-config` option when systems, carriers, renewables and meter
balances are required. See the [shared energy guide](../../../docs/shared_energy_layer.md)
and [workbook instructions](../../../docs/workbook_instructions.md).

The component writes monthly balance temperatures, degree days, utilisation
factors, zone/AHU demands, average monthly power and a manifest with input and
code hashes. Its verification workbook is
[`DT_Prototype_Monthly_SS_VBDD_Energy.xlsx`](../../../spreadsheets/DT_Prototype_Monthly_SS_VBDD_Energy.xlsx).
For equations and the three collapsed approaches, see
[`vbdd_methodology.md`](../../../docs/vbdd_methodology.md) and
[`vbdd_three_collapsed_approaches.md`](../../../docs/vbdd_three_collapsed_approaches.md).
