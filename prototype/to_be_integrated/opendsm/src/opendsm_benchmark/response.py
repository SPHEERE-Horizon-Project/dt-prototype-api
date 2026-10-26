"""
response.py - Daily temperature response of a fitted OpenDSM hourly model, per temporal cluster.

How OpenDSM 1.2.7 uses temperature (hourly EEmeter model, see its HourlyModel._add_temperature_bins
and _add_temperature_interactions): the training days are grouped into "temporal clusters" of
month x day-of-week combinations with similar load shapes; the hourly temperature is split into
bins with fixed edges (default 10, 30, 50, 65, 75, 90, 105 °F, merged when a bin holds too few
values); each bin has its own slope on temperature, globally and per temporal cluster, plus an
intercept per cluster x bin, and the outer bins get an exponential term. The prediction is
therefore a piecewise-linear function of temperature with knots at the bin edges, different for
every temporal cluster and hour of day - the same idea as change-point models with more knots.

To show it like the change-point models of energy_insight (daily average power vs daily mean
temperature), every cluster is evaluated on synthetic days: a representative month x weekday of
the cluster (the one with most model days), a constant temperature T all day, the cluster's mean
hourly irradiance; the 24 predicted hours are averaged into daily average power [kW].

    temperature_response(fitted, data, step)   one table: kind = "curve" (cluster, T_C, P_kW) and
                                               kind = "day" (every model day: cluster, T_C, P_kW)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from opendsm import eemeter as em

from .opendsm_runner import Fit, quiet
from .preprocess import PeriodData
from .settings import Settings


def _to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def cluster_table(model_json: str) -> pd.DataFrame:
    """month (1-12), day_of_week (0 = Monday), cluster."""
    return pd.DataFrame(json.loads(model_json)["temporal_clusters"], columns=["month", "day_of_week", "cluster"])


def knots_c(model_json: str) -> list[float]:
    edges = json.loads(model_json)["temperature_bin_edges"]
    return [round(_to_c(e), 2) for e in edges if np.isfinite(e)]


def temperature_response(fitted: Fit, data: PeriodData, settings: Settings, step: float = 1.0) -> pd.DataFrame:
    frame = data.frame
    dates = frame.index.tz_localize(None).normalize()
    on_model_day = dates.isin(data.model_days)
    f = frame[on_model_day]
    d = dates[on_model_day]
    days = pd.DataFrame({"T_C": f["temperature_C"].groupby(d).mean(), "P_kW": f["observed"].groupby(d).mean(),
                         "ghi_daily_kWh_m2": f["ghi"].groupby(d).sum() / 1000.0})
    days["month"], days["day_of_week"] = days.index.month, days.index.dayofweek
    clusters = cluster_table(fitted.model_json)
    days = days.reset_index(names="date").merge(clusters, on=["month", "day_of_week"], how="left")
    knots = knots_c(fitted.model_json)
    grid = np.arange(np.floor(days["T_C"].min()) - 1.0, np.ceil(days["T_C"].max()) + 1.0 + step / 2, step)
    hours = pd.Series(frame.index.tz_localize(None).hour, index=frame.index)
    rows = []
    for c, cd in days.groupby("cluster"):
        combo = cd.groupby(["month", "day_of_week"]).size().sort_values(ascending=False).index[0]
        first = cd[(cd["month"] == combo[0]) & (cd["day_of_week"] == combo[1])]["date"].min()
        sel = dates.isin(cd["date"])
        profile = frame.loc[sel, "ghi"].groupby(hours[sel].to_numpy()).mean().reindex(range(24)).fillna(0.0)
        idx = pd.date_range(first, periods=24, freq="h", tz=frame.index.tz)
        members = clusters[clusters["cluster"] == c]
        combos = "; ".join(f"{m}:{''.join(str(x) for x in sorted(g['day_of_week']))}" for m, g in members.groupby("month"))
        for T in grid:
            df = pd.DataFrame({"temperature": T * 9.0 / 5.0 + 32.0, "ghi": profile.to_numpy()}, index=idx)
            with quiet():
                model = em.HourlyModel.from_json(fitted.model_json)
                out = model.predict(em.HourlyReportingData(df, is_electricity_data=settings.is_electricity_data),
                                    ignore_disqualification=True)
            rows.append({"kind": "curve", "period": data.period, "cluster": int(c), "T_C": float(T),
                         "P_kW": float(out["predicted"].mean()), "ghi_daily_kWh_m2": float(profile.sum() / 1000.0),
                         "month": int(combo[0]), "day_of_week": int(combo[1]), "members": combos,
                         "knots_C": ";".join(str(k) for k in knots)})
    curves = pd.DataFrame(rows)
    days = days.assign(kind="day", period=data.period, knots_C=";".join(str(k) for k in knots))
    days["date"] = days["date"].dt.strftime("%Y-%m-%d")
    return pd.concat([curves, days], ignore_index=True)
