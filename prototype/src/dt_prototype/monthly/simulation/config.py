"""Configuration for the ISO 13790 monthly semi-stationary calculation."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


def season_mask(index: pd.DatetimeIndex, season: tuple[int, int]) -> np.ndarray:
    """Return the day-of-year availability mask, including seasons spanning New Year."""
    days = index.dayofyear.to_numpy()
    start, end = season
    return (days >= start) & (days <= end) if start <= end else (days >= start) | (days <= end)


@dataclass(frozen=True)
class SimulationConfig:
    """The small set of assumptions that affect monthly sensible demand."""

    heating_season: tuple[int, int] = (288, 120)
    cooling_season: tuple[int, int] = (152, 273)
    ahu_mode: Literal["extended", "basic"] = "extended"
    initial_temperature: float = 15.0
    initial_specific_humidity: float = 0.0105

    def __post_init__(self) -> None:
        if self.ahu_mode not in {"extended", "basic"}:
            raise ValueError("ahu_mode must be 'extended' or 'basic'")
