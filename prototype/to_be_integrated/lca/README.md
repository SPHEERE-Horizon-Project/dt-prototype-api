# Standalone LCA module

This folder contains an independent Python translation and a formula workbook for embodied impacts and the selected pre-retrofit comparison block in `energy_model/outputs/revised_energy_model.xlsx`, worksheet `ENERGY MODEL-DSS`, rows 565–600. The original primary-energy and carbon outputs are preserved. The embodied-impact engine now accepts any number of indicator definitions, calculates every indicator for every technology, and aggregates complete indicators at building level. This module does not call the DT-Prototype thermal solvers.

## Run

From this folder, run `python run_lca.py --input benchmark_case.json --output results` (or run the script with `--help`). To load the complete Level(s)/EN 15804 indicator registry, add `--indicator-catalog indicator_catalog.json`. The CLI writes JSON results, a long-form technology-by-indicator CSV and a source/input hash manifest. Use a fresh output directory. The benchmark is Design option 1; Lyon, extracted from the source workbook's saved values.

Run the independent checks from this folder with `python -m unittest discover -s tests -v`.

`lca_calculation.xlsx` is the verification workbook. Edit amber input cells on `Inputs`, follow formula steps on `Calculation`, and compare the live outputs with the frozen source reference in the final check block.

## Calculation scope, units and limitations

For each technology and indicator, the model calculates installations as `ROUNDUP(project lifetime / service life, 0)`, annual embodied impacts as factor × size / service life, project impacts as factor × size × installations, and residual lifetime as service life × installations − project lifetime. `size` is the assessed quantity and may be made explicit as `base_size × sizing_factor`; `sizing_basis` records why that factor was selected. A factor of `1.0` preserves the workbook benchmark. Renovation indicator factors are multiplied by conditioned floor area. A building result is deliberately unavailable when a non-zero item or renovation factor is missing, so incomplete coverage cannot appear as a valid zero.

Energy and carbon factors must match the quantity unit: for example, kWh/m² with m², or kWh/unit with unit count. The source labels the renovation energy factor in `LCA settings!C2` as `kWh`, although the formula multiplies it by floor area. This module labels it kWh/m² as inferred from that formula and retains the original source label in the input metadata.

The source formula `ENERGY MODEL-DSS!T595` contains the text literal `"T553"` where a cell reference appears intended. The selected benchmark uses `electricity-no fuel`, so that branch returns zero; a fuel-fired DHW case produces an Excel value error. Python preserves and reports this source limitation rather than correcting it silently. Heating fuel lookup uses the included editable fuel factor table.

The JSON contract groups data into `project`, `indicator_definitions`, `renovation`, `electricity_factors`, `pre_retrofit`, `technologies`, and `fuel_factors`. Technology records carry stable asset/category identity and explicit sizing. The clarified assets are Heat pump system (three heat pumps), DHW heat pump, Water tank, BACS (Building Automation and Control Systems) and PV system (total installed kW). Each technology may provide an `indicator_factors` mapping keyed by stable indicator ID. Values may be numbers or `{value, unit}` objects; an explicit unit must match the definition. Legacy energy/carbon fields remain supported. See `INDICATORS.md` and `indicator_catalog.json` for the extension rules and Level(s) identifiers.

The locally named document `LCA indicators Levels selected` was not present in this workspace during this update. The catalog therefore uses the complete Level(s) Indicator 1.2 Table 6 set published by the European Commission/JRC. Once the selected local list is supplied, indicators can be enabled or removed in data without changing the calculation code.

## Provenance

Missing generic indicator factors may be omitted or expressed as JSON `null`.
For a zero-quantity asset, a missing factor contributes zero and does not block
the building total; the factor itself stays unknown. A non-zero asset with a
missing factor keeps its building indicator unavailable. An empty technology
list supports a renovation-only calculation and header-only detail CSV. CLI
detail retains asset IDs and sizing, and the manifest hashes an optional catalog
and the resolved inputs as well as the original JSON.

The DHW heat-pump benchmark preserves the original quantity 26 with per-unit
factors. It is not automatically interpreted as 26 kW. A future external
capacity-based assessment must explicitly supply matching quantity units and
factors.

From the prototype root, `python scripts/verify_assessments.py` checks standalone
source outputs and saved workbook comparisons. The root pytest command includes
this module's tests.

Benchmark source SHA-256: `379531a7c90bffe7818db93393cf7333fefdad780146833de98a0cd4a490d3da`. The input JSON records source cells, source fuel factors, and cached reference outputs. `tests/test_benchmark.py` checks every exposed result against the frozen source reference using `abs(Python − Excel) <= 0.000001 + 0.000000001 × abs(Excel)`.
