# Standalone LCC module

This folder contains an independent Python translation and a formula workbook for the investment and operation cost block in `energy_model/outputs/revised_energy_model.xlsx`, worksheet `ENERGY MODEL-DSS`, rows 506–564. It consumes renovation assumptions, technology cost/size/lifetime/replacement/maintenance data, and annual imported/exported electricity plus baseline bills. It does not call the DT-Prototype thermal solvers.

## Run

From this folder, run `python run_lcc.py --input benchmark_case.json --output results` (or run the script with `--help`). The CLI writes JSON results, per-technology CSV detail and a source/input hash manifest. Use a fresh output directory. The benchmark is Design option 1; Lyon, extracted from the source workbook's saved values.

`lcc_calculation.xlsx` is a verification workbook: edit the amber cells on `Inputs`, follow the formula build on `Calculation`, and inspect the frozen source-output comparisons at the bottom. Blue text marks editable assumptions, green text linked/input references, and black text formulas.

## Calculation scope and inputs

The model annualizes electricity import/export prices and maintenance costs using the source's real discount rate and escalation annuity factors. It calculates initial investment, replacement present value, residual value, demolition cost, maintenance, global cost and per-floor-area outputs. It uses the selected block's annual net electricity quantities and baseline electricity/fuel bills as inputs; fuel inflation is present in the source input row 512 but is not referenced by formulas in this block. The energy-carrier and thermal demand calculations remain outside this module.

Technology cost, size and their units must be compatible. The benchmark uses €/m² × m² for envelope measures and €/unit × units or €/kW × kW for equipment. The explicit sizing fields are `base_size`, `sizing_factor`, `size` and `sizing_basis`, with `size = base_size × sizing_factor`. Use a factor of `1.0` when no allowance or oversizing applies. The result detail exports all four fields for review. Legacy inputs containing only `size` remain valid and imply a factor of `1.0`. Project and component lifetimes must be positive. The source row 533 has no equal-rate branch: when its escalation/discount base is exactly 1, Excel divides by zero; Python reports that condition explicitly.

The JSON contract has four input groups: `assumptions` (project life, rates, prices and demolition fraction), `renovation` (other installation cost, renovation area and net floor area), `annual_energy` (annual import/export kWh and baseline electricity/fuel bills), and `technologies` (stable asset/category identity, unit cost, explicit sizing, service life, replacement fraction and annual maintenance rate). Each technology's `cost_unit` and `size_unit` must describe compatible quantities. The clarified assets are Heat pump system (three heat pumps), DHW heat pump, Water tank, BACS (Building Automation and Control Systems) and PV system (total installed kW). Use `benchmark_case.json` as the complete field-level example; source cell references are included alongside benchmark technology values.

## Provenance

Rates used in discounting/escalation must be greater than -100%, and derived
assessed sizes must be finite. A renovation-only case may use an empty technology
list; its CLI exports a header-only technology table. The historical DHW heat
pump benchmark keeps the source quantity 26 and per-unit factors. This is a
retained test input, not an inferred kW capacity or an independently validated
device count. Capacity-based future inputs require compatible unit factors.

From the prototype root, `python scripts/verify_assessments.py` checks standalone
source outputs and saved workbook comparisons. The root pytest command includes
this module's tests.

Benchmark source SHA-256: `379531a7c90bffe7818db93393cf7333fefdad780146833de98a0cd4a490d3da`. The input JSON records source cells and cached reference outputs. `tests/test_benchmark.py` compares the translated output cells with that frozen reference using `abs(Python − Excel) <= 0.000001 + 0.000000001 × abs(Excel)`.
