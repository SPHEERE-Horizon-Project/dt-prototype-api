"""Small deterministic reference cases for component cross-model verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ReferenceVerificationCase:
    case_id: str
    building: Any
    weather: Any
    comparison_month: str
    expected_primary_component: str


def make_reference_verification_case(
    case_id: Literal[
        "transmission_only",
        "ventilation_only",
        "infiltration_only",
        "no_temperature_difference",
    ],
) -> ReferenceVerificationCase:
    """Create a zero-solar/zero-gain single-zone case in reference-native types."""

    from dt_prototype.common.preprocessing.archetypes import (
        ConstructionSpec,
        EnvelopeArchetype,
        WindowSpec,
    )
    from dt_prototype.common.preprocessing.building_input import BuildingInput
    from dt_prototype.common.preprocessing.geometry import BuildingGeometry, SurfaceSpec
    from dt_prototype.common.preprocessing.schedules import EndUseSchedule
    from dt_prototype.common.preprocessing.weather import WeatherData

    if case_id not in {
        "transmission_only",
        "ventilation_only",
        "infiltration_only",
        "no_temperature_difference",
    }:
        raise ValueError(f"Unknown verification case: {case_id}")

    index = pd.date_range("2023-01-01", periods=8760, freq="h")
    outdoor_temperature = 20.0 if case_id == "no_temperature_difference" else 0.0
    weather_frame = pd.DataFrame(
        {
            "temp_air": np.full(8760, outdoor_temperature),
            "temp_dew": np.full(8760, outdoor_temperature - 2.0),
            "relative_humidity": np.full(8760, 0.5),
            "pressure": np.full(8760, 101325.0),
            "specific_humidity": np.full(8760, 0.005),
            "wind_speed": np.zeros(8760),
            "ghi": np.zeros(8760),
            "dni": np.zeros(8760),
            "dhi": np.zeros(8760),
            "sun_elevation": np.zeros(8760),
            "sun_azimuth": np.zeros(8760),
            "poa_glob_az0_t90": np.zeros(8760),
            "poa_dir_az0_t90": np.zeros(8760),
            "poa_glob_az0_t0": np.zeros(8760),
            "poa_dir_az0_t0": np.zeros(8760),
        },
        index=index,
    )
    weather = WeatherData(
        df=weather_frame,
        latitude=45.0,
        longitude=12.0,
        timezone=1.0,
        time_steps_per_hour=1,
        azimuth_subdivisions=8,
        average_dt_air_sky=0.0,
        location_name=f"verification-{case_id}",
    )

    ext_wall = ConstructionSpec.from_u_value(
        "verification_ext_wall",
        u_value=0.5,
        mass_class="Medium",
        construction_type="ExtWall",
        solar_absorptance=0.0,
    )
    int_wall = ConstructionSpec.from_u_value(
        "verification_int_wall",
        u_value=1.0,
        mass_class="Medium",
        construction_type="IntWall",
        solar_absorptance=0.0,
    )
    envelope = EnvelopeArchetype(
        name="verification_envelope",
        constructions={"ExtWall": ext_wall, "IntWall": int_wall},
        window=WindowSpec(u_value=1.0, shgc=0.0, frame_factor=0.0, shading_coef=1.0),
        wwr=0.0,
        infiltration_ach=0.0,
    )
    surfaces = [SurfaceSpec("IntWall", 100.0, azimuth=0.0, tilt=90.0)]
    if case_id in {"transmission_only", "no_temperature_difference"}:
        surfaces.insert(0, SurfaceSpec("ExtWall", 100.0, azimuth=0.0, tilt=90.0))
    geometry = BuildingGeometry(
        name=case_id,
        building_id=case_id,
        end_use="verification",
        envelope=envelope.name,
        n_floors=1,
        height=3.0,
        footprint_area=100.0,
        net_floor_area=100.0,
        volume=300.0,
        surfaces=surfaces,
    )
    ventilation_ach = 0.5 if case_id == "ventilation_only" else 0.0
    infiltration_ach = 0.5 if case_id == "infiltration_only" else 0.0
    schedule = EndUseSchedule(
        name="verification",
        internal_gain_convective=np.zeros(8760),
        internal_gain_radiative=np.zeros(8760),
        internal_gain_latent=np.zeros(8760),
        heating_setpoint=np.full(8760, 20.0),
        cooling_setpoint=np.full(8760, 99.0),
        humidity_setpoint_low=np.full(8760, 0.35),
        humidity_setpoint_high=np.full(8760, 0.55),
        ventilation_ach=np.full(8760, ventilation_ach),
        electric_load=np.zeros(8760),
        dhw_volume_flow=np.zeros(8760),
        infiltration_ach=np.full(8760, infiltration_ach),
    )
    building = BuildingInput.single_zone(geometry, envelope, schedule)
    component = {
        "transmission_only": "H_transmission_W_K",
        "ventilation_only": "H_ventilation_W_K",
        "infiltration_only": "H_infiltration_W_K",
        "no_temperature_difference": "useful_heating_kWh",
    }[case_id]
    return ReferenceVerificationCase(
        case_id=case_id,
        building=building,
        weather=weather,
        comparison_month="2023-01",
        expected_primary_component=component,
    )
