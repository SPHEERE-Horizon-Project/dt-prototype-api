"""Embedded Model 3 simulation and calibration pipeline.

The calculation module is preserved as an independent implementation inside
the integration package.  The surrounding DT-Prototype adapters translate
shared inputs and outputs without replacing its equations.
"""

from .model3 import run, run_forward

__all__ = ["run", "run_forward"]
