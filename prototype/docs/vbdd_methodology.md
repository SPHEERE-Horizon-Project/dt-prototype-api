# Monthly_SS_VBDD v2: method, interfaces and migration decisions

The thermal equations below remain the Monthly_SS_VBDD core. The optional
[shared energy layer](shared_energy_layer.md) applies systems, renewables and
carrier impacts after it. The [current workbook editions](workbook_instructions.md)
extend the original thermal workbook through that boundary. The equations below
document the retained thermal core and its current verification boundary.

## Purpose and continuity

`src/dt_prototype/monthly_ss_vbdd` is the new thermal-demand component of `energy_model`.
It consumes the prototype's shared geometry, envelope, schedules, weather and
operating seasons. It complements `monthly` and `integration`; neither existing
solver is changed. The complete spreadsheet-preserving v1 package remains in
the parent `energy_model` directory as an auditable legacy implementation.
Physical equality between related methods is distinguished from independent
physical validation throughout the outputs.

The calculation boundary is useful **sensible** demand. Positive heating and
cooling magnitudes are reported separately for the thermal zone and AHU coil,
then added. There is no latent load, plant efficiency, fuel, electricity, DHW,
renewable generation, cost or embodied impact in this version. Zones are
independent and adiabatically separated, matching the supplied reference cases.

## Literature and formula reconciliation

Sources supplied in `Literature`:

- Tronchin, Manfren and Nastasi, *Energy analytics for supporting built
  environment decarbonisation*, Energy Procedia 157 (2019), 1486–1493,
  DOI 10.1016/j.egypro.2018.11.313. Page 1488 equations 3–9 define the heat balance
  and temperature/solar relation. Page 1489 tables 2–3 define the signatures.
- *D4.1 - Regression model_formulas_in progress nomenclature.docx*, the more
  detailed draft. Repeated formatted versions describe the same equations;
  they are not additional model terms.
- Original workbook `ENERGY MODEL-DSS` rows 140–167 and 173–219. Rows 162–167
  are the direct lineage for the physics signature coefficients.

The draft's expanded heating-slope expression is inconsistent with its own
coefficient table. Substitution gives **a1 = −(Hh + eta_h e1)**, consistent with
the published paper and original workbook T163. This sign is used explicitly.
The draft's occasional uppercase Q in a power equation and heating solar
subscript in a cooling equation are treated as notation issues. The model
uses one dimensioned equation per physical quantity, rather than duplicating
typographical variants. No calibration tolerances are inferred from the paper.

## Monthly input contract

`MonthlyInput` is a frozen, validated dataclass. One record is one case/month.
IDs and `representation` distinguish a zone, native single zone or collapsed
case. `period_id` is YYYY-MM; `days` must match the calendar. Temperatures are °C,
heat-transfer coefficients W/K, offsets and gains monthly-average W, capacity
J/K, and AHU energies kWh/month. Missing required values are errors. Zero gains
and disabled conditioning are valid. Net solar may be negative because the
shared surface model includes opaque longwave losses.

The adapter builds static UA, capacity and surface gains with the shared
`Monthly_SS.simulation.models.Model5R1C`, which has no forward thermal solver.
It does **not** read predicted `Monthly_SS`/`Monthly_SS_simplified` heating, cooling or fitted regression
outputs. The shared `_ahu_sensible_balance` supplies the same declared coil
and supply-air convention, including recovery and recirculation.

For each heating or cooling mode, the hourly input schedules are reduced to:

    L = H (Ti − Tm) + o                  [W, averaged over the calendar month]
    H = UA × mean(active) + mean(Hdirect × active)

`Hdirect` includes infiltration and ventilation that directly sees outdoor air.
The offset `o` retains the difference between the exact scheduled ventilation
input moment and Hdirect × (Ti − Tm), including AHU supply temperature. Thus
temperature/flow covariance is not lost. Transmission follows the existing
monthly-mean-temperature convention. Heating and cooling availability are
separate. Default thresholds (>17°C heating, <27°C cooling) and explicit seasons
follow the retained monthly adapter. Gains are averaged over the full month,
as in QSS. **Do not multiply the resulting demand by an active-hours fraction
again.** No adjacent-month interpolation is used.

## Processing equations

