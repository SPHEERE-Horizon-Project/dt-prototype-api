# Semi-stationary balance and three collapsed-zone Monthly_SS_VBDD approaches

For consumption after these thermal calculations, see the
[shared energy layer](shared_energy_layer.md). The [current Monthly_SS_VBDD energy workbook](workbook_instructions.md)
uses the same three selectors and adds service conversion, renewables, grid
exchange and impacts. The equations and historical thermal comparisons below
continue to describe useful demand, not delivered energy.

This guide explains the **useful sensible heating and cooling demand** calculated
by the Monthly_SS_VBDD v2 component. It connects the semi-stationary monthly balance in
the supplied [paper — development-only](validation_archive.md#local-development-material)
(p. 1488, equations 1–9; p. 1489, Tables 2–3) and the more detailed
[D4.1 draft — development-only](validation_archive.md#local-development-material)
(heat-balance equations 1–9 and regression tables) to the three **collapsed
single-zone** cases in the [accepted comparison](../reports/shared_energy/comparison_report.md).
The calculation described here is implemented in
[`Monthly_SS_VBDD/model.py`](../src/dt_prototype/monthly_ss_vbdd/model.py),
[`Monthly_SS_VBDD/preprocessing.py`](../src/dt_prototype/monthly_ss_vbdd/preprocessing.py), and
[`vbdd/weather.py`](../src/dt_prototype/monthly_ss_vbdd/weather.py).

## What the three names mean

| Name in this guide | Name in results | Monthly net solar gain | Gain/loss utilisation | Default attenuation |
| --- | --- | --- | --- | --- |
| **1. Monthly_SS_VBDD monthly collapsed** | `Monthly_SS_VBDD monthly direct` | Directly calculated from the EPW and envelope | Calculated each month from the monthly balance | 0 |
| **2. Monthly_SS_VBDD linear collapsed** | `Monthly_SS_VBDD monthly linear` | Replaced by a fitted linear function of monthly outdoor temperature | **Still calculated each month**, using the replaced solar gain | 0 |
| **3. Monthly_SS_VBDD fixed collapsed** | `Monthly_SS_VBDD fixed direct` | Same direct EPW/envelope gain as approach 1 | Fixed at `η_h = η_c = 1` in the reported run | 0 |

The word **linear** refers to the *solar-gain input*. It does not describe the
whole thermal-demand calculation: approach 2 still recalculates nonlinear
utilisation factors and balance temperatures each month. The word **fixed**
refers to the utilisation factors. Approach 3 does **not** use a linear solar
surrogate. The software can also combine fixed factors with linear solar gain;
that fourth combination is exported as `Monthly_SS_VBDD fixed linear`, but is not one of the
three cases compared here.

All three start from the same collapsed geometry, setpoints, heat-transfer
coefficients, schedules, internal gains, capacity and separate AHU calculation.
They change **only** the solar representation and/or utilisation rule shown
above. `Test building 5` has one physical zone and is therefore a native
single-zone case, not a collapsed two-zone case.

## 1. Semi-stationary monthly balance in the sources

The paper separates heat **sinks/losses** from heat **sources/gains**. In its
notation, with monthly duration `Δt`, indoor temperature `θ_i`, outdoor
temperature `θ_e`, and heat-transfer coefficient `H = H_tr + H_ve`, the
conceptual sensible-demand balances are

$$
Q_{h,\mathrm{nd}}=
\max\!\left[0,\ H_h(\theta_{i,h}-\theta_e)\Delta t
-\eta_h\bigl(Q_{\mathrm{sol},h}+Q_{\mathrm{int}}\bigr)\right],
$$

$$
Q_{c,\mathrm{nd}}=
\max\!\left[0,\ Q_{\mathrm{sol},c}+Q_{\mathrm{int}}
-\eta_c H_c(\theta_{i,c}-\theta_e)\Delta t\right].
$$

Here `η_h` is the fraction of gains useful in offsetting heating losses;
`η_c` is the fraction of heat losses useful in offsetting cooling gains.
The zero bound and the distinction between heating and cooling setpoints are
made explicit in the software. The draft gives the transmission decomposition
`H_tr = Σ U_i A_i + Σ ψ_j l_j + Σ χ_k`. Its ventilation term is based on air
density, heat capacity, air-change rate and volume; the units of the air-change
rate must be converted consistently to seconds when calculating W/K. The
prototype supplies these physical quantities from its shared building and
weather preprocessing; they are not newly estimated from the comparison
targets.

Dividing monthly energy by its hours yields an **average power**. For a
calendar month of `d` days, `Δt = 24d` hours and

$$
\bar q_{h,c}\,[\mathrm{kW}]
=\frac{Q_{h,c}\,[\mathrm{kWh}]}{24d}.
$$

This calendar-hour basis is also used for the later 5P energy-signature
comparison. Active operating schedules have already been incorporated into
the monthly heat-loss inputs below. Multiplying the finished demand by the
operating fraction again would count the schedule twice.

### The implemented input boundary

The v2 processor expresses each month's heating and cooling heat-loss powers
in **watts**, averaged over the *full* month:

$$
L_h=H_h(\theta_h-\bar\theta_e)+o_h,\qquad
L_c=H_c(\theta_c-\bar\theta_e)+o_c,\qquad
G=q_{\mathrm{int}}+q_{\mathrm{sol}}.
$$

`H_h` and `H_c` (W/K) already include the corresponding heating/cooling
availability fractions. The offsets `o_h` and `o_c` (W) preserve scheduled
ventilation and AHU supply-temperature effects that cannot be represented by
one simple `H × (setpoint − monthly temperature)` term. `G` is the full-month
average of internal plus *net* solar gains (W). Net solar may include a negative
longwave term on opaque surfaces. These definitions retain the common
heat-balance structure of the paper while making the prototype's schedule and
AHU boundary explicit.

For clarity, let `m_h(t)` be 1 when heating is intended and available at an
hourly input step, and 0 otherwise; let angle brackets denote a full-month
average. The heating adapter calculates

$$
H_h=UA\,\langle m_h\rangle
+\langle m_h H_{\mathrm{direct}}\rangle,
$$

where `H_direct` contains infiltration and any ventilation that directly sees
outdoor air. It calculates the complete scheduled heating loss using outdoor
and AHU supply temperatures, then defines `o_h` as that loss less
`H_h(θ_h − θ̄_e)`. Cooling is handled in the same way with its own schedule.
Thus the offset preserves the month-average supply-air/temperature moments;
it is **not** an extra heat gain to be added again. The AHU's sensible coil
energy is separately signed and bucketed before monthly aggregation.

## 2. From the balance to variable-base degree days

For each month and case, the model calculates gain/loss utilisation factors
`η_h,m` and `η_c,m`, or takes declared fixed values. The monthly *zone*
demands have the same balance form as the semi-stationary equations:

$$
Q_{\mathrm{zone},h}
=\frac{24d}{1000}\max(0,\ L_h-\eta_hG),\qquad
Q_{\mathrm{zone},c}
=\frac{24d}{1000}\max(0,\ G-\eta_cL_c)
\quad[\mathrm{kWh}].
$$

The software applies these zone formulas only when the corresponding mode is
enabled. It also applies the retained QSS positive-loss floor in monthly-
utilisation mode; details appear below. With positive `H_h`, `H_c` and `η_c`,
the same equations can be rearranged into **variable balance temperatures**:

$$
\theta_{b,h}=\theta_h+\frac{o_h-\eta_hG}{H_h},\qquad
\theta_{b,c}=\theta_c+\frac{o_c-G/\eta_c}{H_c}.
$$

This gives the variable-base degree days (K·day)

$$
\mathrm{DD}_h=d\max(0,\theta_{b,h}-\bar\theta_e),\qquad
\mathrm{DD}_c=d\max(0,\bar\theta_e-\theta_{b,c}),
$$

and the equivalent monthly zone demands

$$
Q_{\mathrm{zone},h}=H_h\,\mathrm{DD}_h\frac{24}{1000},\qquad
Q_{\mathrm{zone},c}=\eta_cH_c\,\mathrm{DD}_c\frac{24}{1000}
\quad[\mathrm{kWh}].
$$

The base temperatures are **outputs of that month's balance**. They shift when
weather-dependent gains, utilisation, setpoints or schedules change. In a
disabled mode, the degree days and zone demand are zero and an undefined
balance temperature is reported as unavailable. Total useful sensible demand
adds the separately computed AHU coil:

$$
Q_{h,\mathrm{total}}=Q_{\mathrm{zone},h}+Q_{\mathrm{AHU},h},\qquad
Q_{c,\mathrm{total}}=Q_{\mathrm{zone},c}+Q_{\mathrm{AHU},c}.
$$

### Monthly utilisation in approaches 1 and 2

These two approaches follow the retained `Monthly_SS` gain/loss utilisation
rule. With thermal capacity `C` (J/K) and the documented external-air time-
constant coefficient `H_τ` (W/K),

$$
\tau=\frac{C}{3600H_\tau}\quad[\mathrm{h}],\qquad
a=1+\frac{\tau}{15\ \mathrm{h}}.
$$

Form a heating ratio `γ_h = G/L_h` and cooling ratio `γ_c = G/L_c` after
bounding each loss below by the retained QSS positive-loss floor of
`10^{-5}` J per month. For numerical consistency with QSS, the implemented
ratios are clipped to `[10^{-9}, 10^5]` for heating and `[10^{-9}, 10^15]` for
cooling. Then

$$
\eta_h=\frac{1-\gamma_h^a}{1-\gamma_h^{a+1}},\qquad
\eta_c=\frac{1-\gamma_c^{-a}}{1-\gamma_c^{-a-1}}.
$$

At `γ = 1`, the limiting value is `a/(a+1)`. The implementation uses stable
algebra near that limit and for extreme ratios. The loss floor is also
reflected in an offset correction before calculating the balance point. In
average-power units, for either mode `x`, this is

$$
\varepsilon_m=\frac{10^{-5}}{3600(24d)}\ \mathrm{W},\qquad
o_{x,\mathrm{eff}}=o_x+\max(\varepsilon_m,L_x)-L_x.
$$

Using `o_eff` instead of `o` in the balance-temperature equations makes the
degree-day calculation algebraically equal to the bounded semi-stationary
balance. Fixed-factor mode retains the unadjusted offset.
The three reported default cases use **zero** heat-transfer attenuation.

## 3. What is collapsed, and when

The first four test buildings each have two independent zones. For the
collapsed alternative, the adapter makes one equivalent zone **before**
applying the nonlinear utilisation and zero-bound operations. For heating
or cooling mode `x`, with zone floor areas `A_i`,

$$
\theta_x^*=\frac{\sum_i A_i\theta_{x,i}}{\sum_i A_i},\quad
H_x^*=\sum_iH_{x,i},\quad
o_x^*=\sum_i\bigl[o_{x,i}+H_{x,i}(\theta_{x,i}-\theta_x^*)\bigr],
$$

$$
G^*=\sum_iG_i,\qquad C^*=\sum_i C_i.
$$

Consequently `H_x^*(θ_x^*−θ̄_e)+o_x^*` equals the sum of the *unclipped*
zone heat-loss powers. The capacity and gains also sum. The implementation
adds the zones' `H_τ` values for the collapsed utilisation calculation; this
is an explicit approximation when the zones' maxima occur at different times.
The AHU components are summed from the physical zones rather than replaced by
a fictitious central AHU.

**Collapse then solve** can differ from **solve each zone then sum** because
the utilisation ratios and `max(0, ·)` bounds are nonlinear. This remains true
even for fixed factors if one zone has a demand while another has an opposing
surplus. The QSS figure used for comparison is its *sum of independently
solved zones*; it is not a QSS collapsed calculation.

## 4. Differences among the three collapsed approaches

### 1. Monthly_SS_VBDD monthly collapsed: direct solar and monthly utilisation

The shared weather preprocessor derives plane-of-array irradiance from the EPW
for each configured surface orientation. Glazing, diffuse radiation, shading,
opaque absorption and longwave exchange produce each zone's net solar gain;
the collapsed monthly `q_sol` is their sum. The model then calculates `γ_h,m`,
`γ_c,m`, `η_h,m` and `η_c,m` from **that month's** losses and gains and computes
the variable balance points and degree days above.

This is the closest continuation of the prototype's retained monthly
semi-stationary QSS. At the **individual-zone** level, direct-solar monthly Monthly_SS_VBDD
and QSS are the same algebra on the same prepared inputs and agree to numerical
precision in this run. The collapsed result need not equal the QSS zone sum
because of the collapse step, not because the balance equations changed.

### 2. Monthly_SS_VBDD linear collapsed: temperature-linear solar, monthly utilisation

For each envelope/case, the preprocessor fits the twelve **input-derived**
monthly net solar average powers to monthly outdoor temperature:

$$
\widehat q_{\mathrm{sol},m}=e_0+e_1\bar\theta_{e,m}.
$$

The fit uses EPW/envelope solar gains only; it does not use heating or cooling
demand. The fitted solar value replaces `q_sol,m` in `G_m`. The model then
recalculates the monthly ratios, utilisation factors, base temperatures and
degree days. The fit is reproduced by the Monthly_SS_VBDD runner, and its effect is
exposed in the [current Monthly_SS_VBDD workbook](../spreadsheets/DT_Prototype_Monthly_SS_VBDD_Energy.xlsx)
and accepted shared-energy results.
The paper allows separate heating-season `e₀,e₁` and cooling-season `f₀,f₁`
solar approximations. This implementation fits **one twelve-month net-solar
relationship per case** and applies it in both modes. It does not estimate
separate seasonal coefficients from the few cooling months in this dataset.
For the thirteen supplied cases the solar-fit `R²` is 0.815–0.824, so the
linear estimate retains a real seasonal residual. It is tied to this weather
year and envelope; it should be refitted when either changes.

The paper's *type 1* energy signature also uses a temperature-linear solar
term. **Approach 2 is not a single global linear demand signature:** its
utilisation factors, effective heat-transfer coefficients, operating offsets
and internal gains can change by month. It only makes the **solar input**
linear in temperature.

### 3. Monthly_SS_VBDD fixed collapsed: direct solar, fixed utilisation

This case uses exactly the same direct net solar input as approach 1. In the
reported run the fixed coefficients are `η_h = η_c = 1` and both attenuation
fractions are zero. Thus every solar/internal gain offsets heating and every
heat loss offsets cooling at full value, before the nonnegative-demand bound.
The balance becomes

$$
Q_{\mathrm{zone},h}=\frac{24d}{1000}\max(0,L_h-G),\qquad
Q_{\mathrm{zone},c}=\frac{24d}{1000}\max(0,G-L_c).
$$

Thermal capacity is retained as an input/diagnostic but **does not affect the
fixed-factor demand**. The fixed coefficients here are an explicit, uncalibrated
steady-balance test. They are **not** the original spreadsheet's empirical
schedule-dependent factors, nor coefficients fitted to `Monthly_SS` or `Monthly_SS_simplified`
outputs. The software allows different declared fixed `η` and attenuation
values; the comparison in this guide refers to the defaults above.

### Connection to the paper's regression coefficients

The D4.1 draft and paper give two inverse-model forms: *type 1*, based on
temperature after replacing solar by `e₀ + e₁θ_e`, and *type 2*, retaining a
separate solar-radiation term. Holding a month's `H`, offsets, internal gains
and **fixed** utilisation constant while writing `q_sol=e₀+e₁θ_e` yields

$$
q_h(\theta_e)=\max(0,a_0+a_1\theta_e),\quad
a_0=\frac{H_h\theta_h+o_h-\eta_h(e_0+q_{\mathrm{int}})}{1000},\quad
a_1=-\frac{H_h+\eta_h e_1}{1000},
$$

$$
q_c(\theta_e)=\max(0,c_0+c_1\theta_e),\quad
c_0=\frac{e_0+q_{\mathrm{int}}-\eta_c(H_c\theta_c+o_c)}{1000},\quad
c_1=\frac{e_1+\eta_cH_c}{1000}.
$$

The intercepts are kW, slopes kW/K, and the corresponding constant-coefficient
breakpoints are `−a₀/a₁` and `−c₀/c₁` where defined. These formulas are exposed
by [`vbdd/signature.py`](../src/dt_prototype/monthly_ss_vbdd/signature.py) and exported
when a new Monthly_SS_VBDD comparison is run.
They describe *local fixed-coefficient signatures*, not the complete
month-varying response of approaches 1 or 2. Approach 3 keeps direct solar,
so it also need not be one global five-parameter curve. The separate 5P fits
in the comparison are **inverse fits to simulated average monthly power**,
not inputs to any of these three forward models.

The D4.1 draft repeats several equations for formatting comparison and has
some notation inconsistencies. In one expanded heating line it implies
`−(H_h − η_h e₁)`, whereas direct substitution, the draft's coefficient
table, the published paper's Table 2 and the original workbook's T163 give
**`−(H_h + η_h e₁)`**, as used above. A cooling line in the draft carries a
heating solar subscript; the cooling balance here uses cooling-period gains.

## 5. Numerical comparison of the collapsed cases

The table shows the reported annual **total useful sensible demand** in
MWh/year: zone plus separate AHU. It uses the four genuinely two-zone
buildings in the supplied 2023 example. The only change between each row's
three VB columns is the solar/utilisation choice in the first table.

| Building | Heat: monthly | Heat: linear | Heat: fixed | Cool: monthly | Cool: linear | Cool: fixed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Test building 1 | 304.544 | 304.449 | 289.146 | 68.040 | 68.910 | 50.883 |
| Test building 2 | 131.811 | 131.654 | 124.064 | 33.621 | 34.339 | 25.914 |
| Test building 3 | 292.816 | 292.578 | 283.982 | 34.908 | 35.389 | 20.034 |
| Test building 4 | 1,154.379 | 1,153.812 | 1,145.957 | 83.485 | 84.404 | 56.930 |

For example, in **Test building 1** the direct-solar/monthly-utilisation case
gives 68.040 MWh cooling. Replacing solar with its temperature-linear estimate
gives 68.910 MWh; keeping direct solar but setting `η_c=1` gives 50.883 MWh.
The temperature-linear simplification therefore changes the solar input *and
then* the monthly utilisation, whereas the fixed case changes utilisation
without changing solar. In July of that case, the monthly cooling balance
temperature moves from 17.981°C (direct/monthly) to 18.101°C (linear/monthly)
and 19.076°C (direct/fixed). Those shifts yield different cooling degree days.
The retained cross-model differences are in the
[numeric comparison — full archive](validation_archive.md#reports-shared-energy-differences-vs-qss-csv) and
[accepted report](../reports/shared_energy/comparison_report.md).

These figures compare model formulations on the **same input data**. They do
not rank physical accuracy: the example has no metered demand for these cases,
the monthly variant shares its balance equations with QSS, and the temperature-
linear solar approximation was fitted on this weather year. The fixed case's
lower cooling follows directly from giving heat losses full cooling
utilisation. The relative differences depend on building, month and which
zone representation is chosen.

## Reproduce or inspect

- Run the three choices from the prototype root with
  [`runners/run_monthly_ss_vbdd.py`](../runners/run_monthly_ss_vbdd.py):

  ```powershell
  python runners/run_monthly_ss_vbdd.py --config configs/example.json --output outputs/vb_monthly
  python runners/run_monthly_ss_vbdd.py --config configs/example.json --solar temperature_linear --output outputs/vb_linear
  python runners/run_monthly_ss_vbdd.py --config configs/example.json --utilisation fixed --output outputs/vb_fixed
  ```

  Select `representation=single_zone_collapsed_from_two_zones` in each run's
  `monthly.csv` or `annual.csv`. Each command needs a new output directory.
- In the [verification workbook](../spreadsheets/DT_Prototype_Monthly_SS_VBDD_Energy.xlsx),
  set `Settings!B5=1, B6=0` for monthly, `B5=1, B6=1` for linear, and
  `B5=0, B6=0` for fixed. `Calc_Monthly` shows the ratios, `η`, balance
  temperatures, degree days and zone/AHU totals; `Out_Annual` displays the
  corresponding collapsed totals. `Check` compares the live formulas to
  frozen Python results for each setting.

For the detailed interface and design decisions, see
[`vbdd_methodology.md`](vbdd_methodology.md). For the complete zone and
historical-model comparisons, see the
[accepted shared-energy report](../reports/shared_energy/comparison_report.md).
