"""Locate the self-contained integration project's bundled inputs and Model 3.

The integration package contains the preserved Model 3 pipeline while the
project root contains shared example inputs. This module only resolves those
locations; it does not share or modify their equations.
"""

from __future__ import annotations

from pathlib import Path


def package_project_root() -> Path:
    """Return the copied project's root directory in an editable checkout."""

    return Path(__file__).resolve().parents[3]


def resolve_project_root(project_root: str | Path | None = None) -> Path:
    """Use an explicit root when supplied, otherwise use this checkout."""

    return package_project_root() if project_root is None else Path(project_root).resolve()


def example_data_dir(project_root: str | Path | None = None) -> Path:
    """Locate the single authoritative bundled example dataset."""

    root = resolve_project_root(project_root)
    standalone = root / "data" / "examples"
    if standalone.is_dir():
        return standalone
    raise FileNotFoundError(
        "Example inputs were not found. Expected data/examples in the project."
    )


def model3_pipeline_root() -> Path:
    """Return the embedded Model 3 pipeline and verification-data directory."""

    root = Path(__file__).resolve().parent / "model3"
    if (root / "model3.py").is_file():
        return root
    raise FileNotFoundError(f"Embedded Model 3 pipeline was not found at {root}")
