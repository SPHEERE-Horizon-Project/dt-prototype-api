"""Tests for the weather preprocessing module (FR-05, FR-12)."""

from __future__ import annotations

import numpy as np

from dt_prototype.common.preprocessing.weather import WeatherData, process_epw, read_epw


def test_epw_parsing(data_dir):
    """The EPW reader extracts site metadata and exactly 8760 hourly rows."""
    df, meta = read_epw(data_dir / "ITA_Venezia-Tessera.161050_IGDG.epw", year=2023)
    assert len(df) == 8760
    assert abs(meta["latitude"] - 45.5) < 0.1
    assert abs(meta["timezone"] - 1.0) < 0.01
    assert df["temp_air"].between(-30, 45).all()
    assert df["relative_humidity"].between(0, 1).all()


def test_specific_humidity_plausible(weather):
    """Derived humidity ratios stay within the physically plausible range."""
    x = weather.df["specific_humidity"]
    assert (x > 0).all() and (x < 0.030).all()


def test_solar_orientation_asymmetry(weather):
    """At a northern-hemisphere site the south facade receives more annual
    irradiation than the north facade (validates the solar model)."""
    south_col, _ = weather.irradiance_columns(azimuth=180.0, tilt=90.0)
    north_col, _ = weather.irradiance_columns(azimuth=0.0, tilt=90.0)
    assert weather.df[south_col].sum() > 1.5 * weather.df[north_col].sum()


def test_horizontal_bin_used_for_roofs(weather):
    """Low-tilt surfaces map to the horizontal irradiance bin."""
    glob, direct = weather.irradiance_columns(azimuth=123.0, tilt=0.0)
    assert glob == "poa_glob_az0_t0" and direct == "poa_dir_az0_t0"


def test_weather_csv_round_trip(weather, tmp_path):
    """WeatherData serialises to CSV + metadata sidecar and reloads equal
    (the explicit preprocessing→simulation handoff, FR-08)."""
    path = tmp_path / "weather.csv"
    weather.to_csv(path)
    reloaded = WeatherData.from_csv(path)
    assert reloaded.n_steps == weather.n_steps
    assert abs(reloaded.average_dt_air_sky - weather.average_dt_air_sky) < 1e-9
    np.testing.assert_allclose(
        reloaded.df["temp_air"].to_numpy(), weather.df["temp_air"].to_numpy(), atol=1e-9
    )


def test_subhourly_interpolation(data_dir):
    """time_steps_per_hour=2 yields 17520 steps and a 1800 s time step (FR-12)."""
    w = process_epw(
        data_dir / "ITA_Venezia-Tessera.161050_IGDG.epw", year=2023, time_steps_per_hour=2
    )
    assert w.n_steps == 17520
    assert w.timestep_seconds == 1800.0
