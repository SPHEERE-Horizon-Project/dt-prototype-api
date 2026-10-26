"""Shared pytest fixtures.

Test *code* lives here (NFR-08); test *data* lives in ``data/tests/``
(NFR-09), reusing the the retained reference example district and Venice EPW file.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")  # headless plotting for the visualisation tests

from dt_prototype.common.preprocessing.archetypes import (
    ConstructionSpec,
    EnvelopeArchetype,
    WindowSpec,
    load_envelope_archetypes,
)
from dt_prototype.common.preprocessing.building_input import BuildingInput, ZoneInput, preprocess_district
from dt_prototype.common.preprocessing.geometry import BuildingGeometry, SurfaceSpec, ZoneGeometry
from dt_prototype.common.preprocessing.schedules import EndUseSchedule, load_end_use_schedules
from dt_prototype.common.preprocessing.weather import process_epw

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "examples"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    """Path to the test-fixture data directory (``data/tests/``)."""
    return DATA_DIR


@pytest.fixture(scope="session")
def weather():
    """Processed Venice EPW weather (session-cached, the retained reference test data)."""
    return process_epw(DATA_DIR / "ITA_Venezia-Tessera.161050_IGDG.epw", year=2023)


@pytest.fixture(scope="session")
def archetypes():
    """Envelope archetype database fixture."""
    return load_envelope_archetypes(DATA_DIR / "archetypes_fixture.json")


@pytest.fixture(scope="session")
def schedules():
    """End-use schedule database fixture."""
    return load_end_use_schedules(DATA_DIR / "schedules_fixture.json", year=2023)


@pytest.fixture(scope="session")
def district(weather, archetypes, schedules):
    """Fully preprocessed the retained reference example district (5 buildings), including
    the HVAC system template database (all system codes resolve)."""
    return preprocess_district(
        geojson_path=DATA_DIR / "example_district.geojson",
        epw_path=DATA_DIR / "ITA_Venezia-Tessera.161050_IGDG.epw",
        archetypes_path=DATA_DIR / "archetypes_fixture.json",
        schedules_path=DATA_DIR / "schedules_fixture.json",
        systems_path=DATA_DIR / "systems_templates.json",
    )


@pytest.fixture(scope="session")
def district_no_templates(weather):
    """Same district preprocessed WITHOUT the system template database —
    the short system codes fall back to IdealLoad (legacy behaviour)."""
    return preprocess_district(
        geojson_path=DATA_DIR / "example_district.geojson",
        epw_path=DATA_DIR / "ITA_Venezia-Tessera.161050_IGDG.epw",
        archetypes_path=DATA_DIR / "archetypes_fixture.json",
        schedules_path=DATA_DIR / "schedules_fixture.json",
    )


def make_box_building(
    name: str = "box",
    footprint: float = 100.0,
    height: float = 6.0,
    n_floors: int = 2,
    heating_setpoint: float = 20.0,
    cooling_setpoint: float = 26.0,
    ach: float = 0.5,
    n_steps: int = 8760,
) -> BuildingInput:
    """Synthetic 10x10 m two-storey box building with constant schedules and
    zero internal gains — used for analytic steady-state model checks."""
    side = float(np.sqrt(footprint))
    surfaces = [
        SurfaceSpec("ExtWall", side * height, azimuth=az, tilt=90.0)
        for az in (0.0, 90.0, 180.0, 270.0)
    ]
    surfaces += [
        SurfaceSpec("Roof", footprint, tilt=0.0),
        SurfaceSpec("GroundFloor", footprint, tilt=0.0),
        SurfaceSpec("IntFloor", footprint, tilt=0.0),
        SurfaceSpec("IntCeiling", footprint, tilt=0.0),
        SurfaceSpec("IntWall", footprint * n_floors, tilt=90.0),
    ]
    geometry = BuildingGeometry(
        name=name,
        building_id=name,
        envelope="test",
        n_floors=n_floors,
        height=height,
        footprint_area=footprint,
        zones=[
            ZoneGeometry(
                name=name,
                zone_label="single",
                end_use="residential",
                n_floors=n_floors,
                net_floor_area=footprint * n_floors,
                volume=footprint * height,
                surfaces=surfaces,
            )
        ],
    )
    constructions = {
        ctype: ConstructionSpec.from_u_value(f"test_{ctype}", u, "Medium", ctype)
        for ctype, u in (
            ("ExtWall", 0.8),
            ("Roof", 0.9),
            ("GroundFloor", 1.2),
            ("IntWall", 1.8),
            ("IntCeiling", 1.5),
            ("IntFloor", 1.5),
        )
    }
    envelope = EnvelopeArchetype(
        name="test",
        constructions=constructions,
        window=WindowSpec(u_value=2.8, shgc=0.7),
        wwr=0.15,
        infiltration_ach=0.0,
    )
    n = n_steps
    schedule = EndUseSchedule(
        name="constant",
        internal_gain_convective=np.zeros(n),
        internal_gain_radiative=np.zeros(n),
        internal_gain_latent=np.zeros(n),
        heating_setpoint=np.full(n, heating_setpoint),
        cooling_setpoint=np.full(n, cooling_setpoint),
        humidity_setpoint_low=np.full(n, 0.0),
        humidity_setpoint_high=np.full(n, 1.0),
        ventilation_ach=np.full(n, ach),
        electric_load=np.zeros(n),
        dhw_volume_flow=np.zeros(n),
    )
    return BuildingInput.single_zone(geometry, envelope, schedule)


def make_two_zone_box_building(
    name: str = "twozone",
    footprint: float = 100.0,
    height: float = 6.0,
    n_floors: int = 2,
    n_steps: int = 8760,
) -> BuildingInput:
    """Synthetic 2-zone box (upper zone above a ground-floor lower zone),
    each with a constant but opposite-extreme schedule: the upper zone's
    heating set point is far above outdoor temperature (always wants
    heating), the lower zone's cooling set point is far below it (always
    wants cooling). Used to check that a building-level result never nets
    one zone's heating against another zone's simultaneous cooling."""
    side = float(np.sqrt(footprint))
    floor_height = height / n_floors

    def zone_surfaces(zone_height, zone_n_floors, include_roof, include_ground):
        surfaces = [
            SurfaceSpec("ExtWall", side * zone_height, azimuth=az, tilt=90.0)
            for az in (0.0, 90.0, 180.0, 270.0)
        ]
        if include_roof:
            surfaces.append(SurfaceSpec("Roof", footprint, tilt=0.0))
        if include_ground:
            surfaces.append(SurfaceSpec("GroundFloor", footprint, tilt=0.0))
        surfaces.append(SurfaceSpec("IntWall", footprint * zone_n_floors, tilt=90.0))
        return surfaces

    upper_floors = n_floors - 1
    geometry = BuildingGeometry(
        name=name,
        building_id=name,
        envelope="test",
        n_floors=n_floors,
        height=height,
        footprint_area=footprint,
        zones=[
            ZoneGeometry(
                name=f"{name}_upper",
                zone_label="upper",
                end_use="hot",
                n_floors=upper_floors,
                net_floor_area=footprint * upper_floors,
                volume=footprint * floor_height * upper_floors,
                surfaces=zone_surfaces(
                    floor_height * upper_floors, upper_floors, True, False
                ),
            ),
            ZoneGeometry(
                name=f"{name}_lower",
                zone_label="lower",
                end_use="cold",
                n_floors=1,
                net_floor_area=footprint,
                volume=footprint * floor_height,
                surfaces=zone_surfaces(floor_height, 1, False, True),
            ),
        ],
    )
    constructions = {
        ctype: ConstructionSpec.from_u_value(f"test_{ctype}", u, "Medium", ctype)
        for ctype, u in (
            ("ExtWall", 0.8),
            ("Roof", 0.9),
            ("GroundFloor", 1.2),
            ("IntWall", 1.8),
            ("IntCeiling", 1.5),
            ("IntFloor", 1.5),
        )
    }
    envelope = EnvelopeArchetype(
        name="test",
        constructions=constructions,
        window=WindowSpec(u_value=2.8, shgc=0.7),
        wwr=0.15,
        infiltration_ach=0.0,
    )
    n = n_steps

    def make_schedule(sched_name: str, heating_sp: float, cooling_sp: float) -> EndUseSchedule:
        return EndUseSchedule(
            name=sched_name,
            internal_gain_convective=np.zeros(n),
            internal_gain_radiative=np.zeros(n),
            internal_gain_latent=np.zeros(n),
            heating_setpoint=np.full(n, heating_sp),
            cooling_setpoint=np.full(n, cooling_sp),
            humidity_setpoint_low=np.full(n, 0.0),
            humidity_setpoint_high=np.full(n, 1.0),
            ventilation_ach=np.full(n, 0.5),
            electric_load=np.zeros(n),
            dhw_volume_flow=np.zeros(n),
        )

    zones = [
        ZoneInput(geometry.zones[0], envelope, make_schedule("hot", 30.0, 35.0)),
        ZoneInput(geometry.zones[1], envelope, make_schedule("cold", -10.0, 5.0)),
    ]
    return BuildingInput(geometry=geometry, zones=zones)


def make_constant_weather(t_ext: float = 0.0, n_steps: int = 8760):
    """Synthetic constant weather (no sun) for analytic model checks."""
    import pandas as pd

    from dt_prototype.common.preprocessing.weather import WeatherData

    index = pd.date_range("2023-01-01", periods=n_steps, freq="h")
    df = pd.DataFrame(index=index)
    df["temp_air"] = t_ext
    df["relative_humidity"] = 0.5
    df["pressure"] = 101325.0
    df["specific_humidity"] = 0.002
    df["ghi"] = 0.0
    df["dni"] = 0.0
    df["dhi"] = 0.0
    df["wind_speed"] = 1.0
    df["sun_elevation"] = -10.0
    df["sun_azimuth"] = 0.0
    for az in range(0, 360, 45):
        df[f"poa_glob_az{az}_t90"] = 0.0
        df[f"poa_dir_az{az}_t90"] = 0.0
    df["poa_glob_az0_t0"] = 0.0
    df["poa_dir_az0_t0"] = 0.0
    return WeatherData(
        df=df, latitude=45.0, longitude=12.0, timezone=1.0, average_dt_air_sky=0.0
    )
