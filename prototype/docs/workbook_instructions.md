# Monthly thermal and shared-energy verification workbooks

> Lean GitHub distribution: monthly reference fixtures and selected summaries are included. For the complete hourly/Excel evidence and strict 318-table reproduction, follow [validation archive instructions](validation_archive.md).

The optional [inverse-model layer](inverse_models.md) consumes exported interval
energy and weather after simulation. Existing verification workbooks and their
thermal, carrier and renewable formulas are unchanged. Statistical fitted values
and residuals are delivered as CSVs/figures, with model artifacts and diagnostics;
they are not inserted into the physical calculation sheets or used to alter
their frozen reference values.

The current editions are in [spreadsheets](../spreadsheets/). They extend the thermal verification to building systems, carriers, renewables, primary energy, carbon and energy cost. The final simplified and Monthly_SS_VBDD editions contain the preserved thermal sheets together with the new shared-energy sheets.

| Workbook | Thermal calculation | Representations / monthly rows |
|---|---|---|
| [Monthly_SS + energy](../spreadsheets/DT_Prototype_Monthly_SS_Energy.xlsx) | Direct semi-stationary loss/gain balance, prepared monthly moments | Four independent two-zone buildings plus one native single-zone building; 108 thermal zone-months → 60 building-months |
| [Monthly_SS_simplified + energy](../spreadsheets/DT_Prototype_Monthly_SS_simplified_Energy.xlsx) | Simplified semi-stationary seasonal-AHU formulas, historically called Model 3 | Original 156 thermal case-months; independent-zone sum/native single zone and four collapsed alternatives → 108 building-months |
| [Monthly_SS_VBDD + energy](../spreadsheets/DT_Prototype_Monthly_SS_VBDD_Energy.xlsx) | Retained Monthly_SS_VBDD formulas with live variant controls | Original 156 thermal case-months; 108 building-months per selected variant; monthly, linear and fixed energy references |

The calculation boundary is **useful sensible zone demand plus separate net sensible AHU demand**, followed by shared systems and a building electricity meter. There is no collapsed QSS implementation in this delivery. Dynamic results are compared in the [Python validation report](../reports/shared_energy/comparison_report.md); these workbooks do not claim to reproduce a dynamic time integration.

The optional geometry `boundary_condition=adiabatic` is processed in Python
before these workbooks' monthly inputs are prepared. It changes transmission,
ground terms and thermal gains while retaining the physical construction and
its appropriate capacity representation. The current workbooks do not parse
raw surface geometry or this new column. To verify a new subset, prepare its
monthly inputs and create a separately labelled verification case/reference;
do not edit the frozen baseline or treat the new geometry as already verified.
The existing baseline workbooks and formulas are unchanged. See
[adiabatic boundary instructions](adiabatic_boundaries.md).

## Open, inspect and change a scenario

1. Open the desired current workbook in Excel with automatic calculation enabled. Start at `Energy_Annual`; use `Energy_Monthly` for period detail. No macro, network connection or external workbook refresh is needed.
2. Select the representation explicitly. A collapsed result is an alternative to the corresponding independent-zone sum. Never sum both into a building or portfolio total.
3. Trace demand through `Energy_Inputs` and conversion through `Energy_Services`. Original simplified/VB thermal input sheets remain editable. New energy sheets link their live thermal outputs, not frozen Python predictions.
4. Change amber assumptions on `Energy_Technologies`, service assignments in `Energy_Services!C`, monthly inputs/matching assumptions on `Energy_Inputs!J:R`, or factors on `Energy_Factors!C:J`. Retain ID/period keys and row ordering. These are fixed-layout verification workbooks; to add buildings, months, technologies or carriers, update the Python dataset/configuration and regenerate the workbook layout.
5. For Monthly_SS_VBDD, set `Settings!B5:B6` to `(1,0)` for monthly direct, `(1,1)` for temperature-linear solar, or `(0,0)` for fixed utilisation/direct solar. `(0,1)` retains the older fixed-linear thermal option but has no shared-energy reference in this run; the energy audit deliberately shows `#N/A` rather than pretending to verify it.
6. Inspect `Energy_Check`. Unmodified baseline rows must say `PASS`. A legitimate input edit should produce `DIFFERENCE` from the frozen reference. An invalid input produces an explicit status/error, not a substituted zero. Restore inputs or regenerate a separately validated reference before interpreting a changed scenario as verified.

The original thermal sheets retain their historical instructions and reference values. Their thermal-only scope notes describe that earlier edition. `Energy_Guide` and this document define the extended edition.

