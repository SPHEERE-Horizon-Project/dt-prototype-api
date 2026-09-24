# Model 3 — Lean Building-Energy Model and Calibration Tool

Model 3 combines Model 1's transparent table structure with Model 2's stronger
monthly physics, technical systems, validation, and Python pathway.

## What is included

- Monthly single-zone forward model with thermal-mass gain utilisation.
- Steady ground heat-transfer coefficient supplied per building.
- Four technical-system configurations with constant, linear, quadratic, or
  two-segment efficiency/COP functions.
- Heating, cooling, DHW, auxiliaries, lighting/appliances, carrier aggregation,
  primary energy, and operational carbon.
- Lean optional PV and solar-thermal calculations.
- Five-parameter change-point fitting in Python.
- Per-carrier NMBE, CV(RMSE), R², carrier-balance, and physical-bound checks.
- One shared CSV schema used by both the workbook builder and Python.

## Deliberately deferred

- The Excel inverse grid. The workbook consumes compact fitted coefficients;
  Python performs the numerical search.
- Detailed ISO 13370 periodic ground modelling. `H_ground_W_K` is an explicit,
  traceable input and can later be replaced by a dedicated ground module.
- Hourly/daily simulation, latent loads, multi-zone airflow, storage, tariffs,
  embodied carbon, and automated geometric extraction.

## Quick start

Run the embedded standard-library Python model from the project environment:

```powershell
python -m dt_prototype.integration.model3
python -m dt_prototype.integration.model3.test_model3
```

Python writes monthly, annual, calibration, and validation CSVs to the chosen
output directory. By default this is the package-local `outputs/python` path;
normal DT-Prototype runs provide their own immutable output directories.

## Workbook/Python responsibility boundary

| Capability | Workbook | Python |
|---|---:|---:|
| Edit project inputs and scenarios | Yes | Reads same schema |
| Monthly forward model | Yes | Yes |
| PV and solar thermal | Yes | Yes |
| Inspect formulas and reconcile outputs | Yes | Yes |
| Fit inverse change points | No | Yes |
| Batch portfolios and testing | Limited | Yes |
| Calibration metrics | Formula summary | Full output |

## Node and edge clarification

In Model 2, `Nodes` and `Edges` describe the energy-flow network: outdoor air,
zone, heating generator, electricity carrier, PV, and similar components are
nodes; heat or energy transfers between them are edges. They are useful for
explaining boundaries and checking that every flow has a destination.

However, Model 2's formulas do not dynamically execute that table as a graph;
the calculation logic is written separately in formulas and Python. Treating
the sheets as operational inputs would therefore create two sources of truth:
editing an edge could appear to change the model while changing no calculation.

Model 3 keeps the idea as a short architecture table in `METHODOLOGY.md`, not as
an editable workbook input. The actual operational routing is the long-format
`systems.csv` table plus explicit carrier aggregation in `model3.py`. If a
future graph solver is implemented, the network table can become operational
at that point.

## Scientific status

This is a transparent research/development tool, not a certified implementation
of ISO 13790, ISO 52016, ISO 13370, ASHRAE Guideline 14, or IPMVP. Replace all
synthetic factors and validate against real buildings before decision use.
