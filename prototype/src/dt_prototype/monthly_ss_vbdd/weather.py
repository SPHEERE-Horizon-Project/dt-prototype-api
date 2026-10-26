"""Monthly orientation radiation and transparent temperature-only surrogates."""
from dataclasses import replace
import numpy as np
import pandas as pd


def monthly_weather(weather) -> pd.DataFrame:
    index = weather.df.index
    if index.has_duplicates or not index.is_monotonic_increasing:
        raise ValueError("weather timestamps must be unique and ordered")
    step_h = weather.timestep_seconds / 3600
    if len(index) > 1 and not np.all(index[1:] - index[:-1] == pd.Timedelta(hours=step_h)):
        raise ValueError("weather timestamps must be continuous")
    records = []
    for period, group in weather.df.groupby(index.to_period("M")):
        hours = len(group) * step_h
        if hours != period.days_in_month * 24:
            raise ValueError(f"incomplete weather month {period}")
        row = dict(period_id=str(period), days=period.days_in_month, hours=hours,
                   outdoor_temp_C=float(group.temp_air.mean()))
        for label, az, tilt in [("N",0,90),("E",90,90),("S",180,90),("W",270,90),("HOR",0,0)]:
            glob, _ = weather.irradiance_columns(az, tilt)
            values = group[glob].to_numpy()
            if not np.isfinite(values).all() or (values < 0).any():
                raise ValueError(f"invalid irradiance {glob}")
            row[f"solar_{label}_kWh_m2"] = float(values.sum()*step_h/1000)
            row[f"solar_{label}_W_m2"] = float(values.mean())
        records.append(row)
    return pd.DataFrame(records)


def linear_fit(temperature, power) -> dict:
    x, y = np.asarray(temperature, float), np.asarray(power, float)
    if len(x) < 3 or not np.isfinite(x).all() or not np.isfinite(y).all() or np.ptp(x) < 1e-6:
        raise ValueError("solar fit requires at least three finite, varying temperatures")
    slope, intercept = np.polyfit(x, y, 1)
    residual = y - (intercept + slope*x)
    sst = np.sum((y-y.mean())**2)
    return dict(intercept_W=float(intercept), slope_W_K=float(slope),
                RMSE_W=float(np.sqrt(np.mean(residual**2))),
                R2=float(1-np.sum(residual**2)/sst) if sst > 0 else None,
                minimum_temperature_C=float(x.min()), maximum_temperature_C=float(x.max()),
                observations=len(x))


def temperature_linear_solar(rows):
    """Fit each case's net solar gain from weather/envelope only, never demand.

    Net solar includes the shared opaque longwave loss and can be negative.
    These coefficients are local to the supplied climate, envelope and year.
    """
    result, diagnostics = [], []
    for case in dict.fromkeys(r.case_id for r in rows):
        selected = [r for r in rows if r.case_id == case]
        fit = linear_fit([r.outdoor_temp_C for r in selected], [r.solar_gain_W for r in selected])
        diagnostics.append(dict(case_id=case, **fit))
        result.extend(replace(r, solar_gain_W=fit['intercept_W']+fit['slope_W_K']*r.outdoor_temp_C) for r in selected)
    return result, pd.DataFrame(diagnostics)


def orientation_multipliers(monthly: pd.DataFrame) -> pd.DataFrame:
    """Monthly POA/horizontal energy ratios; null means a zero denominator."""
    out = monthly[['period_id']].copy()
    for orientation in ('N','E','S','W'):
        denominator = monthly.solar_HOR_kWh_m2.replace(0, np.nan)
        out[f'{orientation}_to_horizontal'] = monthly[f'solar_{orientation}_kWh_m2']/denominator
    return out
