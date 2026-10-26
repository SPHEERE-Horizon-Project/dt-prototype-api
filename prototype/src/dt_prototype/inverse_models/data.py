"""Explicit interval targets, hourly weather and physical series identities."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

BACKENDS = {"5p_monthly", "opendsm_billing", "opendsm_hourly"}
META = {"source_type", "source_id", "building_id", "scenario_id", "carrier", "meter_boundary_id", "weather_id"}
SPLITS = {"train", "validation", "test", "excluded", "predict"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def keys(value, allowed, label):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(f"{label}: expected object with fields {sorted(allowed)}")


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key}")
            result[key] = value
        return result

    def finite(value):
        number = float(value)
        if not np.isfinite(number):
            raise ValueError("non-finite JSON number")
        return number

    def bad(value):
        raise ValueError(f"non-finite JSON constant {value}")

    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique,
                      parse_float=finite, parse_constant=bad)


def csv(path):
    import csv as module
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        reader = module.reader(source, strict=True)
        header = next(reader, [])
        if not header or len(header) != len(set(header)):
            raise ValueError(f"{path}: empty or duplicate CSV header")
        rows = [r for r in reader if r]
        if any(len(r) != len(header) for r in rows):
            raise ValueError(f"{path}: CSV row width mismatch")
    return pd.DataFrame(rows, columns=header)


def timestamps(values, clock):
    """Accept true offset timestamps; reject ambiguous/nonexistent naive civil time."""
    if not len(values):
        raise ValueError("empty timestamp sequence")
    parsed = [pd.Timestamp(v) for v in values]
    if any(pd.isna(t) for t in parsed):
        raise ValueError("missing timestamp")
    aware = [t.tzinfo is not None for t in parsed]
    if any(aware) and not all(aware):
        raise ValueError("do not mix naive and offset timestamps")
    zone = clock["timezone"]
    if all(aware):
        return pd.DatetimeIndex(pd.to_datetime(parsed, utc=True)).tz_convert(zone)
    return pd.DatetimeIndex(parsed).tz_localize(zone, ambiguous="raise", nonexistent="raise")


def validate_clock(clock):
    keys(clock, {"convention", "timezone"}, "clock")
    if clock.get("convention") not in {"standard", "civil", "utc"}:
        raise ValueError("clock.convention must be standard, civil or utc")
    zone = ZoneInfo(clock.get("timezone", ""))
    if clock["convention"] in {"standard", "utc"}:
        offsets = {datetime(y, m, 1, tzinfo=zone).utcoffset().total_seconds()
                   for y in (2020, 2023, 2024) for m in range(1, 13)}
        if len(offsets) != 1 or (clock["convention"] == "utc" and offsets != {0}):
            raise ValueError("standard/UTC clock requires an appropriate fixed-offset timezone")
    return dict(clock)


@dataclass
class Dataset:
    observations: pd.DataFrame
    weather: pd.DataFrame
    series: dict
    clock: dict
    provenance: dict

    def weather_for(self, series_id):
        key = self.series[series_id]["weather_id"]
        return self.weather[self.weather.weather_id == key].copy()


def validate(observations, weather, series, clock, provenance=None):
    clock = validate_clock(clock)
    obs, wx = observations.copy(), weather.copy()
    if not isinstance(series, dict) or not series or obs.empty:
        raise ValueError("nonempty series metadata and observations are required")
    if not {"series_id", "interval_start", "interval_end"}.issubset(obs):
        raise ValueError("observations require series_id, interval_start, interval_end")
    for name, default in [("energy_kWh", ""), ("split", "train"), ("quality", "valid")]:
        if name not in obs:
            obs[name] = default
    obs["series_id"] = obs.series_id.astype(str)
    if set(obs.series_id) != set(series):
        raise ValueError("series metadata must match observed series IDs exactly")
    for sid, metadata in series.items():
        if not isinstance(sid, str) or not sid.strip():
            raise ValueError("series IDs must be nonempty text")
        keys(metadata, META | {"zone_id", "model", "representation", "description"}, "series metadata")
        if any(not isinstance(metadata.get(k), str) or not metadata[k].strip() for k in META):
            raise ValueError(f"{sid}: required text metadata: {sorted(META)}")
        if metadata["source_type"] not in {"measured", "simulated"}:
            raise ValueError("source_type must be measured or simulated")
    for column in ["interval_start", "interval_end"]:
        obs[column] = timestamps(obs[column], clock)
    obs["duration_h"] = (obs.interval_end - obs.interval_start).dt.total_seconds() / 3600
    if not np.isfinite(obs.duration_h).all() or (obs.duration_h <= 0).any():
        raise ValueError("observation intervals must have positive finite duration")
    raw = obs.energy_kWh
    obs["energy_kWh"] = pd.to_numeric(raw.replace("", np.nan), errors="raise")
    if np.isinf(obs.energy_kWh).any() or (obs.energy_kWh.dropna() < 0).any():
        raise ValueError("targets must be finite nonnegative energy or missing; signed net exchange is unsupported")
    if not obs.split.isin(SPLITS).all() or not obs.quality.isin({"valid", "missing", "excluded"}).all():
        raise ValueError("unknown split or quality flag")
    for _, group in obs.groupby("series_id"):
        group = group.sort_values("interval_start")
        if any(a < b for a, b in zip(group.interval_start.iloc[1:], group.interval_end.iloc[:-1])):
            raise ValueError("overlapping or duplicate observation intervals")
    if not {"time", "temperature_C"}.issubset(wx) or wx.empty:
        raise ValueError("weather requires hourly time and temperature_C")
    if "weather_id" not in wx:
        wx["weather_id"] = "default"
    if "ghi_Wm2" not in wx:
        wx["ghi_Wm2"] = np.nan
    wx["time"] = timestamps(wx.time, clock)
    for column in ["temperature_C", "ghi_Wm2"]:
        wx[column] = pd.to_numeric(wx[column].replace("", np.nan), errors="raise")
    if not np.isfinite(wx.temperature_C).all() or np.isinf(wx.ghi_Wm2).any() or (wx.ghi_Wm2.dropna() < 0).any():
        raise ValueError("invalid temperature or irradiance")
    for wid, group in wx.groupby("weather_id"):
        group = group.sort_values("time")
        elapsed = group.time.diff().dropna().dt.total_seconds()
        if not elapsed.eq(3600).all():
            raise ValueError(f"{wid}: weather must be unique, contiguous hourly interval-start data")
    for sid, group in obs.groupby("series_id"):
        w = wx[wx.weather_id == series[sid]["weather_id"]]
        if w.empty:
            raise ValueError(f"{sid}: missing weather ID")
        first, end = w.time.min(), w.time.max() + pd.Timedelta(hours=1)
        alignment = (group.interval_start - first).dt.total_seconds() % 3600
        if ((group.interval_start < first).any() or (group.interval_end > end).any() or
                not alignment.eq(0).all() or not (group.duration_h % 1).eq(0).all()):
            raise ValueError(f"{sid}: weather must exactly cover each interval on hourly boundaries")
    return Dataset(obs.sort_values(["series_id", "interval_start"]).reset_index(drop=True),
                   wx.sort_values(["weather_id", "time"]).reset_index(drop=True), series, clock, provenance or {})


def monthly(dataset, sid):
    """Aggregate true hourly energy only when complete months have one split.

    Actual monthly bills are accepted directly. Partial/mixed-split months are
    rejected; they must never leak training data into a monthly validation bill.
    """
    data = dataset.observations[dataset.observations.series_id == sid].copy()
    starts = pd.DatetimeIndex(data.interval_start)
    data["period"] = starts.tz_localize(None).to_period("M").astype(str)
    records = []
    for period, group in data.groupby("period"):
        start = pd.Timestamp(period).tz_localize(dataset.clock["timezone"])
        end = start + pd.offsets.MonthBegin(1)
        if (group.interval_start.iloc[0] != start or group.interval_end.iloc[-1] != end or
                any(a != b for a, b in zip(group.interval_start.iloc[1:], group.interval_end.iloc[:-1])) or
                group.split.nunique() != 1):
            raise ValueError(f"{sid}/{period}: 5P requires a complete calendar month with a single split")
        values = group.energy_kWh
        energy = values.sum() if values.notna().all() else np.nan
        record = dict(series_id=sid, interval_start=start, interval_end=end, duration_h=(end-start).total_seconds()/3600,
                      energy_kWh=energy, split=group.split.iloc[0], quality="valid" if group.quality.eq("valid").all() else "excluded",
                      days=start.days_in_month)
        weather = dataset.weather_for(sid)
        record["temperature_C"] = weather[(weather.time >= start) & (weather.time < end)].temperature_C.mean()
        records.append(record)
    return pd.DataFrame(records)
