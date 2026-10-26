"""Energy_carriers: shared systems, renewables and impact accounting."""

from .config import EnergyConfig, PerformanceCurve
from .engine import EnergyResult, aggregate_inputs, calculate

__version__ = "1.0.0"
__all__ = ["EnergyConfig", "PerformanceCurve", "EnergyResult", "aggregate_inputs", "calculate"]
