# Independent model runners

The three scripts in this folder select independent calculation engines from
the installed `dt_prototype` package. They share the same configuration and
input adapters; they do not share a heat-balance implementation.

Run them from the project root after installing the package:

```powershell
python runners/run_dynamic.py --config configs/example_tabular.json --output outputs/my_dynamic --model 5R1C
python runners/run_monthly.py --config configs/example_tabular.json --output outputs/my_monthly
python runners/run_simplified.py --config configs/example_tabular.json --output outputs/my_simplified --zone-mode sum
```

Replace `configs/example_tabular.json` with `configs/example.json` to use the
equivalent GeoJSON geometry input. Input paths resolve relative to the config
file. Every run requires a new output directory and writes a manifest,
monthly and annual common results, and engine-specific detail files.

The simplified `--zone-mode` options are:

- `sum`: solve each input zone independently and add the results;
- `collapsed`: use the **Simplified single-zone collapsed** representation by
  combining a two-zone building before one solve;
- `both`: retain both calculations in detailed output and use the zone sum in
  the common monthly and annual results.

The same entry points are also available through the package command:

```powershell
python -m dt_prototype dynamic --config configs/example_tabular.json --output outputs/my_dynamic
python -m dt_prototype monthly --config configs/example_tabular.json --output outputs/my_monthly
python -m dt_prototype simplified --config configs/example_tabular.json --output outputs/my_simplified
```
