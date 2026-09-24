"""Stochastic domestic hot water draw-off profiles (EXTENDED).

Port of the retained reference's "DHW calc" method (``reference_building.domestic_hot_water.
dhw_calc_calculation``): event-based draw-offs generated at 5-minute
resolution from the DHWcalc use categories (small/medium draw-offs, bath,
shower), each with its own daily temporal distribution and a lognormal or
normal flow-rate distribution, then resampled to the simulation time step
and rescaled to conserve the daily volume.

Use parameters are the retained reference's ``schedule_properties.domestic_hot_water_prop``.
"""

from __future__ import annotations

import numpy as np

# DHWcalc use categories (the retained reference schedule_properties), per draw-off type:
# share of daily volume, flow-rate pdf [l/min], daily temporal distribution
_DHW_USES: dict[str, dict] = {
    "small_drawoff": {
        "share": 0.14,
        "pdf": "lognormal",
        "mean": 15 / 60,
        "std": 1.0,
        "temporal": [0.01, 0.01, 0.01, 0.01, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05,
                     0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05,
                     0.05, 0.01],
    },
    "medium_drawoff": {
        "share": 0.36,
        "pdf": "normal",
        "mean": 360 / 60,
        "std": 2.0,
        "temporal": [0.01, 0.01, 0.01, 0.01, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05,
                     0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05,
                     0.05, 0.01],
    },
    "bath_tube": {
        "share": 0.10,
        "pdf": "normal",
        "mean": 480 / 60,
        "std": 2.0,
        "temporal": [0.0, 1e-7, 2e-7, 3e-7, 4e-7, 5e-7, 0.01031, 0.02062, 0.02577,
                     0.03093, 0.04639, 0.05155, 0.05155, 0.05155, 0.05155, 0.05155,
                     0.05155, 0.13402, 0.22680, 0.13402, 0.03093, 0.02062, 0.01031, 0.0],
    },
    "shower": {
        "share": 0.40,
        "pdf": "normal",
        "mean": 480 / 60,
        "std": 2.0,
        "temporal": [0.0, 1e-5, 2e-5, 3e-5, 0.03810, 0.14286, 0.23810, 0.14286,
                     0.03810, 0.01905, 0.01905, 0.01905, 0.01905, 0.01905, 0.01905,
                     0.01905, 0.01905, 0.02857, 0.07619, 0.07619, 0.02857, 0.01905,
                     0.01905, 0.0],
    },
}

_INTERNAL_STEP_MIN = 5  # internal generation resolution [min] (as the retained reference)


def _event_time_steps(
    rng: np.random.Generator, n_events: int, pdf_daily: np.ndarray, n_days: int
) -> np.ndarray:
    """Draw event time-step indices from a daily temporal distribution
    (the retained reference ``_event_distribution``: inverse-CDF sampling)."""
    guess = rng.random((n_days, n_events))
    cdf = np.cumsum(pdf_daily)
    positions = np.interp(guess, cdf, np.arange(len(cdf)))
    return np.round(positions).astype(int)


def stochastic_dhw_profile(
    daily_volume_m3: float,
    n_units: int = 1,
    time_steps_per_hour: int = 1,
    seed: int | None = None,
) -> np.ndarray:
    """Annual stochastic DHW draw-off profile (FR: EXTENDED DHW calc).

    Parameters
    ----------
    daily_volume_m3 : float
        Average daily draw-off volume per unit (dwelling) [m3/day].
    n_units : int
        Number of dwellings; profiles are generated independently per unit
        and summed (more units → smoother profile).
    time_steps_per_hour : int
        Output resolution (internally generated at 5 min).
    seed : int, optional
        Random seed for reproducibility.

    Returns
    -------
    numpy.ndarray
        Volume flow [m3/s], length ``8760 * time_steps_per_hour``; the mean
        daily volume equals ``daily_volume_m3 * n_units``.
    """
    if daily_volume_m3 <= 0.0 or n_units < 1:
        return np.zeros(8760 * time_steps_per_hour)

    rng = np.random.default_rng(seed)
    steps_hour = 60 // _INTERNAL_STEP_MIN
    steps_day = 24 * steps_hour
    n_days = 365
    daily_litres = daily_volume_m3 * 1000.0

    total = np.zeros(n_days * steps_day)
    for _ in range(n_units):
        for use in _DHW_USES.values():
            use_daily_litres = daily_litres * use["share"]
            n_events = max(1, int(round(use_daily_litres / use["mean"])))
            # resample the 24 h distribution to the internal step and normalise
            temporal = np.interp(
                np.arange(0, 24, 1 / steps_hour), np.arange(24), np.asarray(use["temporal"])
            )
            temporal = temporal / temporal.sum()
            events = _event_time_steps(rng, n_events, temporal, n_days)
            if use["pdf"] == "lognormal":
                m, v = use["mean"], use["std"]
                mu = np.log(m**2 / np.sqrt(v + m**2))
                sigma = np.sqrt(np.log(v / m**2 + 1.0))
                volumes = rng.lognormal(mu, sigma, (n_days, n_events))
            else:
                volumes = np.abs(rng.normal(use["mean"], use["std"], (n_days, n_events)))
            use_volume = np.zeros((n_days, steps_day))
            for e in range(n_events):
                use_volume[np.arange(n_days), events[:, e]] += volumes[:, e]
            # rescale so the rounding of event counts conserves the volume
            total_drawn = use_volume.sum()
            if total_drawn > 0.0:
                use_volume *= use_daily_litres * n_days / total_drawn
            total += use_volume.reshape(-1)

    # resample 5-min litres to the simulation step, convert to m3/s
    out_steps = 8760 * time_steps_per_hour
    group = len(total) // out_steps
    litres_per_step = total[: out_steps * group].reshape(out_steps, group).sum(axis=1)
    step_seconds = 3600.0 / time_steps_per_hour
    return litres_per_step / 1000.0 / step_seconds
