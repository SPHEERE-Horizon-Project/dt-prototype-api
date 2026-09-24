# Retained methodology (DT-Prototype terminology)

Historical run paths below refer to archived evidence. Current commands are in the root README.

# Integrated Seasonal/AHU Building Energy Tool — Methodology

## Status and purpose

This document describes the formula-only workbook
`Integrated_Seasonal_AHU_Building_Energy_Tool.xlsx`. The workbook is a
transparent spreadsheet representation of the tested `seasonal_ahu`
comparison path in the integrated Python project. It reproduces monthly useful
sensible heating and cooling for the 13 supplied aggregate and individual-zone
cases.

The validated ISO 13790-style semi-stationary engine remains the scientific
reference. Exact agreement between this workbook and the integrated Python
implementation is **verification** of the spreadsheet translation. Differences
between the spreadsheet/Python result and the reference engine are
**cross-model verification** results; they are not empirical validation.

EPW processing is deliberately outside the workbook. The workbook starts from
monthly weather and operating inputs that have already been mapped by Python.

## 1. Provenance and calculation boundary

| Item | Recorded value |
|---|---|
| Tested source run | `20260810_stage4_seasonal_ahu_comparison_002` |
| Comparison mode | `seasonal_ahu` |
| Model 3 module SHA-256 | `d0d4add1770f3e21cb9ae178f4ce8d206554a2ec9da1b63c8e50b55373e26f9c` |
| Python implementation | `src/dt_prototype/integration/model3/model3.py` |
| Integration mapping | `src/dt_prototype.integration/mapping/reference_to_model3.py` |
| Integrated engines | `src/dt_prototype.integration/engines/` |
| Time step | Monthly |
| Thermal boundary | Single-zone sensible heat balance plus independent sensible AHU coil |
| Output boundary | Useful zone load + sensible AHU coil load |

The workbook contains only the physical comparison boundary exercised by the
completed Stage-4 run. It does not implement EPW aggregation, technical-system
or carrier conversion, DHW, auxiliaries, PV, solar thermal, primary energy,
carbon, measured-data calibration, or five-parameter regression.

## 2. Symbols and units

| Symbol | Workbook field | Meaning | Unit |
|---|---|---|---|
| \(A_f\) | `A_f_m2` | Conditioned floor area | m² |
| \(H_{tr}\) | `H_transmission_W_K` | Non-ground transmission coefficient | W/K |
| \(H_g\) | `H_ground_W_K` | Ground heat-transfer coefficient | W/K |
| \(q_{inf}\) | `q_direct_m3_h` | Infiltration plus non-AHU direct outdoor airflow | m³/h |
| \(q_{ve}\) | `q_ve_ahu_m3_h` | Mechanical airflow handled by the AHU | m³/h |
| \(\eta_{HR,eff}\) | `eta_HR_effective` | Equivalent external-air recovery efficiency | 0–1 |
| \(H_{inf}\) | `H_infiltration_W_K` | Direct-air heat-capacity rate | W/K |
| \(H_{ve,raw}\) | `H_ventilation_raw_W_K` | Raw AHU airflow heat-capacity rate | W/K |
| \(H_{ve,ext}\) | `H_ventilation_effective_W_K` | Effective external-air coefficient | W/K |
| \(C_m\) | `thermal_capacity_J_K` | Lumped zone thermal capacity | J/K |
| \(\tau\) | `time_constant_h` | Thermal time constant | h |
| \(a\) | `utilisation_exponent` | Monthly utilisation exponent | – |
| \(\theta_e\) | `outdoor_temp_C` | Monthly mean outdoor temperature | °C |
| \(\theta_H,\theta_C\) | `theta_H_C`, `theta_C_C` | Active heating/cooling setpoints | °C |
| \(f_H,f_C\) | operation fractions | Monthly heating/cooling availability | 0–1 |
| \(Q_{sol}\) | `aggregated_solar_gain_kWh` | Reference solar term, including opaque long-wave sky exchange | kWh |
| \(Q_{int}\) | `aggregated_internal_gain_kWh` | Aggregated reference internal gains | kWh |
| \(P_{gn}\) | `mapped_gain_power_W` | Mean power derived from \(Q_{sol}+Q_{int}\) | W |
| \(Q_{gn}\) | `total_gain_kWh` | Reconstructed monthly total gain | kWh |
| \(Q_{H,use}\) | `useful_heating_kWh` | Zone + AHU useful sensible heating | kWh |
| \(Q_{C,use}\) | `useful_cooling_kWh` | Zone + AHU useful sensible cooling | kWh |

