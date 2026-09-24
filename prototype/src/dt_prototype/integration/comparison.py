"""Boundary-aware cross-model comparison diagnostics.

Agreement reported here is cross-model verification or comparison.  It is not
labelled empirical validation.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable, Sequence

import pandas as pd

from dt_prototype.integration.schemas import MonthlyPhysicsRecord, MonthlyPhysicsResults


class MappingClassification(str, Enum):
    EQUIVALENT = "EQUIVALENT"
    EQUIVALENT_AFTER_CONVERSION = "EQUIVALENT_AFTER_CONVERSION"
    APPROXIMATE = "APPROXIMATE"
    DELIBERATELY_DIFFERENT = "DELIBERATELY_DIFFERENT"
    NOT_COMPARABLE = "NOT_COMPARABLE"


@dataclass(frozen=True)
class ComparisonRule:
    quantity: str
    classification: MappingClassification
    absolute_tolerance: float = 0.0
    relative_tolerance: float = 0.0
    comparison_basis: str = ""
    next_action: str = ""
    intentional_missing_warning_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComparisonDiagnostic:
    run_id: str
    building_id: str
    scenario_id: str
    weather_id: str
    period_id: str
    zone_id: str | None
    left_engine_id: str
    right_engine_id: str
    quantity: str
    unit: str
    left_value: float | None
    right_value: float | None
    absolute_difference: float | None
    relative_difference_pct: float | None
    mapping_classification: MappingClassification
    comparison_basis: str
    status: str
    next_action: str


_UNITS = {
    "outdoor_temp_C": "degC",
    "H_transmission_W_K": "W/K",
    "H_ventilation_W_K": "W/K",
    "H_infiltration_W_K": "W/K",
    "H_ground_W_K": "W/K",
    "H_total_W_K": "W/K",
    "thermal_capacity_J_K": "J/K",
    "time_constant_h": "h",
    "heating_heat_transfer_kWh": "kWh",
    "cooling_heat_transfer_kWh": "kWh",
    "solar_gain_kWh": "kWh",
    "internal_gain_kWh": "kWh",
    "total_gain_kWh": "kWh",
    "utilisation_factor_heating": "1",
    "utilisation_factor_cooling": "1",
    "zone_sensible_heating_kWh": "kWh",
    "zone_sensible_cooling_kWh": "kWh",
    "ahu_sensible_heating_kWh": "kWh",
    "ahu_sensible_cooling_kWh": "kWh",
    "useful_heating_kWh": "kWh",
    "useful_cooling_kWh": "kWh",
}


def _comparison_key(
    record: MonthlyPhysicsRecord,
) -> tuple[str, str, str, str, str | None]:
    return (
        record.building_id,
        record.scenario_id,
        record.weather_id,
        record.period_id,
        record.zone_id,
    )


def _finite_or_none(value: object) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def compare_monthly_results(
    left: MonthlyPhysicsResults,
    right: MonthlyPhysicsResults,
    rules: Sequence[ComparisonRule],
) -> tuple[ComparisonDiagnostic, ...]:
    """Compare only rows with identical building/scenario/weather/period/zone keys."""

    left.validate()
    right.validate()
    left_index = {_comparison_key(record): record for record in left.records}
    right_index = {_comparison_key(record): record for record in right.records}
    keys = sorted(set(left_index) | set(right_index), key=lambda item: tuple(str(x) for x in item))
    diagnostics: list[ComparisonDiagnostic] = []
    for key in keys:
        left_record = left_index.get(key)
        right_record = right_index.get(key)
        exemplar = left_record or right_record
        assert exemplar is not None
        for rule in rules:
            if not hasattr(exemplar, rule.quantity):
                raise AttributeError(f"Unknown canonical result quantity: {rule.quantity}")
            left_value = (
                None
                if left_record is None
                else _finite_or_none(getattr(left_record, rule.quantity))
            )
            right_value = (
                None
                if right_record is None
                else _finite_or_none(getattr(right_record, rule.quantity))
            )
            absolute_difference: float | None = None
            relative_difference: float | None = None
            if left_value is not None and right_value is not None:
                absolute_difference = left_value - right_value
                if right_value != 0.0:
                    relative_difference = absolute_difference / abs(right_value) * 100.0

            intentional_missing = (
                left_value is None or right_value is None
            ) and any(
                code in rule.intentional_missing_warning_codes
                for record in (left_record, right_record)
                if record is not None
                for code in record.warning_codes
            )
            if rule.classification == MappingClassification.NOT_COMPARABLE:
                status = "NOT_COMPARABLE"
            elif intentional_missing:
                status = "NOT_COMPARABLE"
            elif left_value is None or right_value is None:
                status = "MISSING_QUANTITY"
            elif rule.classification in {
                MappingClassification.EQUIVALENT,
                MappingClassification.EQUIVALENT_AFTER_CONVERSION,
            }:
                tolerance = rule.absolute_tolerance + rule.relative_tolerance * abs(
                    right_value
                )
                status = (
                    "PASS" if abs(absolute_difference or 0.0) <= tolerance else "FAIL"
                )
            elif rule.classification == MappingClassification.APPROXIMATE:
                status = "REVIEW"
            else:
                status = "INFORMATIONAL"

            diagnostics.append(
                ComparisonDiagnostic(
                    run_id=exemplar.run_id,
                    building_id=key[0],
                    scenario_id=key[1],
                    weather_id=key[2],
                    period_id=key[3],
                    zone_id=key[4],
                    left_engine_id=left.engine_id,
                    right_engine_id=right.engine_id,
                    quantity=rule.quantity,
                    unit=_UNITS.get(rule.quantity, "unknown"),
                    left_value=left_value,
                    right_value=right_value,
                    absolute_difference=absolute_difference,
                    relative_difference_pct=relative_difference,
                    mapping_classification=rule.classification,
                    comparison_basis=rule.comparison_basis,
                    status=status,
                    next_action=rule.next_action,
                )
            )
    return tuple(diagnostics)


def verify_zonal_energy_aggregation(
    results: MonthlyPhysicsResults,
    quantities: Iterable[str] = (
        "zone_sensible_heating_kWh",
        "zone_sensible_cooling_kWh",
        "ahu_sensible_heating_kWh",
        "ahu_sensible_cooling_kWh",
        "useful_heating_kWh",
        "useful_cooling_kWh",
    ),
    *,
    absolute_tolerance: float = 1e-8,
) -> tuple[ComparisonDiagnostic, ...]:
    """Verify that two-zone energy rows sum to the building aggregate."""

    results.validate()
    aggregate = {
        (r.building_id, r.scenario_id, r.weather_id, r.period_id): r
        for r in results.records
        if r.zone_id is None
    }
    zones: dict[tuple[str, str, str, str], list[MonthlyPhysicsRecord]] = {}
    for record in results.records:
        if record.zone_id is not None:
            key = (
                record.building_id,
                record.scenario_id,
                record.weather_id,
                record.period_id,
            )
            zones.setdefault(key, []).append(record)

    diagnostics: list[ComparisonDiagnostic] = []
    for key, zone_records in sorted(zones.items()):
        if key not in aggregate:
            continue
        building_record = aggregate[key]
        for quantity in quantities:
            aggregate_value = _finite_or_none(getattr(building_record, quantity))
            zone_values = [_finite_or_none(getattr(record, quantity)) for record in zone_records]
            zone_sum = None if any(value is None for value in zone_values) else sum(zone_values)  # type: ignore[arg-type]
            difference = (
                None
                if aggregate_value is None or zone_sum is None
                else aggregate_value - zone_sum
            )
            diagnostics.append(
                ComparisonDiagnostic(
                    run_id=building_record.run_id,
                    building_id=key[0],
                    scenario_id=key[1],
                    weather_id=key[2],
                    period_id=key[3],
                    zone_id=None,
                    left_engine_id=results.engine_id,
                    right_engine_id=f"{results.engine_id}:sum_of_zones",
                    quantity=quantity,
                    unit=_UNITS.get(quantity, "unknown"),
                    left_value=aggregate_value,
                    right_value=zone_sum,
                    absolute_difference=difference,
                    relative_difference_pct=(
                        None
                        if difference is None or zone_sum in (None, 0.0)
                        else difference / abs(zone_sum) * 100.0
                    ),
                    mapping_classification=MappingClassification.EQUIVALENT,
                    comparison_basis="Reference building energy must equal the sum of independent zones.",
                    status=(
                        "MISSING_QUANTITY"
                        if difference is None
                        else "PASS"
                        if abs(difference) <= absolute_tolerance
                        else "FAIL"
                    ),
                    next_action="Inspect zone-to-building aggregation if this check fails.",
                )
            )
    return tuple(diagnostics)


def diagnostics_frame(
    diagnostics: Sequence[ComparisonDiagnostic],
) -> pd.DataFrame:
    rows = []
    for diagnostic in diagnostics:
        row = asdict(diagnostic)
        row["mapping_classification"] = diagnostic.mapping_classification.value
        rows.append(row)
    return pd.DataFrame(rows)
