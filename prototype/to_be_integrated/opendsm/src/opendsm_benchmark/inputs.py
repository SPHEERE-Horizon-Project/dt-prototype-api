"""
inputs.py - Reads the data of the benchmark, from either source ([inputs] source in config.toml).

    load(settings, periods)    -> {period: (energy, climate)} and the table of model days, whatever the source

    source = "energy_insight"  the cleaned interim datasets of the energy_insight pipeline. The benchmark does
                               not import energy_insight: it reads its CSV files, whose format is fixed by
                               data contracts (docs/data_contracts.md of energy_insight), and checks the columns
                               it needs.
        read_energy(settings, period)    hourly energy, local clock time   (contract energy_hourly)
        read_climate(settings, period)   hourly weather, all sources        (contract climate_hourly)
        read_model_days(settings)        daily selection and calendar       (contract model_dataset_daily)

    source = "csv"             stand-alone: one plain CSV per period, see read_csv_period and the README
        read_csv_period(settings, period)

Whatever the source, the result has the same shape, which preprocess.py turns into OpenDSM's input:
    energy    hourly, index = hour-beginning local clock timestamps (whole days), column energy_kWh
    climate   hourly, index = the same labels, columns settings.temperature_column [degC], settings.ghi_column
              [W/m2]; what the labels mean is set in [time] (weather_label_marks, weather_clock)
    days      one row per date: period, included (day usable for the models), holiday, working_day, day_of_week
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .settings import Settings

HINT = ("Run the energy_insight pipeline first (in its root folder: `python run_pipeline.py`, "
        "or at least stages 1 to 3), or point [inputs] in config.toml to the right files.")


def _read(path: Path, required: list[str], index: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. {HINT}")
    df = pd.read_csv(path, index_col=0, float_precision="round_trip")
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index), name=index)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}. {HINT}")
    if not df.index.is_unique or not df.index.is_monotonic_increasing:
        raise ValueError(f"{path.name}: index must be unique and sorted")
    return df


def _check_whole_days(df: pd.DataFrame, name: str) -> None:
    per_day = pd.Series(df.index.hour, index=df.index).groupby(df.index.normalize()).agg(["count", "min", "max"])
    if ((per_day["count"] != 24) | (per_day["min"] != 0) | (per_day["max"] != 23)).any():
        raise ValueError(f"{name}: every date must have the hours 0-23")


def read_energy(settings: Settings, period: int) -> pd.DataFrame:
    path = settings.input_path("energy_hourly", period)
    df = _read(path, ["energy_kWh", "energy_source"], "timestamp")
    _check_whole_days(df, path.name)
    if (df["energy_kWh"] < 0).any():
        raise ValueError(f"{path.name}: negative energy")
    return df


def read_climate(settings: Settings, period: int) -> pd.DataFrame:
    path = settings.input_path("climate_hourly", period)
    df = _read(path, [settings.temperature_column, settings.ghi_column], "timestamp")
    _check_whole_days(df, path.name)
    for column in (settings.temperature_column, settings.ghi_column):
        if df[column].isna().any() or not np.isfinite(df[column]).all():
            raise ValueError(f"{path.name}: {column} must be complete and finite")
    return df


def read_model_days(settings: Settings) -> pd.DataFrame:
    path = settings.input_path("model_dataset")
    df = _read(path, ["period", "included", "holiday", "working_day", "day_of_week"], "date")
    for column in ("included", "working_day"):
        df[column] = df[column].astype(str).str.lower().map({"true": True, "false": False}).astype(bool)
    return df


# --------------------------------------------------------------------------------------
# Stand-alone source: one plain CSV per period
# --------------------------------------------------------------------------------------
def read_csv_period(settings: Settings, period: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """One period from a plain CSV file ([inputs] csv_file, column names csv_*).

    One row per hour. Columns: the timestamp (hour-BEGINNING, local clock time of the site, no time zone
    suffix, on the hour; the repeated hour of the end of daylight saving time appears once), the energy [kWh],
    the temperature [degC] and the global horizontal irradiance [W/m2] (labelled as [time] says), and
    optionally a `use` column (csv_use): 0 leaves the hour's day out of the models. Hours without a row, or with
    an empty energy, make their day unusable; the weather must be complete (fill gaps beforehand). A day is
    usable if its 24 hours have energy and `use` is not 0. Periods must not share dates.
    Returns (energy, climate, days) as described in the module docstring."""
    c = settings.csv
    path = settings.csv_path(period)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: set [inputs] csv_file in config.toml (one CSV per period)")
    raw = pd.read_csv(path)
    columns = {"timestamp": c["csv_timestamp"], "energy": c["csv_energy"], "temperature": c["csv_temperature"]}
    if c["csv_ghi"]:
        columns["ghi"] = c["csv_ghi"]
    missing = [name for name in columns.values() if name not in raw.columns]
    if missing:
        raise ValueError(f"{path.name}: column(s) {missing} not found; the file has {list(raw.columns)}. "
                         "Set the csv_* names in [inputs] of config.toml.")
    index = pd.DatetimeIndex(pd.to_datetime(raw[columns["timestamp"]]), name="timestamp")
    if index.tz is not None:
        raise ValueError(f"{path.name}: timestamps must be local clock time without a time zone suffix")
    if (index.minute != 0).any() or (index.second != 0).any():
        raise ValueError(f"{path.name}: timestamps must be on the hour (hourly data)")
    if index.duplicated().any():
        raise ValueError(f"{path.name}: duplicated timestamps (the repeated hour of the end of daylight saving "
                         "time must appear once)")
    df = raw.set_index(index).sort_index()
    hours = pd.date_range(df.index[0].normalize(), df.index[-1].normalize() + pd.Timedelta(hours=23), freq="h",
                          name="timestamp")
    df = df.reindex(hours)                                   # whole days; missing rows become NaN
    energy = pd.to_numeric(df[columns["energy"]], errors="raise")
    if (energy < 0).any():
        raise ValueError(f"{path.name}: negative energy")
    weather = {settings.temperature_column: pd.to_numeric(df[columns["temperature"]], errors="raise"),
               settings.ghi_column: (pd.to_numeric(df[columns["ghi"]], errors="raise") if "ghi" in columns
                                     else pd.Series(0.0, index=hours))}
    climate = pd.DataFrame(weather, index=hours)
    bad = [name for name in climate if climate[name].isna().any() or not np.isfinite(climate[name]).all()]
    if bad:
        raise ValueError(f"{path.name}: {bad} must be complete and finite (rows missing or empty): fill the gaps")
    use = (pd.to_numeric(df[c["csv_use"]], errors="raise").fillna(1) != 0) if c["csv_use"] in df else pd.Series(True, index=hours)
    energy_frame = pd.DataFrame({"energy_kWh": energy,
                                 "energy_source": np.where(energy.notna(), "csv", "missing")}, index=hours)
    day = hours.normalize()
    usable = (energy.notna() & use).groupby(day).all()
    dates = pd.DatetimeIndex(usable.index, name="date")
    days = pd.DataFrame({"period": period, "included": usable.to_numpy(), "holiday": 0,
                         "working_day": dates.dayofweek < 5, "day_of_week": dates.day_name()}, index=dates)
    return energy_frame, climate, days


def load(settings: Settings, periods: list[int]) -> tuple[dict[int, tuple[pd.DataFrame, pd.DataFrame]], pd.DataFrame]:
    """Energy and climate of every period and the table of model days, from the configured source."""
    if settings.input_source == "energy_insight":
        days = read_model_days(settings)
        return {p: (read_energy(settings, p), read_climate(settings, p)) for p in periods}, days
    data, parts = {}, []
    for p in periods:
        energy, climate, period_days = read_csv_period(settings, p)
        data[p] = (energy, climate)
        parts.append(period_days)
    days = pd.concat(parts)
    if not days.index.is_unique:
        raise ValueError("the periods share dates: every date must belong to one period")
    return data, days
