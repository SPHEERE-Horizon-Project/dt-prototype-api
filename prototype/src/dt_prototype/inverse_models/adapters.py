"""Read measured interval CSVs or immutable simulation outputs; never rerun physics."""
from pathlib import Path

import pandas as pd
import numpy as np

from .data import SPLITS, csv, keys, load_json, sha, timestamps, validate, validate_clock


def _resample_subhourly(obs):
    """Sum genuine interval energy; incomplete hours remain missing, never imputed."""
    result = []
    for sid, group in obs.groupby("series_id", sort=False):
        duration = (group.interval_end-group.interval_start).dt.total_seconds()/3600
        if not (duration < 1).any():
            result.append(group)
            continue
        if (duration <= 0).any() or (duration > 1).any():
            raise ValueError("subhourly series cannot mix bills or invalid interval durations")
        group = group.sort_values("interval_start").copy()
        group["hour"] = group.interval_start.dt.tz_convert("UTC").dt.floor("h").dt.tz_convert(group.interval_start.dt.tz)
        rows = []
        for hour, part in group.groupby("hour", sort=True):
            end = hour+pd.Timedelta(hours=1)
            if (part.interval_end > end).any() or any(a < b for a,b in zip(part.interval_start.iloc[1:],part.interval_end.iloc[:-1])):
                raise ValueError("overlapping subhourly intervals or an interval crossing an hour")
            if part.split.nunique() != 1:
                raise ValueError("a training/validation split cannot cut an hour")
            complete = (part.interval_start.iloc[0] == hour and part.interval_end.iloc[-1] == end and
                        all(a == b for a,b in zip(part.interval_start.iloc[1:],part.interval_end.iloc[:-1])))
            energy = pd.to_numeric(part.energy_kWh.replace("",np.nan),errors="raise")
            if np.isinf(energy).any() or (energy.dropna() < 0).any():
                raise ValueError("subhourly energy must be nonnegative finite or missing")
            rows.append(dict(series_id=sid,interval_start=hour,interval_end=end,
                energy_kWh=energy.sum() if complete and energy.notna().all() else np.nan,
                split=part.split.iloc[0],quality="valid" if complete and energy.notna().all() and part.quality.eq("valid").all() else "missing"))
        result.append(pd.DataFrame(rows))
    return pd.concat(result,ignore_index=True)


def _split(data, source, clock):
    if "validation_end" in source and "train_end" not in source:
        raise ValueError("validation_end requires train_end")
    if "train_end" not in source:
        return data
    data = data.copy()
    protected = data.split.isin(["excluded", "predict"])
    original = data.split.copy()
    train_end = timestamps([source["train_end"]], clock)[0]
    validation_end = timestamps([source["validation_end"]], clock)[0] if "validation_end" in source else None
    for boundary in [train_end, validation_end]:
        if boundary is not None and ((data.interval_start < boundary) & (data.interval_end > boundary)).any():
            raise ValueError("split boundaries must not cut an observation/bill")
    if validation_end is not None and validation_end <= train_end:
        raise ValueError("validation_end must be after train_end")
    data["split"] = "test" if validation_end is not None else "validation"
    if validation_end is not None:
        data.loc[data.interval_end <= validation_end, "split"] = "validation"
    data.loc[data.interval_end <= train_end, "split"] = "train"
    data.loc[protected, "split"] = original[protected]
    return data


