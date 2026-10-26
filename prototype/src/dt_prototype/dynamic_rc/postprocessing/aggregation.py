"""Temporal and portfolio aggregation of simulation results (FR-13, FR-14, FR-16).

Migrated from ``reference_building._auxiliary_function_for_monthly_calc`` and the
district summary logic of ``reference_ubem.city``, generalised to pandas
resampling over the runner's result DataFrames.

Conventions: power columns [W] are integrated to energy [kWh] over the
aggregation period; state columns (temperatures [°C], humidity [-]) are
averaged.
"""

from __future__ import annotations

import pandas as pd

# state columns are averaged; every other column is treated as power [W]
_STATE_KEYWORDS = ("temperature", "humidity", "_ach", "_soc")
# per-zone columns (see simulation.runner.run_building's zone_upper_*/
# zone_lower_* columns) duplicate the already-inclusive whole-building
# column of the same base name — excluded from cross-building summation to
# avoid double counting at the portfolio level.
_ZONE_COLUMN_PREFIX = "zone_"


def _timestep_hours(df: pd.DataFrame) -> float:
    """Simulation time step [h] inferred from the DataFrame index."""
    if len(df) < 2:
        raise ValueError("Result DataFrame needs at least two rows")
    return (df.index[1] - df.index[0]).total_seconds() / 3600.0


def _split_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Partition columns into (state, power) lists by naming convention."""
    state = [c for c in df.columns if any(k in c for k in _STATE_KEYWORDS)]
    power = [c for c in df.columns if c not in state]
    return state, power


def aggregate(results: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Aggregate a results DataFrame to a coarser temporal resolution.

    Power columns [W] become energy [kWh] per period; state columns are
    averaged (suffixes ``_kWh`` / ``_mean`` are appended).

    Parameters
    ----------
    results : pandas.DataFrame
        Time-indexed runner output (see ``run_building``).
    freq : str
        Pandas offset alias: ``"D"`` for daily, ``"MS"`` for monthly.

    Returns
    -------
    pandas.DataFrame
    """
    dt_h = _timestep_hours(results)
    state_cols, power_cols = _split_columns(results)
    parts = []
    if power_cols:
        energy = results[power_cols].resample(freq).sum() * dt_h / 1000.0
        parts.append(energy.add_suffix("_kWh"))
    if state_cols:
        parts.append(results[state_cols].resample(freq).mean().add_suffix("_mean"))
    return pd.concat(parts, axis=1)


def to_daily(results: pd.DataFrame) -> pd.DataFrame:
    """Hourly/sub-hourly → daily aggregation (FR-13)."""
    return aggregate(results, "D")


def to_monthly(results: pd.DataFrame) -> pd.DataFrame:
    """Hourly/sub-hourly → monthly aggregation (FR-14)."""
    return aggregate(results, "MS")


def portfolio_time_series(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Sum the power columns across buildings into one district time series
    (FR-16). State columns are dropped (zone temperatures are not additive).
    Per-zone columns (``zone_upper_*``/``zone_lower_*``) are excluded too:
    they duplicate their building's own whole-building column and would
    otherwise be double-counted on top of it.

    Parameters
    ----------
    results : dict
        Building name → runner output DataFrame.

    Returns
    -------
    pandas.DataFrame
        District-level power series [W] at the simulation resolution.
    """
    if not results:
        raise ValueError("Empty results dictionary")
    total = None
    for df in results.values():
        _, power_cols = _split_columns(df)
        power_cols = [c for c in power_cols if not c.startswith(_ZONE_COLUMN_PREFIX)]
        contribution = df[power_cols]
        total = contribution if total is None else total.add(contribution, fill_value=0.0)
    return total
