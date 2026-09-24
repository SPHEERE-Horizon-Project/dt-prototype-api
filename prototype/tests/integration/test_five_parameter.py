from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from dt_prototype.integration.energy_signature import build_five_parameter_report
from dt_prototype.integration.five_parameter import (
    FiveParameterConfig,
    build_simulated_measured_comparison,
    build_simulated_signature_vs_measured_metrics,
    calculate_metrics,
    fit_five_parameter,
    fit_five_parameter_portfolio,
)


def _daily_energy(temperature: np.ndarray) -> np.ndarray:
    return (
        2.0
        + 1.5 * np.maximum(0.0, 12.0 - temperature)
        + 0.8 * np.maximum(0.0, temperature - 24.0)
    )


def _portfolio_frame() -> pd.DataFrame:
    temperatures = np.array([-5, 0, 5, 10, 13, 15, 18, 21, 24, 27, 30, 32.0])
    days = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
    rows = []
    for source_type, source_id in (("simulated", "forward"), ("measured", "meter")):
        for month, (temperature, day, daily) in enumerate(
            zip(temperatures, days, _daily_energy(temperatures)), start=1
        ):
            energy = daily * day
            if source_type == "measured" and month >= 11:
                energy *= 1.10
            rows.append(
                {
                    "source_type": source_type,
                    "source_id": source_id,
                    "source_run_id": "synthetic",
                    "building_id": "B001",
                    "scenario_id": "baseline",
                    "weather_id": "weather",
                    "period_id": f"2023-{month:02d}",
                    "carrier": "electricity",
                    "meter_boundary_id": "whole_building_import",
                    "energy_kWh": energy,
                    "days": day,
                    "outdoor_temp_C": temperature,
                    "calibration_validation_flag": (
                        "calibration" if month <= 10 else "validation"
                    ),
                    "data_quality_flag": "valid",
                    "interpretation_status": "DIRECTLY_COMPARABLE",
                }
            )
    return pd.DataFrame(rows)


def test_synthetic_five_parameter_recovery_is_exact() -> None:
    temperature = np.array([-5, 0, 5, 10, 13, 15, 18, 21, 24, 27, 30, 32.0])
    fit = fit_five_parameter(temperature, _daily_energy(temperature))
    assert fit.beta_base_kWh_day == pytest.approx(2.0, abs=1e-10)
    assert fit.beta_heating_kWh_day_K == pytest.approx(1.5, abs=1e-10)
    assert fit.heating_change_point_C == pytest.approx(12.0)
    assert fit.beta_cooling_kWh_day_K == pytest.approx(0.8, abs=1e-10)
    assert fit.cooling_change_point_C == pytest.approx(24.0)
    assert fit.effective_parameter_count == 5


def test_metrics_use_observed_minus_predicted_and_distinguish_ndbe() -> None:
    observed = np.array([10.0, 20.0, 30.0])
    predicted = np.array([9.0, 18.0, 27.0])
    metrics = calculate_metrics(observed, predicted, parameter_count=1)
    assert metrics["RMSE_average_power_kW"] == pytest.approx(np.sqrt(14.0 / 2.0))
    assert metrics["NMBE_pct"] == pytest.approx(15.0)
    assert metrics["NDBE_pct"] == pytest.approx(10.0)
    assert metrics["CV_RMSE_pct"] == pytest.approx(100 * np.sqrt(7.0) / 20.0)


def test_portfolio_fit_keeps_validation_out_of_parameter_estimation() -> None:
    frame = _portfolio_frame()
    parameters, predictions = fit_five_parameter_portfolio(frame)
    assert len(parameters) == 2
    measured = parameters[parameters["source_type"].eq("measured")].iloc[0]
    simulated = parameters[parameters["source_type"].eq("simulated")].iloc[0]
    for column in (
        "beta_base_kWh_day",
        "beta_heating_kWh_day_K",
        "heating_change_point_C",
        "beta_cooling_kWh_day_K",
        "cooling_change_point_C",
    ):
        assert measured[column] == pytest.approx(simulated[column], abs=1e-10)
    assert measured["calibration_RMSE_average_power_kW"] == pytest.approx(0.0, abs=1e-10)
    assert measured["validation_RMSE_average_power_kW"] > 0.0
    measured_predictions = predictions[predictions["source_type"].eq("measured")]
    assert measured_predictions["included_in_fit"].sum() == 10
    assert measured_predictions["included_in_validation_metrics"].sum() == 2

    comparison = build_simulated_measured_comparison(parameters)
    assert set(comparison["quantity"]) >= {
        "beta_heating_average_power_kW_K",
        "calibration_R2",
        "validation_CV_RMSE_pct",
        "validation_NDBE_pct",
    }
    direct = build_simulated_signature_vs_measured_metrics(parameters, predictions)
    assert len(direct) == 1
    assert direct.iloc[0]["calibration_RMSE_average_power_kW"] == pytest.approx(
        0.0, abs=1e-10
    )
    assert direct.iloc[0]["validation_RMSE_average_power_kW"] > 0.0