def load_dataset(settings, base, simulation_results=None):
    source = settings["source"]
    keys(source, {"type", "observations", "weather", "series", "results", "project_config", "resolution",
                  "target", "buildings", "models", "carrier", "meter_boundary_id", "train_end", "validation_end"}, "source")
    if "validation_end" in source and "train_end" not in source:
        raise ValueError("validation_end requires train_end")
    if source.get("type") == "csv":
        keys(source, {"type", "observations", "weather", "series", "train_end", "validation_end"}, "CSV source")
        obs_path, wx_path = base / source["observations"], base / source["weather"]
        clock = validate_clock(settings["clock"])
        obs, wx = csv(obs_path), csv(wx_path)
        required = {"series_id", "interval_start", "interval_end"}
        allowed = required | {"energy_kWh", "split", "quality", "duration_h"}
        if not required.issubset(obs) or set(obs)-allowed:
            raise ValueError(f"observation CSV columns: missing {sorted(required-set(obs))}, unknown {sorted(set(obs)-allowed)}")
        if not {"time", "temperature_C"}.issubset(wx) or set(wx)-{"weather_id", "time", "temperature_C", "ghi_Wm2"}:
            raise ValueError("weather CSV requires time, temperature_C and only optional weather_id, ghi_Wm2")
        for column in ["interval_start", "interval_end"]:
            obs[column] = timestamps(obs[column], clock)
        for column, default in [("split","train"),("quality","valid"),("energy_kWh","")]:
            if column not in obs:
                obs[column] = default
        # Validate flags before aggregation or date cutoffs can conceal a typo.
        if not obs.split.isin(SPLITS).all() or not obs.quality.isin({"valid", "missing", "excluded"}).all():
            raise ValueError("unknown split or quality flag")
        if "duration_h" in obs:
            supplied = pd.to_numeric(obs.duration_h, errors="raise")
            elapsed = (obs.interval_end-obs.interval_start).dt.total_seconds()/3600
            if not np.isfinite(supplied).all() or not np.allclose(supplied, elapsed, rtol=0, atol=1e-10):
                raise ValueError("duration_h must match the explicit interval boundaries")
        obs = _resample_subhourly(obs)
        if "train_end" in source:
            obs = _split(obs, source, clock)
        return validate(obs, wx, source["series"], clock,
                        {str(obs_path.resolve()): sha(obs_path), str(wx_path.resolve()): sha(wx_path)})
    if source.get("type") not in {"energy_run", "thermal_monthly"}:
        raise ValueError("source.type must be csv, energy_run or thermal_monthly")
    keys(source, {"type", "results", "project_config", "resolution", "target", "buildings", "models",
                  "carrier", "meter_boundary_id", "train_end", "validation_end"}, "simulation source")
    for name in ["buildings", "models"]:
        if name in source:
            values = source[name]
            if (not isinstance(values, list) or not values or
                    any(not isinstance(v, str) or not v.strip() for v in values) or len(values) != len(set(values))):
                raise ValueError(f"{name} must be a nonempty list of unique exact text identifiers")
    if simulation_results is not None and source["type"] != "energy_run":
        raise ValueError("forward analysis requires source.type=energy_run")
    from dt_prototype.common.project import ProjectInputs
    from dt_prototype.common.preprocessing.weather import read_epw
    from dt_prototype.common.output_paths import output_component

    directory = Path(simulation_results) if simulation_results is not None else base / source["results"]
    project = ProjectInputs.load(base / source["project_config"])
    manifest_path = directory / "manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("status") != "complete" or manifest.get("input_hashes") != project.hashes():
        raise ValueError("simulation must be complete with matching project/input hashes")
    year = project.configuration["inputs"]["calendar_year"]
    wx, info = read_epw(project.paths["weather_epw"], year)
    offset = float(info["timezone"])
    if offset != int(offset) and "clock" not in settings:
        raise ValueError("fractional EPW offset: provide an explicit matching standard-time clock")
    default_zone = "UTC" if offset == 0 else f"Etc/GMT{int(-offset):+d}"
    clock = settings.get("clock", {"convention": "standard", "timezone": default_zone})
    if clock["convention"] != "standard" or pd.Timestamp(f"{year}-01-01", tz=clock["timezone"]).utcoffset().total_seconds()/3600 != offset:
        raise ValueError("simulation clock must preserve the EPW standard-time offset")
    weather = pd.DataFrame({"time": wx.index, "temperature_C": wx.temp_air.to_numpy(),
                            "ghi_Wm2": wx.ghi.to_numpy(), "weather_id": "simulation_weather"})
    target = source.get("target", "grid_import_kWh")
    targets = {"grid_import_kWh": ("electricity", "electricity_grid_import"),
               "grid_export_kWh": ("electricity", "electricity_grid_export"),
               "gross_electricity_kWh": ("electricity", "electricity_gross_consumption"),
               "pv_generation_kWh": ("electricity", "pv_generation"),
               **{k: ("useful_sensible", k) for k in ["zone_heating_kWh", "zone_cooling_kWh", "ahu_heating_kWh", "ahu_cooling_kWh", "dhw_kWh", "heating_kWh", "cooling_kWh"]}}
    if target not in targets and not (target.endswith("_kWh") and source.get("carrier") and source.get("meter_boundary_id")):
        raise ValueError("unknown energy target; supply explicit carrier and meter_boundary_id for another kWh target")
    carrier, boundary = targets.get(target, (source.get("carrier"), source.get("meter_boundary_id")))
    carrier, boundary = source.get("carrier", carrier), source.get("meter_boundary_id", boundary)
    provenance = {str(manifest_path.resolve()): sha(manifest_path), "project_inputs": project.hashes()}
    resolution = source.get("resolution", "monthly")
    if resolution not in {"monthly", "hourly"} or (source["type"] == "thermal_monthly" and resolution != "monthly"):
        raise ValueError("unsupported simulation resolution")
    frames, metadata = [], {}
    if resolution == "monthly":
        path = directory / ("energy_monthly.csv" if source["type"] == "energy_run" else "monthly.csv")
        frame = pd.read_csv(path, dtype={"building_id": str}, keep_default_na=False)
        if "model" not in frame:
            frame["model"] = manifest["engine"]
        if target not in frame:
            raise ValueError(f"requested energy target {target!r} is absent from {path.name}")
        # Thermal VBDD exports have distinct zone rows as well as collapsed
        # alternatives; combining their identities creates overlapping bills.
        if "zone_id" not in frame:
            frame["zone_id"] = ""
        provenance[str(path.resolve())] = sha(path)
        groups = frame.groupby(["building_id", "model", "representation", "zone_id"], sort=True)
    else:
        groups = []
        for case in manifest["cases"]:
            if case["resolution"] != "dynamic":
                continue
            bid, model, rep = str(case["building_id"]), case["model"], case["representation"]
            if source.get("buildings") and bid not in source["buildings"]:
                continue
            if source.get("models") and model not in source["models"]:
                continue
            path = directory / "cases" / output_component(bid) / output_component(model) / "energy_intervals.csv.gz"
            group = pd.read_csv(path)
            time = pd.to_datetime(group.time)
            group["interval_start"] = time.dt.floor("h")
            aggregated = group.groupby("interval_start")[[target, "duration_h"]].sum(min_count=1)
            if not aggregated.duration_h.eq(1).all():
                raise ValueError("dynamic source must contain complete energy-conserving hours")
            group = aggregated.reset_index()
            provenance[str(path.resolve())] = sha(path)
            groups.append(((bid, model, rep, ""), group))
    for (bid, model, rep, zone), group in groups:
        if source.get("buildings") and bid not in source["buildings"]:
            continue
        if source.get("models") and model not in source["models"]:
            continue
        sid = f"{bid}/{model}/{rep}/{target}"
        if zone:
            sid = f"{bid}/{model}/{rep}/zone={zone}/{target}"
        if resolution == "monthly":
            start = pd.to_datetime(group.period_id + "-01")
            end = start + pd.offsets.MonthBegin(1)
        else:
            start, end = group.interval_start, group.interval_start + pd.Timedelta(hours=1)
        data = pd.DataFrame({"series_id": sid, "interval_start": list(start), "interval_end": list(end),
                             "energy_kWh": pd.to_numeric(group[target]).to_numpy(), "split": "train", "quality": "valid"})
        for column in ["interval_start", "interval_end"]:
            data[column] = timestamps(data[column], clock)
        frames.append(_split(data, source, clock))
        scenario = next((c.get("scenario_id", "simulation") for c in manifest.get("cases", [])
                         if str(c["building_id"]) == bid and c["model"] == model and c["representation"] == rep), "simulation")
        metadata[sid] = dict(source_type="simulated", source_id=directory.name, building_id=bid,
                             scenario_id=scenario, carrier=carrier, meter_boundary_id=boundary,
                             weather_id="simulation_weather", model=model, representation=rep)
        if zone:
            metadata[sid]["zone_id"] = str(zone)
    if not frames:
        raise ValueError("no simulation series match the requested models/buildings/resolution")
    for selector, field in [("buildings", "building_id"), ("models", "model")]:
        unmatched = set(source.get(selector, [])) - {item[field] for item in metadata.values()}
        if unmatched:
            raise ValueError(f"requested {selector} are absent from the selected source: {sorted(unmatched)}")
    return validate(pd.concat(frames, ignore_index=True), weather, metadata, clock, provenance)
