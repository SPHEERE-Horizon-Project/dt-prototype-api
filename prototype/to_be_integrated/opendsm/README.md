# OpenDSM benchmark

A separate program that predicts the hourly load of a building with **OpenDSM** (LF Energy, formerly OpenEEmeter),
version 1.2.7, and its EEmeter hourly model, in sample and out of sample, and writes the predictions that energy_insight
component 5 compares its hourly model with. The OpenDSM library is used unchanged.

It runs **on its own**: it has its own environment (OpenDSM needs pandas 2.x while energy_insight uses pandas 3), its own
configuration and entry point, and does not import energy_insight. It reads either the interim datasets of energy_insight
or, stand-alone, one plain CSV file per period (section "Stand-alone use"), so it can benchmark any hourly dataset.

## Set-up

Run these commands in this folder:

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

`requirements.txt` pins the tested environment (Python 3.12). It pins `multimethod<2` because OpenDSM's dependency
scikit-fda fails to import with multimethod 2.x.

## Run

With the default configuration (`source = "energy_insight"`), first run energy_insight in the root folder, at least stages
1 and 2 (`python run_pipeline.py --stages 1 2`): the benchmark reads its cleaned datasets. Then, in this folder:

```bash
.venv\Scripts\python run_benchmark.py
```

About 1 minute. Options: `--periods 3` (selected periods), `--config other.toml` (another configuration; its paths are
relative to its folder). Settings are in `config.toml`, whose sections are named in its header: inputs, time conventions,
weather columns, OpenDSM options, folds. A mistake in the file stops the run at once with a list of problems.

Afterwards run energy_insight stage 5 again (`python run_pipeline.py --stages 5`) to update the comparison.

## Modules (`src/opendsm_benchmark/`)

| Module | Role |
|---|---|
| `settings.py` | `config.toml` as a typed object, checked when loaded; the standard-time zone of a site |
| `inputs.py` | reads the data from either source and checks it |
| `preprocess.py` | model time (local standard time), °F, weather, model days → OpenDSM's frames |
| `opendsm_runner.py` | OpenDSM fit and predict, used unchanged |
| `folds.py` | blocked cross-validation folds |
| `response.py` | the daily temperature response of the fitted model, per temporal cluster |
| `metrics.py` | accuracy measures |
| `pipeline.py` | the run, end to end, and its command line |

## What it does

1. **Inputs** (`inputs.py`). Whatever the source, three tables per period: hourly energy (local clock time), hourly weather
   (temperature and irradiance) and the days usable for the models.
   - `source = "energy_insight"`: the interim datasets of energy_insight (hourly energy, hourly weather, the daily selection of
     model days), checked against the columns they need.
   - `source = "csv"`: one CSV per period; a day is usable when its 24 hours have energy and `use` is not 0.
2. **Pre-processing** (`preprocess.py`).
   - Energy (local clock time) and weather (as `[time]` says: start or end of the hour, in UTC or in the local clock) are converted to
     local *standard* time. There every day has 24 hours and the two refer to the same hour. `model_timezone = "auto"` derives
     the standard time from `site_timezone` (UTC+1 for Europe/Rome, which is the POSIX zone `Etc/GMT-1`).
   - Temperature is converted to °F. The irradiance is the `ghi_column` of `config.toml`: `ghi_Wm2`, the same series energy_insight uses
     (local measurements, with ERA5 corrected towards them where they have gaps). The raw ERA5 series `GHI_era5_raw_Wm2` is the alternative.
   - Days that are not model days are passed to OpenDSM as flagged missing data, so OpenDSM neither trains on them nor imputes them.
3. **OpenDSM** (`opendsm_runner.py`). The library is used unchanged. Four of its properties are handled here.
   - Daylight-saving days break its day-by-day features, which is why the models run in local standard time.
   - `predict()` alters the fitted model, so a fresh copy is restored from its JSON for every prediction call.
   - It cannot predict a month × weekday absent from training. Prediction runs on consecutive days only; a day whose month × weekday
     was not trained gets no prediction (missing values in the predictions file, and excluded from the accuracy of that variant).
   - `is_electricity_data = false` keeps the genuine zero net import of PV hours.
   - OpenDSM's baseline sufficiency rules are not met by short periods. The fits are made with `ignore_disqualification` and every
     disqualification is listed in `results/summary/benchmark_fits.csv`.
4. **Folds** (`folds.py`). Blocked 5-fold cross-validation: the model days are cut into 7-day blocks and assigned round-robin to the
   folds. Every model day is predicted by a model fitted without its fold. The folds of every day are written, so energy_insight
   scores its models on the same split.
5. **Temperature response** (`response.py`). How the fitted solar model depends on temperature, per temporal cluster of OpenDSM, with
   the knots of its temperature bins. It is drawn by energy_insight beside the change-point models.

## Stand-alone use

Set `source = "csv"` in `config.toml` and provide one CSV file per period. No other program is needed.