def test_report_is_immutable_and_writes_table_plot_and_manifest(tmp_path) -> None:
    output = build_five_parameter_report(
        _portfolio_frame(), tmp_path, "five-parameter", FiveParameterConfig()
    )
    assert (output / "regression_parameters_metrics.csv").exists()
    assert (output / "regression_monthly_predictions.csv").exists()
    assert (output / "regression_simulated_measured_comparison.csv").exists()
    assert (
        output / "regression_simulated_signature_vs_measured_metrics.csv"
    ).exists()
    figures = list((output / "figures").glob("*.svg"))
    assert len(figures) == 1
    assert "Monthly average power (kW)" in figures[0].read_text(encoding="utf-8")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["series"] == 2
    assert manifest["residual_sign_convention"] == "observed_minus_predicted"
    with pytest.raises(FileExistsError):
        build_five_parameter_report(_portfolio_frame(), tmp_path, "five-parameter")


@pytest.mark.parametrize('column,value', [('energy_kWh', np.inf),
    ('outdoor_temp_C', -np.inf), ('energy_kWh', -1), ('outdoor_temp_C', np.nan)])
def test_invalid_validation_observation_does_not_abort_other_series(column, value):
    frame = _portfolio_frame()
    frame.loc[23, column] = value
    parameters, predictions = fit_five_parameter_portfolio(frame)
    assert len(parameters) == 2
    measured = parameters[parameters.source_type.eq('measured')].iloc[0]
    assert measured.validation_observations == 1
    assert measured.excluded_rows == 1
    rejected = predictions[predictions.source_type.eq('measured') & predictions.period_id.eq('2023-12')]
    assert not rejected.iloc[0].included_in_validation_metrics


def test_empty_input_has_actionable_error_without_partial_report(tmp_path):
    with pytest.raises(ValueError, match='at least one observation'):
        build_five_parameter_report(_portfolio_frame().iloc[:0], tmp_path, 'empty')
    assert not (tmp_path / 'empty').exists()


def test_all_failed_series_still_produce_report(tmp_path):
    frame = _portfolio_frame()
    frame['data_quality_flag'] = 'excluded'
    output = build_five_parameter_report(frame, tmp_path, 'failed')
    manifest = json.loads((output / 'manifest.json').read_text())
    assert manifest['counts']['failed_series'] == 2
    assert manifest['counts']['figures'] == 0
    assert manifest['status'] == 'failed'
    assert 'period_id' in pd.read_csv(output / 'regression_monthly_predictions.csv').columns


@pytest.mark.parametrize('run_id', ['../escape', '/absolute', r'C:\escape', 'CON'])
def test_report_run_id_cannot_escape_output_root(tmp_path, run_id):
    with pytest.raises(ValueError, match='run_id'):
        build_five_parameter_report(_portfolio_frame(), tmp_path, run_id)


def test_long_and_colliding_figure_identifiers_are_portable(tmp_path):
    frame = _portfolio_frame()
    other = frame.copy()
    frame['building_id'] = 'a/b' * 100
    other['building_id'] = 'a?b' * 100
    output = build_five_parameter_report(pd.concat([frame, other]), tmp_path, 'long')
    figures = list((output / 'figures').glob('*.svg'))
    assert len(figures) == 2
    assert all(len(p.name) < 80 for p in figures)


@pytest.mark.parametrize('settings', [FiveParameterConfig(change_point_step_C=np.nan),
    FiveParameterConfig(heating_change_point_min_C=-np.inf),
    FiveParameterConfig(minimum_observations=6.5)])
def test_invalid_regression_configuration_rejected(settings):
    with pytest.raises(ValueError):
        settings.validate()


def test_nnls_fast_path_matches_independent_active_set_enumeration():
    from itertools import combinations
    from dt_prototype.integration.five_parameter import _nonnegative_least_squares_3
    rng = np.random.default_rng(20260919)
    for _ in range(50):
        design = rng.uniform(0, 10, (12, 3))
        response = rng.uniform(0, 20, 12)
        candidates = [np.zeros(3)]
        for size in range(1, 4):
            for active in combinations(range(3), size):
                partial = np.linalg.lstsq(design[:, active], response, rcond=None)[0]
                if np.all(partial >= 0):
                    beta = np.zeros(3)
                    beta[list(active)] = partial
                    candidates.append(beta)
        expected = min(np.linalg.norm(response - design @ beta) for beta in candidates)
        actual = _nonnegative_least_squares_3(design, response)
        assert np.all(actual >= 0)
        assert np.linalg.norm(response - design @ actual) == pytest.approx(expected, abs=1e-10)


def test_excluded_split_is_counted_and_not_fitted():
    frame = _portfolio_frame()
    frame.loc[23, 'calibration_validation_flag'] = 'excluded'
    parameters, _ = fit_five_parameter_portfolio(frame)
    measured = parameters[parameters.source_type.eq('measured')].iloc[0]
    assert measured.excluded_rows == 1
    assert measured.validation_observations == 1


def test_plot_keeps_same_source_from_different_runs_separate(tmp_path):
    frame = _portfolio_frame()
    other = frame.copy()
    other['source_run_id'] = 'second-run'
    other['energy_kWh'] *= 2
    output = build_five_parameter_report(pd.concat([frame, other]), tmp_path, 'runs')
    svg = next((output / 'figures').glob('*.svg')).read_text(encoding='utf-8')
    assert svg.count('<polyline ') == 4
    assert 'second-run' in svg