All energy outputs use positive magnitudes. A signed AHU coil load is positive
for heating and negative for cooling before it is separated into the two
reported magnitudes.

## 3. Workbook architecture

The workbook follows the original spreadsheet tool's long-format,
formula-driven style and colour convention:

- amber cells: editable mapped inputs;
- blue cells: settings and lookups;
- no fill: calculated intermediates;
- green cells: outputs and comparison results.

| Sheet | Role |
|---|---|
| `README` | Scope, provenance, editing rules, and limitations |
| `Nomenclature` | Symbols, units, meanings, and Python anchors |
| `Settings_General` | Air properties, utilisation constants, and tolerance |
| `Settings_Mass` | Model 3 mass-class capacity lookup |
| `In_Cases` | One static input row per aggregate or individual-zone case |
| `In_Monthly` | One monthly input row per case |
| `Calc_Case` | Heat-transfer coefficients, capacity, time constant, exponent |
| `Calc_Monthly` | Seasonal zone balance, AHU segments, and totals |
| `Tested_Results` | Immutable Python and reference fixtures from the tested run |
| `Check_Reproduction` | Monthly spreadsheet-versus-Python reconciliation |
| `Out_Monthly` | Compact monthly outputs |
| `Out_Annual` | Annual totals and floor-area-specific results |
| `Comparison` | Annual reference-versus-spreadsheet table and chart |

## 4. Mapped inputs

### 4.1 Static case inputs

The integration adapter maps the reference case to Model 3 inputs without
altering either engine's heat-balance implementation:

- transmission and ground coefficients are copied from the reference result;
- reference thermal capacity per floor area is assigned to the nearest Model 3
  mass class;
- heating and cooling setpoints are area-weighted means of active reference
  setpoint schedules;
- infiltration and ventilation mass flow are converted to annual-mean volume
  flow using reference air density;
- airflow served by an AHU remains separate from direct airflow;
- sensible recovery, outdoor-air ratio, and supply temperatures are
  airflow-weighted;
- windows and solar apertures are zero in the mapped case because the already
  resolved reference solar and internal gains are supplied directly;
- system and environmental factors are neutral for this useful-load-only
  comparison.

For aggregate two-zone cases, the mapping combines selected zones into one
equivalent Model 3 zone. The validated reference still solves upper and lower
zones independently. Therefore aggregate results are classified
`APPROXIMATE`. Individual upper and lower cases are the scientifically
preferred comparison because they preserve the independent-zone boundary.

### 4.2 Monthly inputs

For every case and month, `In_Monthly` contains:

- number of calendar days;
- monthly mean outdoor temperature;
- aggregated reference solar gain (the reference `phi_sol` term, including
  opaque long-wave sky exchange);
- aggregated reference internal gain;
- formula-derived mapped mean gain power;
- heating operation fraction;
- cooling operation fraction.

The workbook visibly derives mapped gain power from the two imported gain
components:

\[
P_{gn,m} = \frac{1000\,(Q_{sol,m}+Q_{int,m})}{24\,d_m}
\]

It then reconstructs the comparison-model total gain:

\[
Q_{gn,m} = Q_{sol,m}+Q_{int,m}
\]

The operation fractions are area-weighted monthly means of hourly season
availability and active setpoint schedules. Each is constrained to \([0,1]\)
and their sum must not exceed 1.

## 5. Static heat-transfer and mass calculations

With air density \(\rho_a=1.2\,\mathrm{kg/m^3}\) and specific heat
\(c_{p,a}=1005\,\mathrm{J/(kg\,K)}\):

\[
H_{inf}=\frac{\rho_a c_{p,a} q_{inf}}{3600}
\]

\[
H_{ve,raw}=\frac{\rho_a c_{p,a} q_{ve}}{3600}
\]

\[
H_{ve,ext}=\frac{\rho_a c_{p,a}
\left[q_{ve}(1-\eta_{HR,eff})+q_{inf}\right]}{3600}
\]

\[
H_{tot}=H_{tr}+H_g+H_{ve,ext}
\]

For the selected mass class:

\[
C_m=c_{m,class} A_f
\]

\[
\tau=\frac{C_m}{3600H_{tot}}
\]

\[
a=a_0+\frac{\tau}{\tau_0}
\qquad a_0=1,\quad \tau_0=15\,\mathrm{h}
\]

## 6. Monthly zone heat balance

Let \(t_m=24d_m\). In the enhanced path, direct envelope/ground/infiltration
exchange remains connected to outdoor air while AHU ventilation is connected
to supply air. This prevents double counting the AHU external-air load.