## Sheet and field map

| Sheet / cells | Meaning and source |
|---|---|
| `Energy_Annual!A:J`, row 7 onward | Building, representation and eight summed carrier/meter/impact results; currency EUR in the supplied scenario |
| `Energy_Inputs!A:C` | Stable building ID, representation, `YYYY-MM`; one unique composite key |
| `Energy_Inputs!D:E` | Full calendar hours and monthly mean outdoor °C, from the validated case `energy_inputs.csv` |
| `Energy_Inputs!F:I` | Formula links to zone heat, AHU heat, zone cool, AHU cool, all positive kWh |
| `Energy_Inputs!J:M` | Useful DHW, appliance electricity, fan electricity, base auxiliary electricity, kWh; common preprocessing |
| `Energy_Inputs!N:O` | Available PV AC generation and solar thermal heat at DHW generator bus, kWh; common weather/equipment preprocessing |
| `Energy_Inputs!P:R` | Monthly PV factor, named PV basis, monthly solar utilisation; explicit configuration inputs |
| `Energy_Inputs!S` | Owning input validation: numeric completeness, ranges, hours, unique composite key |
| `Energy_Technologies!A:B` | Technology ID and carrier |
| `Energy_Technologies!C:H` | Performance coefficients c0…c5 in ascending powers of °C |
| `Energy_Technologies!I:L` | Distribution, emission and regulation efficiencies; auxiliary electric kWh per generated kWh |
| `Energy_Technologies!M:Q` | Temperature domain, clip/error policy, source and input validation |
| `Energy_Factors!A:L` | Carrier/month, eight import/export factors/prices, source and validation; 48 rows for four carriers × twelve months |
| `Energy_Services!A:D` | Input-row link, service, editable technology ID, looked-up carrier; five services per building-month |
| `Energy_Services!E:I` | Useful energy, outdoor/evaluated temperature, performance and product of downstream efficiencies |
| `Energy_Services!J:P` | Required generator heat, used solar, remaining generator heat, delivered carrier energy, auxiliaries, downstream losses and conversion residual |
| `Energy_Services!Q:R` | Owning validation and exact technology lookup row |
| `Energy_Monthly!A:D` | Building, representation, period and current model identity |
| `Energy_Monthly!E:CK` | 85 formula-calculated quantities with exact Python field names; energy kWh, carbon kgCO2e, costs/credits EUR |
| `Energy_Reference` | Frozen values from `shared_energy_v1_validated/energy_monthly.csv`, grouped by scenario; audit input only |
| `Energy_Check` | Excel-minus-Python differences and tolerance status; terminal audit with no output dependencies |
| `Energy_Guide` | Embedded scope, source map, limits and instructions |

Original Model 3 fields and equations are documented in [spreadsheet methodology](spreadsheet_methodology.md). Original Monthly_SS_VBDD fields and equations are documented in [Monthly_SS_VBDD methodology](vbdd_methodology.md) and [the three variants](vbdd_three_collapsed_approaches.md). Their individual-zone thermal rows remain available. Zone service allocations and ancillary quantities are in the Python report's zone appendices; PV/import/export are building-meter quantities, not fabricated per-zone meters.

## Equations exposed in the new sheets

For service s and period m, let Q be useful demand, η the product of distribution, emission and regulation efficiencies, and p(T) the bounded performance curve. Then:

\[
Q_{req}=Q/\eta,\qquad p(T)=\sum_{j=0}^{5}c_jT_*^j.
\]

The declared policy either clips T to its domain or rejects out-of-domain values. Performance must be strictly positive. For DHW only, available solar heat A and monthly utilisation u give:

\[
S=u\min(Q_{req},A),\quad Q_{gen}=Q_{req}-S,\quad
E_{del}=Q_{gen}/p(T),\quad E_{aux}=a_{aux}Q_{gen}.
\]

Other services use S=0. Delivered service energies are assigned to their carriers. Gross electricity L additionally includes service auxiliaries, appliances, fans and base auxiliaries. Given PV AC production P:

\[
E_{self}=\begin{cases}
f\min(L,P),&\text{overlap basis},\\
\min(fP,L,P),&\text{generation basis},
\end{cases}\quad
E_{import}=L-E_{self},\quad E_{export}=P-E_{self}.
\]

Unused available solar heat is A−S. Imported energy times the carrier's period factor produces each import burden/cost. Electricity export times its separately declared export factor produces credits. Net primary energy, carbon and cost subtract those credits; physical imports of gas, district heat and other fuel remain unchanged.

