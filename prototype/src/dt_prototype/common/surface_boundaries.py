"""Optional thermal boundary overrides, independent of physical construction."""

from .constants import EXTERNAL_SURFACE_TYPES


def validate_boundary_condition(value: str) -> None:
    """Keep the small input vocabulary explicit; unknown conditions must fail."""
    if value not in ("auto", "adiabatic"):
        raise ValueError(
            f"boundary_condition must be 'auto' or 'adiabatic', got {value!r}"
        )


def is_external_surface(surface_type: str, boundary_condition: str = "auto") -> bool:
    """Whether the surface exchanges heat with outdoors/ground.

    ``auto`` retains the surface-type convention, including adiabatic internal
    mass. An explicit override does not change construction, area or glazing.
    """
    return boundary_condition != "adiabatic" and surface_type in EXTERNAL_SURFACE_TYPES