### 6.1 Heating transfer and utilisation

\[
H_{direct}=H_{tr}+H_g+H_{inf}
\]

\[
Q_{H,ht} =
\frac{t_m f_H}{1000}
\left[
H_{direct}(\theta_H-\theta_e)
+H_{ve,raw}(\theta_H-\theta_{sup,H})
\right]
\]

If \(Q_{H,ht}\leq0\), zone heating is zero. Otherwise:

\[
\gamma_H=\frac{Q_{gn}}{Q_{H,ht}}
\]

\[
\eta_H =
\begin{cases}
\frac{a}{a+1}, & \gamma_H \approx 1\\
\frac{1-\gamma_H^a}{1-\gamma_H^{a+1}}, & \text{otherwise}
\end{cases}
\]

\[
Q_{H,zone}=\max(0,Q_{H,ht}-\eta_HQ_{gn})
\]

### 6.2 Cooling transfer and utilisation

\[
Q_{C,ht} =
\frac{t_m f_C}{1000}
\left[
H_{direct}(\theta_C-\theta_e)
+H_{ve,raw}(\theta_C-\theta_{sup,C})
\right]
\]

If \(f_C=0\), zone cooling is zero. Otherwise the enhanced implementation
guards \(Q_{C,ht}\) with a lower value of \(10^{-12}\) kWh and uses the
validated-reference ratio orientation:

\[
\gamma_C=\frac{Q_{gn}}{Q_{C,ht}}
\]

\[
\eta_C =
\begin{cases}
1, & \gamma_C<0\\
\frac{a}{a+1}, & \gamma_C \approx 1\\
\frac{1-\gamma_C^{-a}}{1-\gamma_C^{-(a+1)}}, & \text{otherwise}
\end{cases}
\]

\[
Q_{C,zone}=\max(0,Q_{gn}-\eta_CQ_{C,ht})
\]

The workbook reproduces this exact tested branch. It does not use the
reciprocal legacy cooling ratio retained in Python solely to protect historical
Model 3 reference outputs.

## 7. Independent sensible AHU calculation

For a segment with return temperature \(\theta_r\), supply temperature
\(\theta_s\), and monthly fraction \(f\):

\[
\theta_{rec}=\theta_e+\eta_{HR}(\theta_r-\theta_e)
\]

\[
\theta_{mix}=r_{oa}\theta_{rec}+(1-r_{oa})\theta_r
\]

\[
Q_{coil} =
\frac{H_{ve,raw}(\theta_s-\theta_{mix})t_mf}{1000}
\]

The workbook evaluates three independent segments:

1. heating segment: \(\theta_r=\theta_H\),
   \(\theta_s=\theta_{sup,H}\), fraction \(f_H\);
2. cooling segment: \(\theta_r=\theta_C\),
   \(\theta_s=\theta_{sup,C}\), fraction \(f_C\);
3. neutral segment: \(\theta_r=(\theta_H+\theta_C)/2\),
   \(\theta_s=\theta_{sup,C}\), fraction
   \(f_N=\max(0,1-f_H-f_C)\).

The useful AHU magnitudes are:

\[
Q_{AHU,H}=\sum_s\max(0,Q_{coil,s})
\]

\[
Q_{AHU,C}=\sum_s\max(0,-Q_{coil,s})
\]

Total useful sensible demand is:

\[
Q_{H,use}=Q_{H,zone}+Q_{AHU,H}
\]

\[
Q_{C,use}=Q_{C,zone}+Q_{AHU,C}
\]

## 8. Reproduction and audit procedure

1. Open `Check_Reproduction`.
2. Confirm that the overall status is `PASS`.
3. Inspect monthly component deltas: zone heating, AHU heating, total heating,
   zone cooling, AHU cooling, and total cooling.
4. The supplied tolerance is \(10^{-6}\) kWh per monthly component.
5. If amber inputs are changed, the spreadsheet outputs update but the golden
   Python fixtures remain fixed. A failed check then indicates an intentional
   scenario change or an inconsistent edit, not necessarily a formula defect.
6. To establish a new golden comparison, run the integrated Python workflow
   into a new immutable run directory and replace fixtures only with recorded
   provenance and input hashes.

## 9. Verified reproduction result

The generated workbook was evaluated over:

- 13 cases;
- 12 months per case;
- 156 case-month records;
- one total-gain component and six demand components per record.

The maximum absolute spreadsheet-versus-Python difference is:

