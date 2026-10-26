"""
preprocess.py - Dedicated pre-processing: from the energy_insight datasets to OpenDSM's input.

For each period:
  1. energy (local clock time with daylight saving, timestamp = start of the hour) -> model time
     (local standard time, UTC+1): the non-existent spring hour is dropped (the meter recorded a
     value for an hour that did not exist); the single value of the repeated autumn hour is given
     to its first occurrence, so the second one is missing and filled linearly;
  2. weather (timestamps as [time] says: start or end of the hour, in UTC or in the local clock) -> start of
     the hour in model time; a single hour missing because of the clock change is filled linearly;
  3. model days = days (in model time) whose 24 hours all belong to days selected by
     energy_insight for its models (no reconstructed profiles, no metering gaps, complete data);
  4. OpenDSM columns: `observed` [kWh], `temperature` [°F], `ghi` [W/m²]. Hours outside the model
     days get observed = NaN and `interpolated_observed` = 1: OpenDSM then neither trains on them
     nor imputes them (its gap filling is meant for short gaps; these are exclusions of up to
     15 months).

In model time every day has 24 hours (no daylight-saving days) and energy and weather refer to
the same hour all year, which OpenDSM's day-by-day feature construction requires. The model time is the
local STANDARD time of the site ([time] model_timezone; "auto" derives it from the site's time zone).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .settings import Settings


@dataclass
class PeriodData:
    period: int
    frame: pd.DataFrame                    # hourly, model time (tz-aware index)
    model_days: pd.DatetimeIndex           # naive dates (model time)
    info: dict = field(default_factory=dict)


def energy_to_model_time(energy: pd.Series, site_tz: str, model_tz: str) -> tuple[pd.Series, dict]:
    """Local-clock hourly series -> model time. Returns the series and conversion counts."""
    local = energy.index.tz_localize(site_tz, ambiguous=np.ones(len(energy), dtype=bool), nonexistent="NaT")
    out = pd.Series(energy.to_numpy(), index=local, name=energy.name)
    dropped = int(local.isna().sum())
    either = int(energy.index.tz_localize(site_tz, ambiguous="NaT", nonexistent="NaT").isna().sum())
    out = out[local.notna()].tz_convert(model_tz)
    return out, {"nonexistent_hours_dropped": dropped, "repeated_hours_first_occurrence": either - dropped}


def weather_to_model_time(weather: pd.DataFrame, marks: str, clock: str, model_tz, site_tz: str | None = None
                          ) -> pd.DataFrame:
    """Weather labelled at the start or end of the hour in `clock` -> start of the hour, model time.

    clock = "UTC" (or any fixed-offset zone name), or "local" = the clock of the site (`site_tz`, with daylight
    saving time; labelled like the energy: the repeated hour of the autumn is the first occurrence, the
    non-existent hour of the spring is dropped)."""
    shift = pd.Timedelta(hours=1) if marks == "end" else pd.Timedelta(0)
    shifted = weather.index - shift
    out = weather.copy()
    if clock == "local":
        local = shifted.tz_localize(site_tz, ambiguous=np.ones(len(shifted), dtype=bool), nonexistent="NaT")
        out.index = local
        out = out[local.notna()]
        out.index = out.index.tz_convert(model_tz)
    else:
        out.index = shifted.tz_localize(clock).tz_convert(model_tz)
    return out


def build_period(settings: Settings, period: int, energy: pd.DataFrame, climate: pd.DataFrame,
                 days: pd.DataFrame) -> PeriodData:
    """OpenDSM input frame of one period (see module docstring)."""
    tz = settings.model_timezone
    selected = days.index[(days["period"] == period) & days["included"]]
    e_model, info = energy_to_model_time(energy["energy_kWh"], settings.site_timezone, tz)
    w = weather_to_model_time(climate[[settings.temperature_column, settings.ghi_column]],
                              settings.weather_label_marks, settings.weather_clock, tz, settings.site_timezone)

    first, last = w.index.min(), w.index.max()                     # whole model-time days only
    start = first if first == first.floor("D") else first.ceil("D")
    end = (last + pd.Timedelta(hours=1)).floor("D") - pd.Timedelta(hours=1)
    idx = pd.date_range(start, end, freq="h", tz=tz, name="timestamp")
    frame = pd.DataFrame(index=idx)
    date = idx.tz_localize(None).normalize()                       # model-time calendar day
    local_date = idx.tz_convert(settings.site_timezone).tz_localize(None).normalize()
    eligible = local_date.isin(selected)                           # hour belongs to a selected local day

    observed = e_model.reindex(idx).where(eligible)
    missing = observed.isna() & eligible
    per_day_missing = pd.Series(missing, index=idx).groupby(date).transform("sum").to_numpy()
    fill_ok = eligible & (per_day_missing <= settings.max_filled_hours_per_day)
    filled = observed.interpolate(limit=settings.max_filled_hours_per_day, limit_area="inside")
    observed = observed.where(~(missing & fill_ok), filled)
    model_day = pd.Series(observed.notna() & eligible, index=idx).groupby(date).transform("all").to_numpy()

    # weather on every hour of the model time; the one hour that a local clock change can leave without a value
    # is filled linearly (nothing to fill when the weather is in UTC)
    wx = w.reindex(idx).interpolate(limit=settings.max_filled_hours_per_day, limit_area="inside")
    frame["observed"] = observed.where(model_day)
    frame["temperature"] = wx[settings.temperature_column] * 9.0 / 5.0 + 32.0
    frame["ghi"] = wx[settings.ghi_column]
    frame["interpolated_observed"] = (~model_day).astype(int)
    frame["temperature_C"] = wx[settings.temperature_column]
    frame["model_day"] = model_day
    frame["filled_hour"] = missing & model_day
    cal = days.reindex(date)
    frame["working_day"] = cal["working_day"].fillna(False).astype(bool).to_numpy()
    frame["holiday"] = cal["holiday"].fillna(0).astype(int).to_numpy()
    frame["local_timestamp"] = idx.tz_convert(settings.site_timezone).tz_localize(None)

    model_days = pd.DatetimeIndex(sorted(set(date[model_day])))
    if frame[["temperature", "ghi"]].isna().any().any():
        raise ValueError(f"period {period}: weather does not cover every hour in model time")
    info.update({
        "period": period, "hours": len(frame), "days": int(len(frame) / 24),
        "selected_local_days": int(len(selected)), "model_days": int(len(model_days)),
        "filled_hours": int(frame["filled_hour"].sum()),
        "first_day": f"{model_days.min():%Y-%m-%d}", "last_day": f"{model_days.max():%Y-%m-%d}",
    })
    return PeriodData(period, frame, model_days, info)
