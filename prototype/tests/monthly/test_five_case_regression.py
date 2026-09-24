from pathlib import Path

import pytest

from dt_prototype.common.preprocessing.building_input import preprocess_district
from dt_prototype.monthly.run import annual_summary, run_portfolio


DATA = Path(__file__).resolve().parents[2] / "data" / "examples"

# MWh annual values established by the prior QSS-vs-dynamic validation.
EXPECTED_MWH = {
    "Test building 1": (320.081, 72.104),
    "Test building 2": (138.054, 34.289),
    "Test building 3": (304.314, 37.863),
    "Test building 4": (1159.575, 84.637),
    "Test building 5": (2931.188, 269.089),
}


def test_five_case_annual_qss_regression() -> None:
    district = preprocess_district(
        DATA / "example_district.geojson",
        DATA / "ITA_Venezia-Tessera.161050_IGDG.epw",
        DATA / "archetypes.json",
        DATA / "schedules.json",
    )
    summary = annual_summary(run_portfolio(district)) / 1000.0
    assert set(summary.index) == set(EXPECTED_MWH)
    for building, (heating, cooling) in EXPECTED_MWH.items():
        assert summary.loc[building, "total_sensible_heating_demand_kWh"] == pytest.approx(heating, abs=0.002)
        assert summary.loc[building, "total_sensible_cooling_demand_kWh"] == pytest.approx(cooling, abs=0.002)