| Column (name in `[inputs] csv_*`) | Content |
|---|---|
| `timestamp` | hour beginning, local clock time of the site, no time zone suffix, on the hour; the repeated hour at the end of daylight saving time appears once |
| `energy_kWh` | energy of the hour [kWh] (= mean power [kW]); an empty value makes the day unusable |
| `temperature_C` | outdoor temperature [°C], complete |
| `ghi_Wm2` | global horizontal irradiance [W/m²], complete; set `csv_ghi = ""` and `variants = ["nonsolar"]` if there is none |
| `use` (optional) | 0 leaves the day out of the models |

```csv
timestamp,energy_kWh,temperature_C,ghi_Wm2,use
2021-03-26 00:00:00,4.1,11.6,0,1
2021-03-26 01:00:00,4.2,11.4,0,1
```

```toml
[inputs]
source = "csv"
periods = [1]
csv_file = "data/hourly_period_{period}.csv"      # relative to the folder of config.toml
[time]
site_timezone = "America/New_York"                 # IANA name of the clock of the file
weather_label_marks = "start"                      # the weather is labelled at the start of the hour ...
weather_clock = "local"                            # ... in the local clock of the site
model_timezone = "auto"                            # local standard time, derived from site_timezone
```

Rules: every date has its 24 hours (rows missing in the file are gaps); periods must not share dates; the weather must be complete
(fill gaps beforehand); the energy may have gaps (those days are left out). This mode was checked against the energy_insight mode on the
Procida data: the predictions are identical, hour by hour. The `local` weather clock was checked to give the same weather in model time as the
UTC convention.

## Porting the benchmark

1. Copy this folder (without `.venv/` and `results/`) to the new project or machine. It needs `run_benchmark.py`, `src/`, `config.toml`,
   `requirements.txt` (and `pyproject.toml` for an installable package).
2. Create the environment there (Python 3.11 or later) with `pip install -r requirements.txt`. Optionally `pip install .`, which provides the
   command `opendsm-benchmark --config <file>`.
3. Edit `config.toml`: `[inputs]` (source, files), `[time]` (clocks), `[opendsm]` (variants, seed).
4. Run `run_benchmark.py`; read the results below.
5. To use them in energy_insight, point its `[hourly_model] benchmark_*` patterns to the files.

## Outputs (`results/`)

- `period_<k>/predictions_period_<k>.csv`: every hour of the period: the measured value (`observed`), the in-sample (`in_sample_<variant>`)
  and the out-of-sample (`cv_<variant>`) prediction of each variant, the fold of the day, the local clock timestamp.
- `period_<k>/folds_period_<k>.csv`: the fold of every model day.
- `period_<k>/temperature_response_period_<k>.csv`: the response curve of every temporal cluster (`kind = curve`) and every model day with its
  cluster (`kind = day`).
- `period_<k>/models/opendsm_<variant>_model_period_<k>.json`: the fitted OpenDSM model (the parameter count is read from it; the models can be
  reloaded with `HourlyModel.from_json`).
- `summary/benchmark_metrics.csv`: hourly and daily accuracy of every variant, in sample and out of sample.
- `summary/benchmark_fits.csv`: OpenDSM's qualification of each fit and the overridden disqualifications.

## Variants

- `solar`: temperature and irradiance (OpenDSM's solar hourly model). The comparator of energy_insight's hourly model.
- `nonsolar`: temperature only. The like-for-like comparator of the energy_insight models that use no irradiance.

## Results (Procida)

Hourly CV(RMSE), as OpenDSM's own predictions on the benchmark's hours (`summary/benchmark_metrics.csv`; no degrees-of-freedom correction, the
out-of-sample predictions have p = 0):

| Period | Solar, in sample | Solar, out of sample | Temperature-only, in sample | Temperature-only, out of sample |
|---|---|---|---|---|
| 1 | 36.2 % | 42.3 % | 40.0 % | 46.4 % |
| 2 | 33.6 % | 42.0 % | 36.5 % | 44.5 % |
| 3 | 41.2 % | 46.8 % | 43.6 % | 49.4 % |

The comparison with energy_insight component 5 uses the same hours with ASHRAE Guideline 14 degrees of freedom (in sample: n − p, with OpenDSM's
p = its non-zero coefficients, 389 / 476 / 433 for the solar variant); see `data/3_output/reports/5_hourly_model_report.md` of the root project.

**Previous irradiance input.** The first version of this benchmark used raw ERA5 irradiance (`GHI_era5_raw_Wm2`). Its solar variant then gave
43.6 %, 42.7 % and 46.8 % out of sample. That result is reproduced by setting `ghi_column = "GHI_era5_raw_Wm2"` in `config.toml`, with the results
written to another folder (`results_dir`). The series of energy_insight is the better match for the comparison: it is the weather that the
energy_insight models use.

## Notes and limitations

- OpenDSM is designed for one-year baselines and counterfactual savings. These periods are shorter or gappier, so the results are a benchmark of
  the model structure on this data, not compliant OpenDSM measurements.
- The predictions are made on the days of the model dataset (energy_insight) or the usable days of the CSV files.
- The PV identification that was part of earlier versions of this benchmark (rolling irradiance response, start date of the PV) is not part of the
  workflow any more. It is not needed for the comparison of component 5.