`Energy_Monthly` exposes residuals for service allocation, solar heat, load, PV and meter balances. These are accounting identities, independent of agreement between thermal models.

### QSS formula boundary

`QSS_Inputs` stores monthly prepared zone moments, not predicted zone heating/cooling. `QSS_Calc` calculates gains G, heat-transfer powers Lh/Lc, a=1+C/(3600 Hτ × 15 h), the gain/loss ratios and their utilisation factors. The direct demands are:

\[
Q_h=h_m\max(0,L_h^+-\eta_hG)/1000,\qquad
Q_c=h_m\max(0,G-\eta_cL_c^+)/1000.
\]

Disabled services are zero. L+ retains the Python floor of 1e−5 J divided by month seconds. Ratios retain the QSS bounds; the unity limit follows `numpy.isclose(gamma,1)` with atol=1e−8 and rtol=1e−5. The reciprocal form is used where needed for numerical stability. These formulas are an independent Excel evaluation of the retained QSS algebra, not independent evidence that QSS physics is accurate. The prepared AHU sensible coil energies are integrated upstream and visibly imported.

## What must be regenerated

Weather, geometry, envelope, surface orientation, schedules, PV/ST equipment or airflow changes require rerunning preprocessing. Editing a thermal demand cell does not update DHW, fan/appliance schedules or renewable production. Monthly irradiation can support a PV production formula, but monthly average weather cannot exactly recover solar-thermal hourly clipping or dynamic load coincidence. This edition imports those explicitly labelled common production totals and reproduces conversion/matching downstream.

To refresh the delivered reference pack, first produce and audit a new shared-energy run with the same sensible boundary. Create a versioned workbook from the new prepared inputs and retain its new source map and expected values. Do not overwrite an accepted reference merely to hide differences.

The cleaned release retains the final workbooks and their native Excel evidence,
without the one-time construction intermediates. Verify the accepted artifacts
from the prototype root after the fresh run and audit steps in the
[operational guide](running_forward_and_inverse.md):

```powershell
python scripts/verify_release.py --energy-results outputs/my_forward/energy --expected-tests 506 --output outputs/my_checks/release.json
```

The retained evidence records how native Excel recalculated every variant,
exercised meaningful perturbations, restored the baseline, scanned errors and
saved/reopened the files. Normal Excel saving rewrites package XML, so semantic
formula/value, chart and validation checks supplemented the package-preservation
audit. Python runtime never reads workbook predictions or requires Excel.

The acceptance evidence is [workbook_validation.md](../reports/workbooks/workbook_validation.md), `native_excel_summary.json`, `native_excel_comparison.csv`, `preservation.json` and `workbook_manifest.json` in the same report folder. Use numeric tolerance 1e−6 + 1e−9 × |reference|; text/categories match exactly. Formula-length limits, error scans, lookup uniqueness and live input propagation are part of verification.

Current factors and prices are illustrative. Monthly mean performance is an approximation and generally differs from summing dynamic E/p(T). Polynomial positivity is validated over the complete domain in Python; Excel checks evaluated temperatures, so revalidate any edited curve with `EnergyConfig` before deployment. No ISO-standard matching conformance, measured-consumption accuracy, batteries, latent demand or gross AHU reheat is claimed.

## Standalone assessment companions

The optional [simulation pipeline](pipeline.md) consumes the existing external
whole-asset result CSV and optional resolved inventory; it does not execute
these standalone workbook/calculation engines. No formula changes are needed
in the monthly or standalone workbooks for the pipeline switch. Prepare/edit
quantities through the existing JSON/Excel quantity workflow, calculate asset
totals externally, and return them with matching identities/units. The new
matched CSV examples are orchestration fixtures, not revised Excel predictions.

LCC, LCA and Circularity workbooks remain under `to_be_integrated/`. LCC/LCA use
base quantity × sizing factor = assessed quantity. Their source benchmark keeps
the DHW heat-pump quantity as `unit`, with compatible per-unit factors; the prior
kW reinterpretation has been corrected. Changing to a capacity basis requires
explicit design inputs and compatible external factors. PV remains installed kW.

The [15 October audit](code_audit_20261015.md) changed five unit/note cells across
LCC/LCA, with no formula changes, retaining all 26 benchmark checks.
`python scripts/verify_assessments.py` checks saved workbook and Python results.
This audit used Artifact Tool recalculation, error scans and visual inspection;
it did not repeat native Excel automation. Earlier native Excel evidence for
the three monthly energy workbooks remains a separate unchanged record.
