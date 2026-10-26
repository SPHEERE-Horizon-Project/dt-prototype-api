# Preparing and validating measured energy data

No measured building dataset was supplied for this development. The executable
checks and synthetic fixtures are ready; **empirical validation remains pending**.
Neither a successful fit nor a simulation comparison establishes operational
accuracy. The check cannot independently verify whether a file labelled
`measured` actually came from a meter; provenance remains the data owner's duty.

## Fill the input template

Copy [inverse_measured_template.json](../configs/inverse_measured_template.json)
to a project-specific configuration. The template is deliberately not runnable
until the two CSV files exist. `data/private/` is ignored by Git. Enter a stable
building ID, dataset ID, meter boundary, carrier, weather station and scenario.
Use multiple series entries for independent buildings/meters; do not add totals
to their constituent meters, or combine collapsed and zonal alternatives.

Create `observations.csv` with this header:

```csv
series_id,interval_start,interval_end,energy_kWh,split,quality
```

Each row is an actual meter interval, with an inclusive start and exclusive end.
Use kWh **consumed during that interval**, not average kW or a cumulative register.
Convert cumulative registers externally after checking resets/rollovers. Import
and export require separate nonnegative series; signed net exchange is unsupported.
Missing readings are blank, not zero. Supported splits are `train`, `validation`,
`test`, `excluded`, `predict`; quality is `valid`, `missing`, `excluded`.
Use a complete earlier training block and a later holdout block selected before
fitting. Retain a final untouched test period if the validation period is used
to select models or thresholds.

Create hourly interval-start `weather.csv`:

```csv
weather_id,time,temperature_C,ghi_Wm2
```

Temperature must cover every requested interval with contiguous hourly records.
GHI is optional for 5P/billing/nonsolar hourly, required for solar hourly. Its
unit is W/m², not hourly solar energy. Declare the clock correctly: civil clocks
need explicit UTC offsets for repeated autumn hours; nonexistent spring hours
must not be fabricated. EPW-based simulated weather uses fixed standard time.
The template uses `Europe/Rome` civil time; change it to match the actual data.

5P requires complete calendar months. Billing accepts actual contiguous bill
intervals with local-midnight boundaries; do not manufacture hourly readings
from monthly bills. Hourly requires genuine hourly energy (or supported
subhourly energy summed without filling gaps). See the
[inverse contract](inverse_models.md) for detailed rules and model selections.
To use OpenDSM, select its backend(s) and add the isolated `opendsm_python` path.

## Define acceptance before viewing holdout results

[measured_acceptance_policy.json](../configs/measured_acceptance_policy.json)
contains **illustrative project settings**, not ISO/ASHRAE certification criteria:

- At least 365 elapsed training days and 90 observed holdout days.
- At least three observed holdout intervals and 5 °C training temperature span.
- Complete prediction coverage of eligible observed holdout intervals.
- Absolute NMBE ≤5%; CV(RMSE) ≤20% for 5P/billing and ≤35% for hourly.
- No native OpenDSM disqualification.

Choose thresholds suitable for the meter, use case and resolution, record why,
and freeze them before inspection. Scores use observed minus predicted and
`p=0`, matching common inverse reporting. Training and holdout durations sum
eligible interval lengths; gaps do not count as observed days. A percentage
metric undefined because of zero mean load fails acceptance, rather than
silently passing. The policy does not assert comprehensive seasonal or regime
coverage from duration alone: inspect temperature ranges, heating/cooling
seasons, changes in occupancy/equipment and extrapolation warnings as well.

```powershell
python runners/run_preflight.py --kind inverse --config configs/my_measured.json
python runners/run_inverse_models.py --config configs/my_measured.json --output outputs/measured_fit
python runners/run_measured_validation.py --results outputs/measured_fit --policy configs/measured_acceptance_policy.json --report outputs/measured_acceptance.json
```

Acceptance checks re-read hashed run snapshots, verify series identities,
reconstruct observed monthly targets where necessary, and reject altered split,
quality, target or interval labels in predictions. The report records policy,
manifest and prediction hashes, scores and reasons per model. A synthetic or
simulated source always returns `review_required`; it cannot pass empirical
validation. Native disqualification and wrapper compatibility warnings remain
available in the model manifest.

Exit **0** means all selected models meet the declared checks; **2** means
review is required; **1** means the validation inputs are invalid. Passing this
check is project-defined observed-holdout acceptance, not approved savings or
statutory certification. An evaluation run containing only holdout periods does
not contain enough documented training coverage for this check; retain the full
training/holdout snapshot or inspect its separate training evidence explicitly.

The supplied synthetic two-year fixtures test the data contract, holdout
separation and acceptance logic. The separate single-year building-1 fixture
tests the OpenDSM zero-coefficient compatibility case. Both remain labelled
simulated in data and documentation.
