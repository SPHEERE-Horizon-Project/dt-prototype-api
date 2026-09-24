# Model 3 Methodology and Architecture

## 1. Design principles

1. One stable input schema for Excel and Python.
2. Monthly formulas remain visible and traceable in the workbook.
3. Repeated numerical work and calibration fitting belong in Python.
4. Optional features are gated by explicit binary inputs.
5. Assumptions and deferred physics are visible rather than hidden in formulas.

## 2. Calculation boundary

The model represents one conditioned zone per building and month. It predicts
useful heating, cooling, and DHW; converts them through technical systems; adds
auxiliary and lighting/appliance electricity; subtracts self-consumed PV; and
aggregates delivered energy by carrier.

### 2.1 Heat-transfer coefficients

`H_transmission = H_transmission_opaque + H_transmission_windows`

`H_ventilation = rho_air * cp_air / 3600 * [q_ve*(1-eta_HR) + q_inf]`

`H_total = H_transmission + H_ventilation + H_ground`

`H_ground` is a direct steady coefficient. This is the main deliberate
simplification from Model 2.

### 2.2 Thermal dynamics

The thermal capacity is selected from a mass-class lookup and multiplied by
conditioned floor area. The time constant and heating/cooling utilisation
exponents follow the monthly ISO 13790-style approach used in Model 2.

### 2.3 Gains and demand

Solar gains use five orientations (N, E, S, W, horizontal), a common glazing
g-value, shading factor, and frame fraction. Internal gains combine occupants
and the heat fraction of lighting/appliance electricity.

Useful heating and cooling are determined from heat transfer, gains, and the
gain/loss utilisation factors. DHW uses an exposed per-person daily rate.

## 3. Technical systems

The systems table is the operational routing definition. Each configuration
contains five services: primary and secondary heating, primary and secondary
DHW, and cooling. Each row assigns a carrier and an efficiency function.

| Configuration | Heating/DHW concept | Cooling |
|---|---|---|
| 1 | Gas boiler | Electric chiller |
| 2 | Electric heat pump | Reversible heat pump |
| 3 | Heat pump above bivalent temperature, gas backup below | Reversible heat pump |
| 4 | District heat | Split-system electricity |

The data-driven table is easier to extend than adding new workbook branches.

## 4. PV and solar thermal

`PV generation = enabled * peak_kWp * performance_ratio * irradiation`

PV first offsets gross monthly electricity. Any remainder is reported as
exported energy; it does not create negative delivered electricity.

`Solar thermal = min(DHW demand, enabled * collector area * efficiency * irradiation)`

This intentionally omits temperature-dependent collector curves, storage, and
distribution losses. The two modules remain visible and replaceable.

## 5. Inverse model and calibration

Python fits the five-parameter change-point equation per building and carrier:

`E_day = beta_base + beta_H*max(0,T_H-T_e) + beta_C*max(0,T_e-T_C)`

The two change points are profiled over a compact in-memory grid; the three
linear coefficients are solved analytically. No candidate grid is written to
Excel. The workbook stores only the fitted coefficients and uses them to show
monthly predictions and reconciliation.

NMBE and CV(RMSE) are reported per carrier. The default monthly thresholds are
±5% and 15%, retained from Model 2's reference interpretation. R² is reported
for the inverse fit. These metrics support calibration work but do not by
themselves establish formal standards compliance.

## 6. Conceptual flow network

| From | To | Flow | Operational implementation |
|---|---|---|---|
| Outdoor/ground | Zone | Transmission and ventilation losses | Forward heat-balance equations |
| Sun | Zone | Solar gains | Building windows + time-series irradiation |
| Occupants/equipment | Zone | Internal gains | Occupancy and operation inputs |
| Zone | Heating/cooling systems | Useful demand | Monthly demand calculation |
| Sun | DHW system | Solar-thermal contribution | Optional capped ST module |
| Systems | Energy carriers | Delivered energy | `systems.csv` carrier column |
| Sun/PV | Electricity balance | PV self-consumption/export | Optional PV module |
| Carriers | Primary energy/carbon | Factors | `factors.csv` |

This table documents the intended energy boundary. It is not an editable graph
that drives the solver; the operational source of truth is identified in the
last column.

## 7. Deferred scientific decisions

- Ground periodicity and floor-type-specific ISO 13370 coefficients.
- Physical interpretation of inverse slopes and change points.
- Location/year-specific primary energy and carbon factors.
- PV export credit and storage dispatch.
- Solar-thermal temperature correction and storage losses.
- Empirical validation across climates, use types, and system configurations.

