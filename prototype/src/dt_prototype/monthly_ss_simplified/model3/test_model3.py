"""Regression and physical-bound smoke tests for Model 3."""

from pathlib import Path
from tempfile import TemporaryDirectory

from .model3 import run


def main():
    root = Path(__file__).resolve().parent
    with TemporaryDirectory() as temp_dir:
        forward, parameters, fitted, metrics = run(root / "example_data", temp_dir)

    assert len(forward) == 12
    assert len(parameters) == 2
    assert len(fitted) == 24
    assert len(metrics) == 2
    for row in forward:
        assert row["useful_heating_kWh"] >= 0
        assert row["useful_cooling_kWh"] >= 0
        assert row["useful_dhw_kWh"] >= 0
        assert row["solar_thermal_kWh"] <= row["useful_dhw_kWh"] + 1e-9
        assert row["pv_self_used_kWh"] <= row["pv_generation_kWh"] + 1e-9
        assert row["delivered_electricity_kWh"] >= -1e-9
        assert abs(row["carrier_balance_residual_kWh"]) < 1e-7
        assert 0 <= row["eta_heating"] <= 1.0 + 1e-9
        assert 0 <= row["eta_cooling"] <= 1.0 + 1e-9
    for fit in parameters:
        assert fit["heating_change_point_C"] <= fit["cooling_change_point_C"]
        assert fit["observations"] == 12
    print("PASS: forward bounds, carrier balance, PV/ST caps, and calibration structure")


if __name__ == "__main__":
    main()