Let G = internal + net solar average gains. Attenuation alpha first scales H and
o by (1 − alpha); the default alpha is zero. Fixed mode uses user-supplied eta.
Monthly mode uses:

    tau = C / (3600 H_tau)               [h]
    a = 1 + tau / 15
    gamma_h = clip(G / Lh, 1e−9, 1e5)
    gamma_c = clip(G / Lc, 1e−9, 1e15)
    eta_h = (1 − gamma_h^a) / (1 − gamma_h^(a+1))
    eta_c = (1 − gamma_c^(−a)) / (1 − gamma_c^(−a−1))

At gamma=1, eta=a/(a+1). A reciprocal evaluation avoids numerical overflow.
In monthly mode, L is bounded below at the retained QSS value of 1e−5 J/month,
converted to average W. The corresponding offset correction preserves the
degree-day identity. `H_tau` is UA plus the maximum external-air coefficient
over the year, matching retained QSS. It is not the schedule-reduced H above.

    Tb,h = Th + (oh − eta_h G) / Hh
    Tb,c = Tc + (oc − G / eta_c) / Hc
    DDh = days × max(Tb,h − Tm, 0)
    DDc = days × max(Tm − Tb,c, 0)
    Qzone,h = Hh × DDh × 24 / 1000       [kWh]
    Qzone,c = eta_c Hc × DDc × 24 / 1000 [kWh]

Disabled modes have zero degree days and zero zone demand. A zero H gives an
unavailable balance temperature; enabling a mode with zero H is rejected.
AHU heating/cooling is bucketed by sign **before** hourly/monthly and zone
aggregation. It remains a separate output and is unchanged by zone utilisation.
Average monthly total power is (Qzone,h + Qzone,c + Qahu,h + Qahu,c)/(24 days).

Direct-solar monthly-factor Monthly_SS_VBDD and QSS are the same algebra when supplied
the same inputs. Their numerical equality is a strong implementation check,
but must not be described as evidence from an independent physics model.

## Fixed-factor physics signatures

For qsolar = e0 + e1 Tm and fixed internal gains, H, offsets and eta:

    a0 = [Hh Th + oh − eta_h(e0 + qint)]/1000
    a1 = −[Hh + eta_h e1]/1000
    c0 = [e0 + qint − eta_c(Hc Tc + oc)]/1000
    c1 = [e1 + eta_c Hc]/1000
    qh = max(a0 + a1 Tm, 0)
    qc = max(c0 + c1 Tm, 0)

Interceptions are kW, slopes kW/K and breakpoints −a0/a1 and −c0/c1.
`signature.physics_coefficients` exposes these terms and flags unconventional
slope signs. Monthly schedules/gains may change these coefficients between
months. Consequently a real portfolio need not be exactly a five-parameter
curve. A constant-input analytic test recovers its known 18°C and 22°C
breakpoints and 1 kW/K slopes with the existing independent 5P fitter.

The original workbook uses empirical solar/internal utilisation and attenuation
lookups indexed by its own categorical schedules/control settings. Those
categories have no established mapping to the prototype's hourly schedules.
V2 therefore does not silently transplant or calibrate them. Fixed defaults
eta=1, alpha=0 are a declared steady-balance baseline, **not** the calibrated
parameters of the original spreadsheet. Fixed-mode cooling disagreement is
reported. The monthly-factor option supplies the QSS-continuity calculation.

## Weather preprocessing choices

1. **Default: EPW orientation integration.** Reuse the shared solar-position and
   isotropic-sky transposition. Integrate global/direct surface radiation over
   actual timestep hours, then aggregate N/E/S/W/horizontal kWh/m² and mean W/m².
   The shared surface model additionally uses all configured azimuth bins,
   glazing areas/g-values/frame/shading/diffuse factors, opaque absorptance and
   longwave exchange. The five-orientation export is a review view, not a
   restriction of the envelope model to four facades.
2. **Monthly multipliers.** `orientation_multipliers` exports POA/horizontal
   energy ratios. Multiply matching monthly horizontal irradiation by these
   ratios before applying effective apertures. Zero horizontal energy returns
   an unavailable ratio, not zero. Ratios describe this climate and month;
   reusing them at another site needs justification. They are supplied as a
   preprocessing interface, not an additional demand variant in this run.
