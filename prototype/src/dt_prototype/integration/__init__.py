"""Common contracts and independent engine adapters for the integrated model."""

from dt_prototype.integration.five_parameter import FiveParameterConfig, FiveParameterFit

from dt_prototype.integration.schemas import (
    BuildingRecord,
    CalibrationOverrideRecord,
    CalculationStatus,
    CalibrationValidationFlag,
    CarrierFactorRecord,
    ConstructionLayerRecord,
    ConstructionRecord,
    MeterBoundaryRecord,
    MonthlyPhysicsRecord,
    MonthlyPhysicsResults,
    MonthlyWeatherRecord,
    ScheduleValueRecord,
    ScenarioOverlayRecord,
    SurfaceRecord,
    SystemServiceRecord,
    WindowRecord,
    ZoneRecord,
)

__all__ = [
    "BuildingRecord",
    "CalibrationOverrideRecord",
    "CalculationStatus",
    "CalibrationValidationFlag",
    "CarrierFactorRecord",
    "ConstructionLayerRecord",
    "ConstructionRecord",
    "MeterBoundaryRecord",
    "MonthlyPhysicsRecord",
    "MonthlyPhysicsResults",
    "MonthlyWeatherRecord",
    "ScheduleValueRecord",
    "ScenarioOverlayRecord",
    "SurfaceRecord",
    "SystemServiceRecord",
    "WindowRecord",
    "ZoneRecord",
    "FiveParameterConfig",
    "FiveParameterFit",
]

__version__ = "0.2.0"
