from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def reference_district(project_root: Path):
    from dt_prototype.common.preprocessing.building_input import preprocess_district

    data = project_root / "data" / "examples"
    return preprocess_district(
        data / "example_district.geojson",
        data / "ITA_Venezia-Tessera.161050_IGDG.epw",
        data / "archetypes.json",
        data / "schedules.json",
    )