3. **Temperature-linear option.** Fit each case's net monthly solar W to Tm
   using only weather and envelope inputs. The processor substitutes e0+e1 Tm.
   CSV diagnostics expose fit range, residual RMSE and R². Keep negative net
   gains when produced by the longwave term. Refit after climate, glazing,
   shading or orientation changes. The current implementation fits all twelve
   months; season-specific fits or monthly orientation modifiers are possible
   extensions when sufficient climate data are supplied. They are not fitted
   here on too few cooling months merely to improve agreement.

Hourly geometry/orientation and AHU preprocessing is outside the verification
workbook's input boundary. The workbook explicitly labels prepared H/offsets,
net solar and AHU energies as inputs. It verifies the complete thermal Monthly_SS_VBDD
processing equations from that boundary, rather than claiming an Excel EPW
processor. Weather integration/conservation is covered by Python tests.

## Multi-zone and collapsed cases

Independent zones are solved and summed. The collapsed alternative sums
capacity, gains, H and offsets **before** utilisation. Setpoints are area-weighted
and each offset receives H_i(T_i − Tcollapsed), preserving the original summed
loss moment exactly. H_tau is the sum of each zone's UA + annual maximum external
coefficient (explicit approximation for noncoincident maxima). Shared AHU
energies remain sums of the physical zone AHUs; collapsing the thermal zone
does not invent a new shared air-handling system.

This collapse is more conservative than `Monthly_SS_simplified`'s historical annual-mean airflow and
nearest-capacity-class mapping. Differences in collapsed results are expected.
QSS's independent-zone sum is used as the comparison reference and labelled as
such, not misrepresented as a QSS collapsed solve. Test building 5 is native
single-zone, with no dummy zone. Never sum every row of the alternative-case
table into a portfolio total.

## Verification and deliverables

The supplied `comparison_report.md` remains unmodified. Fresh QSS and seasonal
AHU Model 3 executions reproduce its 30 annual values within 0.00501 MWh (the
report displays 0.01 MWh). Historical dynamic figures are retained separately
with that precision; their underlying hourly results were not supplied/rerun.
The new comparison exports all individual, independent-sum and collapsed
results plus case plots and numeric 5P fits. Residuals in 5P outputs are physics
minus fitted power. Cross-model differences are candidate minus QSS, with QSS
as the percentage denominator. Fit flags and missing-regime warnings are kept.
These are in-sample fits of 12 simulated months, not metered calibration tests.

The new workbook follows Model 3 styling (amber inputs, blue imported
references, green outputs). It contains all 156 entity/month rows, explicit
intermediates and 22 Python comparison quantities, switching among four
default utilisation/solar combinations. Native Excel verification changes
controls and inputs, recalculates and saves/reopens at the default. The approved
numerical tolerance is abs(error) ≤ 1e−6 + 1e−9 abs(reference), in each stated
unit. Text matches exactly. Python snapshots do not update when workbook inputs
change, so intentional differences remain visible.

The clean release retains the final recalculated workbook at
[`spreadsheets/DT_Prototype_Monthly_SS_VBDD_Energy.xlsx`](../spreadsheets/DT_Prototype_Monthly_SS_VBDD_Energy.xlsx)
and the complete native Excel evidence at
[`reports/workbooks/workbook_validation.md`](../reports/workbooks/workbook_validation.md).
Construction intermediates and one-off build tools remain in the user's backup.
Run `python scripts/verify_release.py` to verify the retained workbook identity
and saved formula-check state.

## Deliberate differences from the v1 spreadsheet

| Legacy feature | V2 decision |
| --- | --- |
| Cell-address evaluation and broad financial/services scope | Typed, semantic thermal module; legacy conversion preserved |
| Fixed February and global weekly operating fraction | Explicit calendar month plus shared hourly schedule moments |
| T150 cooling schedule refers to heating input T30 | Separate heating/cooling schedule mapping |
| Adjacent-month interpolation near base temperatures | Monthly-mean degree days; no invented submonthly distribution |
| Categorical empirical gain/attenuation factors | Declared fixed factors or independently calculated monthly factors |
| Original simplified weather/solar aperture regressions | Shared EPW/surface model, with optional transparent linear surrogate |
| Single spreadsheet design case | Typed independent-zone, native single-zone and conserved collapsed inputs |

These decisions define a new version. They are not claimed as bitwise
equivalence to the old spreadsheet. The original conversion and its historical
equivalence tests remain the evidence for that separate claim.
