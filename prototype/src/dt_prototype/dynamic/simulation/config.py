"""Simulation run configuration.

Replaces the retained reference's global ``CONFIG`` singleton with an explicit, immutable
dataclass passed to the runner — no module-level state, so the core logic is
side-effect free and FastAPI-ready (NFR-04). Batch runs (FR-03) are simply
lists of :class:`SimulationConfig` objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


def season_mask(index: pd.DatetimeIndex, season: tuple[int, int]) -> np.ndarray:
    """Return the availability mask for a day-of-year season.

    ``season`` is ``(start_day_of_year, end_day_of_year)``.  Intervals whose
    start is after their end wrap over New Year (the usual heating-season
    convention).  Keeping this helper beside :class:`SimulationConfig`
    ensures the dynamic and quasi-steady-state runners apply identical
    availability rules.
    """
    day_of_year = index.dayofyear.to_numpy()
    start, end = season
    if start <= end:
        return (day_of_year >= start) & (day_of_year <= end)
    return (day_of_year >= start) | (day_of_year <= end)


@dataclass(frozen=True)
class SimulationConfig:
    """Settings for one simulation run.

    Attributes
    ----------
    model : str
        Thermal model name from the registry: ``"5R1C"`` or ``"7R2C"``
        (the retained reference aliases ``"1C"`` / ``"2C"`` accepted). FR-09/FR-10.
    latent : bool
        Solve the zone latent (humidity) balance and report latent loads.
    plants : bool
        If True, attach the heating/cooling systems named in the building
        input (GeoJSON attributes) and compute fuel/electricity use;
        if False, ideal loads only.
    heating_season, cooling_season : tuple of int
        (start_day_of_year, end_day_of_year) during which the corresponding
        conditioning is available; the heating interval wraps over new year.
    heating_max_power, cooling_max_power : float or None
        Plant capacity limits [W]; None = unlimited (pure ideal load).
        Cooling limit is negative.
    initial_temperature : float
        Initial thermal-mass/air temperature [°C].
    initial_specific_humidity : float
        Initial zone humidity ratio [kg/kg].
    sizing : str
        Plant sizing method when ``plants`` is on (EXTENDED):
        ``"design_day"`` runs heating/cooling design-day simulations with
        the selected thermal model; ``"static"`` uses the steady-state
        estimate of the base version. Explicit ``*_max_power`` values
        override both.
    dhw_tank : bool
        Route the DHW demand through an auto-sized storage tank between
        generator and draw-off (EXTENDED); False = instantaneous supply.
    pv_battery : bool
        Attach an auto-sized battery to buildings with PV and report grid
        exchange columns (EXTENDED).
    ahu_mode : {"extended", "basic"}
        AHU algorithm. ``"extended"`` enables recirculation, psychrometric
        saturation checks and explicit cooling/reheat coil accounting.
        ``"basic"`` reproduces the BASIC-version 100% outdoor-air algorithm
        with net sensible-coil accounting.
    """

    model: str = "7R2C"
    latent: bool = True
    plants: bool = False
    heating_season: tuple[int, int] = (288, 120)  # Oct 15 – Apr 30 (wraps)
    cooling_season: tuple[int, int] = (152, 273)  # Jun 1 – Sep 30
    heating_max_power: float | None = None
    cooling_max_power: float | None = None
    initial_temperature: float = 15.0
    initial_specific_humidity: float = 0.0105
    sizing: str = "design_day"
    dhw_tank: bool = True
    pv_battery: bool = False
    ahu_mode: Literal["extended", "basic"] = "extended"

    def __post_init__(self) -> None:
        """Validate settings whose accepted values are a closed set."""
        if self.ahu_mode not in {"extended", "basic"}:
            raise ValueError(
                "ahu_mode must be 'extended' or 'basic', "
                f"got {self.ahu_mode!r}"
            )
