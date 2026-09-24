"""Immutable I/O and lean SVG reporting for five-parameter energy signatures."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd

from dt_prototype.integration.five_parameter import (
    FiveParameterConfig,
    build_simulated_measured_comparison,
    build_simulated_signature_vs_measured_metrics,
    fit_five_parameter_portfolio,
    validate_five_parameter_input,
)
from dt_prototype.common.output_paths import output_component, validate_run_id


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reference_run_to_five_parameter_input(source_run_dir: str | Path) -> pd.DataFrame:
    """Adapt completed five-building physics files without changing their contents.

    The verification response is total useful sensible heating plus cooling at
    the building aggregate.  It is explicitly labelled as a non-metered useful
    demand, not as a delivered carrier.
    """

    source = Path(source_run_dir).resolve()
    files = (
        source / "physics_full_monthly.csv",
        source / "physics_model3_comparison_monthly.csv",
    )
    frames: list[pd.DataFrame] = []
    for path in files:
        if not path.exists():
            continue
        physics = pd.read_csv(path, dtype={"building_id": str, "scenario_id": str})
        required = {
            "run_id",
            "engine_id",
            "building_id",
            "scenario_id",
            "weather_id",
            "period_id",
            "zone_id",
            "days",
            "outdoor_temp_C",
            "useful_heating_kWh",
            "useful_cooling_kWh",
            "calculation_status",
        }
        missing = required - set(physics.columns)
        if missing:
            raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
        aggregate = physics[physics["zone_id"].isna()].copy()
        aggregate["source_type"] = "simulated"
        aggregate["source_id"] = aggregate["engine_id"]
        aggregate["source_run_id"] = aggregate["run_id"]
        aggregate["carrier"] = "useful_sensible"
        aggregate["meter_boundary_id"] = "not_metered__useful_sensible_total"
        aggregate["energy_kWh"] = (
            aggregate["useful_heating_kWh"] + aggregate["useful_cooling_kWh"]
        )
        aggregate["calibration_validation_flag"] = "calibration"
        aggregate["data_quality_flag"] = np.where(
            aggregate["calculation_status"]
            .astype(str)
            .str.upper()
            .isin(("OK", "WARNING")),
            "valid",
            "excluded",
        )
        aggregate["interpretation_status"] = "HEURISTIC_ONLY"
        frames.append(
            aggregate[
                [
                    "source_type",
                    "source_id",
                    "source_run_id",
                    "building_id",
                    "scenario_id",
                    "weather_id",
                    "period_id",
                    "carrier",
                    "meter_boundary_id",
                    "energy_kWh",
                    "days",
                    "outdoor_temp_C",
                    "calibration_validation_flag",
                    "data_quality_flag",
                    "interpretation_status",
                    "calculation_boundary_id",
                ]
            ]
        )
    if not frames:
        raise FileNotFoundError(f"no supported physics result files found in {source}")
    return pd.concat(frames, ignore_index=True)


def _svg_energy_signature(
    predictions: pd.DataFrame,
    parameters: pd.DataFrame,
    title: str,
) -> str:
    """Render one accessible, dependency-free energy-signature SVG."""

    width, height = 900, 560
    left, right, top, bottom = 86, 28, 58, 82
    plot_width = width - left - right
    plot_height = height - top - bottom
    temperatures = predictions["outdoor_temp_C"].astype(float).to_numpy()
    powers = np.concatenate(
        (
            predictions["observed_average_power_kW"].astype(float).to_numpy(),
            predictions["predicted_average_power_kW"].astype(float).to_numpy(),
        )
    )
    finite_t = temperatures[np.isfinite(temperatures)]
    finite_p = powers[np.isfinite(powers)]
    x_min = float(np.min(finite_t)) if len(finite_t) else 0.0
    x_max = float(np.max(finite_t)) if len(finite_t) else 1.0
    y_min = min(0.0, float(np.min(finite_p))) if len(finite_p) else 0.0
    y_max = float(np.max(finite_p)) if len(finite_p) else 1.0
    x_pad = max(1.0, 0.05 * max(x_max - x_min, 1.0))
    y_pad = max(0.05, 0.08 * max(y_max - y_min, 1.0))
    x_min, x_max = x_min - x_pad, x_max + x_pad
    y_min, y_max = y_min, y_max + y_pad

    def x(value: float) -> float:
        return left + (value - x_min) * plot_width / (x_max - x_min)

    def y(value: float) -> float:
        return top + (y_max - value) * plot_height / (y_max - y_min)

    colors = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#56B4E9")
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{escape(title)}</title>',
        '<desc id="desc">Monthly average power observations and fitted five-parameter energy-signature curves by source.</desc>',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{left}" y="30" font-family="Arial, sans-serif" font-size="20" font-weight="600" fill="#222">{escape(title)}</text>',
        f'<rect x="{left}" y="{top}" width="{plot_width}" height="{plot_height}" fill="none" stroke="#555" stroke-width="1"/>',
    ]
    for fraction in np.linspace(0.0, 1.0, 6):
        tick_value = x_min + fraction * (x_max - x_min)
        x_pos = x(tick_value)
        pieces.extend(
            (
                f'<line x1="{x_pos:.2f}" y1="{top}" x2="{x_pos:.2f}" y2="{top + plot_height}" stroke="#ddd" stroke-width="1"/>',
                f'<text x="{x_pos:.2f}" y="{top + plot_height + 24}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#333">{tick_value:.1f}</text>',
            )
        )
    for fraction in np.linspace(0.0, 1.0, 6):
        tick_value = y_min + fraction * (y_max - y_min)
        y_pos = y(tick_value)
        pieces.extend(
            (
                f'<line x1="{left}" y1="{y_pos:.2f}" x2="{left + plot_width}" y2="{y_pos:.2f}" stroke="#ddd" stroke-width="1"/>',
                f'<text x="{left - 12}" y="{y_pos + 4:.2f}" text-anchor="end" font-family="Arial, sans-serif" font-size="12" fill="#333">{tick_value:.2f}</text>',
            )
        )
    pieces.extend(
        (
            f'<text x="{left + plot_width / 2}" y="{height - 24}" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" fill="#222">Monthly mean outdoor temperature (°C)</text>',
            f'<text x="22" y="{top + plot_height / 2}" text-anchor="middle" transform="rotate(-90 22 {top + plot_height / 2})" font-family="Arial, sans-serif" font-size="14" fill="#222">Monthly average power (kW)</text>',
        )
    )

    source_keys = ['source_type', 'source_id', 'source_run_id']
    legend_x = left + 8
    for index, (source_key, subset) in enumerate(predictions.groupby(source_keys, sort=False)):
        color = colors[index % len(colors)]
        mask = pd.Series(True, index=parameters.index)
        for column, value in zip(source_keys, source_key):
            mask &= parameters[column].eq(value)
        parameter = parameters[mask].iloc[0]
        source_id = ' / '.join(str(value) for value in source_key)
        curve_t = np.linspace(x_min, x_max, 160)
        curve_p = (
            float(parameter["beta_base_average_power_kW"])
            + float(parameter["beta_heating_average_power_kW_K"])
            * np.maximum(0.0, float(parameter["heating_change_point_C"]) - curve_t)
            + float(parameter["beta_cooling_average_power_kW_K"])
            * np.maximum(0.0, curve_t - float(parameter["cooling_change_point_C"]))
        )
        points = " ".join(
            f"{x(float(t)):.2f},{y(float(p)):.2f}" for t, p in zip(curve_t, curve_p)
        )
        pieces.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5"/>'
        )
        for _, point in subset.iterrows():
            if (not math.isfinite(float(point["observed_average_power_kW"]))
                    or not math.isfinite(float(point['outdoor_temp_C']))
                    or not (point['included_in_fit'] or point['included_in_validation_metrics'])):
                continue
            x_pos = x(float(point["outdoor_temp_C"]))
            y_pos = y(float(point["observed_average_power_kW"]))
            if str(point["calibration_validation_flag"]).lower() == "validation":
                pieces.append(
                    f'<rect x="{x_pos - 4:.2f}" y="{y_pos - 4:.2f}" width="8" height="8" fill="white" stroke="{color}" stroke-width="2"/>'
                )
            else:
                pieces.append(
                    f'<circle cx="{x_pos:.2f}" cy="{y_pos:.2f}" r="4" fill="{color}" stroke="white" stroke-width="1"/>'
                )
        legend_y = top + 20 + index * 22
        pieces.extend(
            (
                f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 24}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>',
                f'<text x="{legend_x + 32}" y="{legend_y + 4}" font-family="Arial, sans-serif" font-size="12" fill="#222">{escape(source_id)}</text>',
            )
        )
    pieces.append("</svg>")
    return "\n".join(pieces)


def write_energy_signature_figures(
    predictions: pd.DataFrame,
    parameters: pd.DataFrame,
    figures_dir: str | Path,
) -> list[str]:
    target = Path(figures_dir)
    target.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    grouping = ["building_id", "scenario_id", "weather_id", "carrier", "meter_boundary_id"]
    successful = parameters[parameters["fit_status"].isin(("PASS", "REVIEW"))]
    for key, group_parameters in successful.groupby(grouping, sort=True, dropna=False):
        mask = pd.Series(True, index=predictions.index)
        for column, value in zip(grouping, key):
            mask &= predictions[column].eq(value)
        group_predictions = predictions[mask]
        if group_predictions.empty:
            continue
        title = f"Building {key[0]} — {key[3]} energy signature"
        file_name = "energy-signature__" + output_component(json.dumps(list(key), default=str)) + ".svg"
        (target / file_name).write_text(
            _svg_energy_signature(group_predictions, group_parameters, title),
            encoding="utf-8",
        )
        names.append(file_name)
    return names


def build_five_parameter_report(
    input_frame: pd.DataFrame,
    outputs_root: str | Path,
    run_id: str,
    config: FiveParameterConfig | None = None,
    source_description: str = "canonical_input_frame",
) -> Path:
    """Write a new immutable regression report directory."""

    settings = (config or FiveParameterConfig()).validate()
    validate_run_id(run_id)
    validate_five_parameter_input(input_frame)
    run_dir = Path(outputs_root).resolve() / run_id
    if run_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing run directory: {run_dir}")
    run_dir.mkdir(parents=True)
    validated_inputs = run_dir / "validated_inputs"
    figures = run_dir / "figures"
    validated_inputs.mkdir()
    figures.mkdir()
    input_path = validated_inputs / "five_parameter_input.csv"
    input_frame.to_csv(input_path, index=False)

    parameters, predictions = fit_five_parameter_portfolio(input_frame, settings)
    comparison = build_simulated_measured_comparison(parameters)
    direct_metrics = build_simulated_signature_vs_measured_metrics(
        parameters, predictions
    )
    parameters.to_csv(run_dir / "regression_parameters_metrics.csv", index=False)
    predictions.to_csv(run_dir / "regression_monthly_predictions.csv", index=False)
    comparison.to_csv(run_dir / "regression_simulated_measured_comparison.csv", index=False)
    direct_metrics.to_csv(
        run_dir / "regression_simulated_signature_vs_measured_metrics.csv",
        index=False,
    )
    figure_names = write_energy_signature_figures(predictions, parameters, figures)
    manifest = {
        "run_id": run_id,
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": ('failed' if parameters['fit_status'].eq('FAILED').all()
                   else 'partial' if parameters['fit_status'].eq('FAILED').any() else 'complete'),
        "workflow": "five_parameter_post_processing",
        "source_description": source_description,
        "input_hash_sha256": _sha256(input_path),
        "regression_configuration": asdict(settings),
        "response_basis": "monthly_average_power_kW",
        "fit_equation_basis": "monthly_energy_kWh_divided_by_days",
        "residual_sign_convention": "observed_minus_predicted",
        "metric_definitions": {
            "RMSE": "sqrt(sum(residual^2)/(n-p))",
            "R2": "1-SSE/SST",
            "adjR2": "1-(1-R2)*(n-1)/(n-p)",
            "NMBE_pct": "100*sum(residual)/((n-p)*mean(observed))",
            "CV_RMSE_pct": "100*RMSE/mean(observed)",
            "NDBE_pct": "100*sum(residual)/sum(observed)",
        },
        "residual_definition": "observed_minus_predicted",
        "counts": {
            "input_rows": len(input_frame),
            "series": len(parameters),
            "successful_or_review_series": int(
                parameters["fit_status"].isin(("PASS", "REVIEW")).sum()
            ),
            "failed_series": int(parameters["fit_status"].eq("FAILED").sum()),
            "figures": len(figure_names),
            "simulated_measured_comparison_rows": len(comparison),
            "simulated_signature_vs_measured_rows": len(direct_metrics),
        },
        "files": {
            "parameters_and_metrics": "regression_parameters_metrics.csv",
            "monthly_predictions": "regression_monthly_predictions.csv",
            "simulated_measured_comparison": "regression_simulated_measured_comparison.csv",
            "simulated_signature_vs_measured_metrics": (
                "regression_simulated_signature_vs_measured_metrics.csv"
            ),
            "figures": figure_names,
        },
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8"
    )
    return run_dir


def build_five_parameter_report_from_csv(
    input_csv: str | Path,
    outputs_root: str | Path,
    run_id: str,
    config: FiveParameterConfig | None = None,
) -> Path:
    path = Path(input_csv).resolve()
    return build_five_parameter_report(
        pd.read_csv(path, dtype={"building_id": str, "scenario_id": str}),
        outputs_root,
        run_id,
        config,
        source_description=str(path),
    )


def build_five_parameter_report_from_reference_run(
    source_run_dir: str | Path,
    outputs_root: str | Path,
    run_id: str,
    config: FiveParameterConfig | None = None,
) -> Path:
    source = Path(source_run_dir).resolve()
    return build_five_parameter_report(
        reference_run_to_five_parameter_input(source),
        outputs_root,
        run_id,
        config,
        source_description=str(source),
    )
