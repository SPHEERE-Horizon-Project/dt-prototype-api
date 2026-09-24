"""Reproducible example orchestration for the validated reference portfolio."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dt_prototype.common.output_paths import validate_run_id

from dt_prototype.integration.comparison import (
    ComparisonRule,
    MappingClassification,
    compare_monthly_results,
    diagnostics_frame,
    verify_zonal_energy_aggregation,
)
from dt_prototype.integration.engines import (
    Model3Engine,
    SemiStationaryEngine,
    SemiStationaryRequest,
)
from dt_prototype.integration.mapping import write_reference_case_as_model3_inputs
from dt_prototype.integration.model3 import model3
from dt_prototype.integration.project_paths import (
    example_data_dir,
    resolve_project_root,
)
from dt_prototype.integration.schemas import MonthlyPhysicsResults
from dt_prototype.integration.weather import (
    audit_raw_epw_ingestion,
    process_epw_to_monthly,
    sha256_file,
)


def _git_commit(project_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip()


def _combine_results(
    engine_id: str,
    engine_version: str,
    results: list[MonthlyPhysicsResults],
    metadata: dict[str, Any],
) -> MonthlyPhysicsResults:
    return MonthlyPhysicsResults(
        engine_id=engine_id,
        engine_version=engine_version,
        records=tuple(record for result in results for record in result.records),
        warnings=tuple(warning for result in results for warning in result.warnings),
        metadata=metadata,
    ).validate()


def _comparison_rules() -> tuple[ComparisonRule, ...]:
    return (
        ComparisonRule(
            "outdoor_temp_C",
            MappingClassification.EQUIVALENT_AFTER_CONVERSION,
            absolute_tolerance=1e-12,
            comparison_basis="same reference monthly weather",
            next_action="Check period/weather identity if this fails.",
        ),
        ComparisonRule(
            "H_transmission_W_K",
            MappingClassification.EQUIVALENT_AFTER_CONVERSION,
            absolute_tolerance=1e-8,
            comparison_basis="reference non-ground UA mapped to Model 3 opaque UA",
            next_action="Inspect surface and ground boundary mapping if this fails.",
        ),
        ComparisonRule(
            "H_ground_W_K",
            MappingClassification.EQUIVALENT_AFTER_CONVERSION,
            absolute_tolerance=1e-8,
            comparison_basis="same validated reference 0.7-U ground component",
            next_action="Inspect ground_method_id and floor area if this fails.",
        ),
        ComparisonRule(
            "total_gain_kWh",
            MappingClassification.EQUIVALENT_AFTER_CONVERSION,
            absolute_tolerance=1e-8,
            comparison_basis="reference total gain prescribed through Model 3 internal-gain channel",
            next_action="Inspect monthly energy-to-power conversion if this fails.",
        ),
        ComparisonRule(
            "H_total_W_K",
            MappingClassification.APPROXIMATE,
            comparison_basis="reference monthly air exchange mapped to annual mean",
            next_action="Review schedule and AHU boundary; do not tune tolerance.",
        ),
        ComparisonRule(
            "thermal_capacity_J_K",
            MappingClassification.APPROXIMATE,
            comparison_basis="reference layer capacity mapped to nearest Model 3 mass class",
            next_action="Review mass-class selection and report both values.",
        ),
        ComparisonRule(
            "time_constant_h",
            MappingClassification.APPROXIMATE,
            comparison_basis="capacity and effective-H definitions differ; no aggregate two-zone tau",
            next_action="Compare individual zones and component definitions.",
            intentional_missing_warning_codes=(
                "AGGREGATED_TIME_CONSTANT_NOT_UNIQUE",
            ),
        ),
        ComparisonRule(
            "useful_heating_kWh",
            MappingClassification.APPROXIMATE,
            comparison_basis="operating schedules, AHU, utilisation, and zone aggregation differ",
            next_action="Trace intermediate losses/gains before useful demand.",
        ),
        ComparisonRule(
            "useful_cooling_kWh",
            MappingClassification.APPROXIMATE,
            comparison_basis="operating schedules, AHU, utilisation, and zone aggregation differ",
            next_action="Trace intermediate losses/gains before useful demand.",
        ),
    )


def run_supplied_reference_comparison(
    project_root: str | Path | None,
    outputs_root: str | Path,
    run_id: str,
    comparison_mode: str = "legacy",
) -> Path:
    """Run all supplied buildings and write a new immutable comparison directory."""

    if comparison_mode not in {"legacy", "seasonal_ahu"}:
        raise ValueError("comparison_mode must be 'legacy' or 'seasonal_ahu'")
    validate_run_id(run_id)

    root = resolve_project_root(project_root)
    output_root = Path(outputs_root).resolve()
    run_dir = output_root / run_id
    if run_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing run directory: {run_dir}")
    run_dir.mkdir(parents=True)
    (run_dir / "weather").mkdir()
    mapped_inputs_root = run_dir / "validated_inputs" / "model3_mapped"
    mapped_inputs_root.mkdir(parents=True)

    reference_data = example_data_dir(root)
    epw = reference_data / "ITA_Venezia-Tessera.161050_IGDG.epw"
    geojson = reference_data / "example_district.geojson"
    archetypes_path = reference_data / "archetypes.json"
    schedules_path = reference_data / "schedules.json"
    model3_path = Path(model3.__file__).resolve()
    weather_id = "venezia_161050_igdg"

    prepared_weather = process_epw_to_monthly(epw, weather_id)
    weather_audit = audit_raw_epw_ingestion(
        epw, prepared_weather.reference_hourly_weather
    )
    if not weather_audit.passed:
        raise RuntimeError(f"Independent EPW ingestion audit failed: {weather_audit}")
    prepared_weather.to_frame().to_csv(
        run_dir / "weather" / "monthly_weather.csv", index=False
    )
    (run_dir / "weather" / "weather_manifest.json").write_text(
        json.dumps(dict(prepared_weather.metadata), indent=2), encoding="utf-8"
    )

    from dt_prototype.common.preprocessing.archetypes import load_envelope_archetypes
    from dt_prototype.common.preprocessing.building_input import (
        DistrictInput,
        assemble_building_input,
    )
    from dt_prototype.common.preprocessing.geometry import load_district_geojson
    from dt_prototype.common.preprocessing.schedules import load_end_use_schedules

    geometries = load_district_geojson(geojson)
    archetypes = load_envelope_archetypes(archetypes_path)
    schedules = load_end_use_schedules(schedules_path)
    district = DistrictInput(
        weather=prepared_weather.reference_hourly_weather,
        buildings=[
            assemble_building_input(geometry, archetypes, schedules)
            for geometry in geometries
        ],
    )

    reference_engine = SemiStationaryEngine()
    model3_engine = Model3Engine()
    reference_by_building: list[MonthlyPhysicsResults] = []
    model3_by_building: list[MonthlyPhysicsResults] = []
    all_diagnostics = []
    mapping_manifests = []

    for building in district.buildings:
        building_id = building.geometry.building_id
        scenario_id = "baseline"
        reference = reference_engine.simulate(
            SemiStationaryRequest(
                run_id=run_id,
                building_id=building_id,
                scenario_id=scenario_id,
                weather_id=weather_id,
                building=building,
                weather=district.weather,
                include_zone_results=True,
            )
        )
        reference_by_building.append(reference)

        building_model3_parts: list[MonthlyPhysicsResults] = []
        requested_zones: list[str | None] = [None]
        if len(building.zones) > 1:
            requested_zones.extend(
                zone.geometry.zone_label for zone in building.zones
            )
        for zone_id in requested_zones:
            label = "aggregate" if zone_id is None else zone_id
            mapped = write_reference_case_as_model3_inputs(
                mapped_inputs_root / building_id / label,
                reference_results=reference,
                reference_building=building,
                reference_weather=district.weather,
                run_id=run_id,
                scenario_id=scenario_id,
                weather_id=weather_id,
                zone_id=zone_id,
                comparison_mode=comparison_mode,
            )
            mapping_manifests.append(mapped.manifest)
            building_model3_parts.append(model3_engine.simulate(mapped.request))
        building_model3 = _combine_results(
            model3_engine.engine_id,
            model3_engine.engine_version,
            building_model3_parts,
            {"building_id": building_id},
        )
        model3_by_building.append(building_model3)
        all_diagnostics.extend(
            compare_monthly_results(
                building_model3,
                reference,
                _comparison_rules(),
            )
        )
        if len(building.zones) > 1:
            all_diagnostics.extend(verify_zonal_energy_aggregation(reference))

    reference_results = _combine_results(
        reference_engine.engine_id,
        reference_engine.engine_version,
        reference_by_building,
        {"portfolio": "supplied_reference_five_buildings"},
    )
    legacy_results = _combine_results(
        model3_engine.engine_id,
        model3_engine.engine_version,
        model3_by_building,
        {"portfolio": "mapped_reference_comparison_cases"},
    )
    reference_results.to_frame().to_csv(
        run_dir / "physics_full_monthly.csv", index=False
    )
    legacy_results.to_frame().to_csv(
        run_dir / "physics_model3_comparison_monthly.csv", index=False
    )
    warning_frames = [
        frame
        for frame in (
            reference_results.warnings_frame(),
            legacy_results.warnings_frame(),
        )
        if not frame.empty
    ]
    pd.concat(warning_frames, ignore_index=True).to_csv(
        run_dir / "warnings.csv", index=False
    )
    diagnostics = diagnostics_frame(tuple(all_diagnostics))
    diagnostics.to_csv(run_dir / "cross_model_diagnostics.csv", index=False)

    exact_diagnostics = diagnostics[
        diagnostics["mapping_classification"].isin(
            (
                MappingClassification.EQUIVALENT.value,
                MappingClassification.EQUIVALENT_AFTER_CONVERSION.value,
            )
        )
    ]
    manifest = {
        "run_id": run_id,
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete",
        "code_commit": _git_commit(root),
        "engine_names_versions": {
            reference_engine.engine_id: reference_engine.engine_version,
            model3_engine.engine_id: model3_engine.engine_version,
        },
        "primary_engine": reference_engine.engine_id,
        "comparison_engine": model3_engine.engine_id,
        "comparison_mode": comparison_mode,
        "reference_status": "benchmark_validated_in_prior_project_phases",
        "input_hashes": {
            "epw": sha256_file(epw),
            "geojson": sha256_file(geojson),
            "archetypes": sha256_file(archetypes_path),
            "schedules": sha256_file(schedules_path),
            "model3_module": sha256_file(model3_path),
        },
        "epw_preprocessing_metadata": dict(prepared_weather.metadata),
        "epw_independent_audit": {
            "passed": weather_audit.passed,
            "raw_row_count": weather_audit.raw_row_count,
            "selected_record_indices_zero_based": list(
                weather_audit.selected_record_indices
            ),
            "maximum_temperature_mean_difference_C": (
                weather_audit.maximum_temperature_mean_difference_C
            ),
            "maximum_ghi_sum_difference_kWh_m2": (
                weather_audit.maximum_ghi_sum_difference_kWh_m2
            ),
        },
        "comparison_cases": {
            "single_zone": True,
            "individual_zones": True,
            "independent_two_zone_aggregate": True,
            "reference_dynamic_rerun_required": False,
            "seasonal_mask_enabled": comparison_mode == "seasonal_ahu",
            "separate_ahu_enabled": comparison_mode == "seasonal_ahu",
        },
        "comparison_counts": {
            "buildings": len(district.buildings),
            "reference_rows": len(reference_results.records),
            "model3_rows": len(legacy_results.records),
            "diagnostics": len(diagnostics),
            "equivalent_diagnostics": len(exact_diagnostics),
            "equivalent_pass": int((exact_diagnostics["status"] == "PASS").sum()),
            "equivalent_fail": int((exact_diagnostics["status"] == "FAIL").sum()),
        },
        "mapping_manifests": mapping_manifests,
        "calibration_periods": [],
        "validation_periods": [],
        "regression_parameter_bounds": "not_used_in_this_verification_run",
        "dependency_environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "random_seed": 13790,
        "output_format_note": (
            "Stage 2/4 verification uses CSV; release Parquet outputs require the "
            "future locked artifact environment."
        ),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return run_dir