| Quantity | Maximum absolute difference |
|---|---:|
| Total gain | 0.000000000029 kWh/month |
| Heating components and total | 0.000000000031 kWh/month |
| Cooling components and total | 0.000000000015 kWh/month |
| Required tolerance | 0.000001000 kWh/month |
| Overall status | **PASS** |

No spreadsheet formula error values were found during workbook inspection.
Every sheet was rendered and visually checked after export.

## 10. Cross-model verification summary

The following annual values compare the formula-equivalent
spreadsheet/Python result with the validated semi-stationary reference.

| Case | Heating difference | Cooling difference | Classification |
|---|---:|---:|---|
| Test building 1 — aggregate | -7.3% | -7.2% | APPROXIMATE — independent zones collapsed |
| Test building 1 — lower | -2.3% | -3.8% | APPROXIMATE — monthly/annual mapping assumptions |
| Test building 1 — upper | -0.8% | -4.7% | APPROXIMATE — monthly/annual mapping assumptions |
| Test building 2 — aggregate | -7.1% | -5.4% | APPROXIMATE — independent zones collapsed |
| Test building 2 — lower | -0.6% | -1.9% | APPROXIMATE — monthly/annual mapping assumptions |
| Test building 2 — upper | -0.1% | +4.2% | APPROXIMATE — monthly/annual mapping assumptions |
| Test building 3 — aggregate | -4.5% | -5.7% | APPROXIMATE — independent zones collapsed |
| Test building 3 — lower | -1.4% | -3.0% | APPROXIMATE — monthly/annual mapping assumptions |
| Test building 3 — upper | -0.8% | +4.4% | APPROXIMATE — monthly/annual mapping assumptions |
| Test building 4 — aggregate | -1.2% | -6.4% | APPROXIMATE — independent zones collapsed |
| Test building 4 — lower | -0.5% | -11.3% | APPROXIMATE — monthly/annual mapping assumptions |
| Test building 4 — upper | -0.9% | -6.4% | APPROXIMATE — monthly/annual mapping assumptions |
| Test building 5 — aggregate | -0.8% | -5.5% | APPROXIMATE — monthly/annual mapping assumptions |

The seasonal mask and independent AHU treatment explain the large improvement
previously observed for Test building 1 lower, Test building 2 lower, Test building 3 lower, and Test building 4
lower. Residual differences remain because monthly averages, annual-mean
airflow mapping, nearest mass-class mapping, constant active setpoints, and
prescribed aggregate gains are deliberate approximations.

## 11. Limitations and safe extension

- The workbook accepts monthly inputs; it neither reads nor independently
  verifies EPW records.
- It reproduces the tested comparison cases, not every option in the wider
  Model 3 portfolio engine.
- Aggregate two-zone rows are useful diagnostics but should not replace the
  individual-zone comparisons.
- The AHU calculation is sensible only; latent loads and humidity are outside
  scope.
- Airflow is represented by annual means and AHU weather by monthly means.
- Thermal mass is represented by the nearest supported Model 3 mass class.
- Solar and internal gains are imported as separately aggregated reference
  quantities. The workbook makes their sum and the mapped mean gain power
  visible, but it does not independently rebuild them from raw geometry,
  schedules, or EPW irradiance.
- Calibration and 5P regression should remain in tested Python modules until
  their scientific decisions, carrier boundaries, bounds, and data split are
  fully documented. A future spreadsheet extension should consume their
  outputs, not silently invent a second fitting algorithm.

## 12. Python implementation anchors

The main equation anchors are:

- `src/dt_prototype/integration/model3/model3.py::ventilation_htc`;
- `src/dt_prototype/integration/model3/model3.py::utilisation_factor_heating`;
- `src/dt_prototype/integration/model3/model3.py::utilisation_factor_cooling`;
- `src/dt_prototype/integration/model3/model3.py::_fraction`;
- `src/dt_prototype/integration/model3/model3.py::building_coefficients`;
- `src/dt_prototype/integration/model3/model3.py::_ahu_sensible_demand`;
- `src/dt_prototype/integration/model3/model3.py::monthly_demand`;
- `src/dt_prototype.integration/mapping/reference_to_model3.py::_monthly_operation_fractions`;
- `src/dt_prototype.integration/mapping/reference_to_model3.py::_enhanced_airflow_mapping`;
- `src/dt_prototype.integration/mapping/reference_to_model3.py::write_reference_case_as_model3_inputs`.

These anchors, the source-run identifier, and the recorded module hash form the
minimum audit trail for the supplied workbook.
