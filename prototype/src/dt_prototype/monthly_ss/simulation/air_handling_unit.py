"""AHU parameters used by the monthly sensible heat balance."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AirHandlingUnit:
    """Sensible heat-recovery and supply-temperature assumptions for an AHU."""

    eta_sensible: float = 0.5
    t_sup_heating: float = 20.0
    t_sup_cooling: float = 16.0
    outdoor_air_ratio: float = 1.0

    @classmethod
    def from_dict(cls, spec: dict, mode: str = "extended") -> "AirHandlingUnit":
        """Create the monthly model inputs from a schedule's ``ahu`` block."""
        ratio = 1.0 if mode == "basic" else float(spec.get("outdoor_air_ratio", 1.0))
        if not 0.0 < ratio <= 1.0:
            raise ValueError(f"outdoor_air_ratio must be in (0, 1], got {ratio}")
        return cls(
            eta_sensible=float(spec.get("sensible_recovery_eff", 0.5)),
            t_sup_heating=float(spec.get("supply_temperature_heating", 20.0)),
            t_sup_cooling=float(spec.get("supply_temperature_cooling", 16.0)),
            outdoor_air_ratio=ratio,
        )
