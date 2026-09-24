"""EN 16798-1 adaptive comfort categories (EXTENDED).

Classifies each time step of a simulation into the EN 16798-1 comfort
categories using the adaptive model for the cooling/mid seasons:

    T_comf = 0.33 * T_rm + 18.8        (10 °C <= T_rm <= 30 °C)

with the exponentially weighted running mean outdoor temperature T_rm
(alpha = 0.8). Category bands around T_comf (operative temperature):
Cat I  +2/-3 K, Cat II +3/-4 K, Cat III +4/-5 K, Cat IV outside.
When T_rm is below the adaptive model's validity (heating season), fixed
operative bands for normal-activity spaces are used instead:
Cat I 21-25 °C, Cat II 20-26 °C, Cat III 19-27 °C.

EXTENSION POINT: PMV-based categories for fully mechanically cooled
buildings.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_ALPHA = 0.8
_ADAPTIVE_T_RM_MIN = 10.0  # [°C] validity of the adaptive model
_ADAPTIVE_T_RM_MAX = 30.0
# (upper offset, lower offset) around T_comf per category [K]
_ADAPTIVE_BANDS = {1: (2.0, -3.0), 2: (3.0, -4.0), 3: (4.0, -5.0)}
# fixed operative bands for the heating season (normal activity, cat I-III)
_WINTER_BANDS = {1: (21.0, 25.0), 2: (20.0, 26.0), 3: (19.0, 27.0)}


def running_mean_outdoor_temperature(daily_mean: np.ndarray, alpha: float = _ALPHA) -> np.ndarray:
    """Exponentially weighted running mean outdoor temperature [°C]
    (EN 16798-1), one value per day.

    Parameters
    ----------
    daily_mean : numpy.ndarray
        Daily mean outdoor temperatures [°C].
    alpha : float
        Weighting constant (standard value 0.8).

    Returns
    -------
    numpy.ndarray
        Running mean series, same length (day 0 uses its own mean).
    """
    t_rm = np.empty_like(daily_mean, dtype=float)
    t_rm[0] = daily_mean[0]
    for d in range(1, len(daily_mean)):
        t_rm[d] = (1.0 - alpha) * daily_mean[d - 1] + alpha * t_rm[d - 1]
    return t_rm


def en16798_category_series(
    operative_temperature: pd.Series, outdoor_temperature: pd.Series
) -> pd.Series:
    """Per-time-step EN 16798-1 comfort category (1, 2, 3 or 4).

    Parameters
    ----------
    operative_temperature : pandas.Series
        Zone operative temperature [°C] (runner output column).
    outdoor_temperature : pandas.Series
        Outdoor air temperature [°C] on the same index.

    Returns
    -------
    pandas.Series
        Integer category per step (4 = outside category III).
    """
    index = operative_temperature.index
    steps_day = int(round(86400.0 / (index[1] - index[0]).total_seconds()))
    n_days = len(index) // steps_day
    daily = outdoor_temperature.to_numpy()[: n_days * steps_day].reshape(n_days, steps_day)
    t_rm_day = running_mean_outdoor_temperature(daily.mean(axis=1))
    t_rm = np.repeat(t_rm_day, steps_day)[: len(index)]

    op = operative_temperature.to_numpy()
    adaptive = t_rm >= _ADAPTIVE_T_RM_MIN
    t_comf = 0.33 * np.clip(t_rm, _ADAPTIVE_T_RM_MIN, _ADAPTIVE_T_RM_MAX) + 18.8

    category = np.full(len(op), 4, dtype=int)
    for cat in (3, 2, 1):  # tightening order so the best category wins
        up, low = _ADAPTIVE_BANDS[cat]
        in_adaptive = adaptive & (op <= t_comf + up) & (op >= t_comf + low)
        t_low, t_up = _WINTER_BANDS[cat]
        in_winter = ~adaptive & (op >= t_low) & (op <= t_up)
        category[in_adaptive | in_winter] = cat
    return pd.Series(category, index=index, name="en16798_category")


def comfort_kpis(
    results: pd.DataFrame,
    outdoor_temperature: pd.Series,
    occupied: pd.Series | np.ndarray | None = None,
    operative_temperature_column: str = "operative_temperature",
) -> dict[str, float]:
    """EN 16798-1 comfort KPIs of one building (or one zone) run.

    Parameters
    ----------
    results : pandas.DataFrame
        Runner output (uses ``operative_temperature_column``).
    outdoor_temperature : pandas.Series
        Outdoor air temperature [°C] on the same index (e.g.
        ``weather.df["temp_air"]``).
    occupied : array-like of bool, optional
        Occupancy mask; when omitted, all time steps are evaluated.
    operative_temperature_column : str
        Column of ``results`` to evaluate — the whole-building
        ``"operative_temperature"`` by default, or a per-zone column (e.g.
        ``"zone_upper_operative_temperature"``) for a two-zone building
        (see ``preprocessing.geometry``'s two-zone convention), since
        comfort is a per-space concept and each zone's own temperature is
        more meaningful than the cross-zone average.

    Returns
    -------
    dict
        ``cat_i_fraction`` .. ``cat_iv_fraction`` (of occupied hours),
        ``hours_outside_cat_ii`` and ``hours_outside_cat_iii`` (absolute),
        ``mean_category``.
    """
    categories = en16798_category_series(
        results[operative_temperature_column], outdoor_temperature
    )
    if occupied is not None:
        categories = categories[np.asarray(occupied, dtype=bool)]
    if len(categories) == 0:
        raise ValueError("comfort_kpis: no occupied time steps to evaluate")

    dt_hours = (results.index[1] - results.index[0]).total_seconds() / 3600.0
    total = len(categories)
    fractions = {
        f"cat_{label}_fraction": float((categories == cat).sum()) / total
        for cat, label in ((1, "i"), (2, "ii"), (3, "iii"), (4, "iv"))
    }
    return {
        **fractions,
        "hours_outside_cat_ii": float((categories > 2).sum()) * dt_hours,
        "hours_outside_cat_iii": float((categories > 3).sum()) * dt_hours,
        "mean_category": float(categories.mean()),
    }
