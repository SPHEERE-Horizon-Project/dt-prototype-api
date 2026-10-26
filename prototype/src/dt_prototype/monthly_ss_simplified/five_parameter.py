"""Bounded five-parameter monthly energy-signature regression.

The module is deliberately independent from both forward-physics engines.  It
fits monthly energy normalized to average daily energy and reports equivalent
average-power coefficients.  Residuals are always observed minus predicted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Iterable

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = (
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
)

GROUP_COLUMNS = (
    "source_type",
    "source_id",
    "source_run_id",
    "building_id",
    "scenario_id",
    "weather_id",
    "carrier",
    "meter_boundary_id",
)

_GOOD_QUALITY_FLAGS = frozenset({"valid", "ok", "pass", "good"})


@dataclass(frozen=True)
class FiveParameterConfig:
    """Explicit regression settings; defaults reproduce the legacy search grid.

    These are verification defaults, not universal production bounds.  Real
    meter analyses should declare project-specific values in the run manifest.
    """

    heating_change_point_min_C: float = 8.0
    heating_change_point_max_C: float = 20.0
    cooling_change_point_min_C: float = 14.0
    cooling_change_point_max_C: float = 26.0
    change_point_step_C: float = 0.5
    minimum_observations: int = 6
    minimum_regime_observations: int = 2
    minimum_temperature_span_C: float = 5.0
    coefficient_lower_bound: float = 0.0

    def validate(self) -> "FiveParameterConfig":
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
                raise ValueError(f'{name} must be finite and numeric')
        for name in ('minimum_observations', 'minimum_regime_observations'):
            if not isinstance(getattr(self, name), int):
                raise ValueError(f'{name} must be an integer')
        if self.heating_change_point_max_C < self.heating_change_point_min_C:
            raise ValueError("heating change-point bounds are reversed")
        if self.cooling_change_point_max_C < self.cooling_change_point_min_C:
            raise ValueError("cooling change-point bounds are reversed")
        if self.change_point_step_C <= 0:
            raise ValueError("change_point_step_C must be positive")
        if self.minimum_observations < 6:
            raise ValueError("a 5P fit requires at least six observations")
        if self.minimum_regime_observations < 1:
            raise ValueError("minimum_regime_observations must be positive")
        if self.minimum_temperature_span_C < 0:
            raise ValueError("minimum_temperature_span_C must be non-negative")
        if self.coefficient_lower_bound != 0.0:
            raise ValueError("the lean solver currently supports a zero lower bound")
        return self


@dataclass(frozen=True)
class FiveParameterFit:
    beta_base_kWh_day: float
    beta_heating_kWh_day_K: float
    heating_change_point_C: float
    beta_cooling_kWh_day_K: float
    cooling_change_point_C: float
    sse_kWh_day_squared: float
    formal_parameter_count: int
    effective_parameter_count: int
    heating_regime_observations: int
    cooling_regime_observations: int
    fit_status: str
    warning_codes: tuple[str, ...]

    def predict_daily_energy(self, outdoor_temp_C: Iterable[float]) -> np.ndarray:
        temperature = np.asarray(tuple(outdoor_temp_C), dtype=float)
        return (
            self.beta_base_kWh_day
            + self.beta_heating_kWh_day_K
            * np.maximum(0.0, self.heating_change_point_C - temperature)
            + self.beta_cooling_kWh_day_K
            * np.maximum(0.0, temperature - self.cooling_change_point_C)
        )


def _grid(lower: float, upper: float, step: float) -> np.ndarray:
    count = int(np.floor((upper - lower) / step + 1e-12))
    values = lower + step * np.arange(count + 1, dtype=float)
    if values[-1] < upper - 1e-10:
        values = np.append(values, upper)
    return values


def _nonnegative_least_squares_3(design: np.ndarray, response: np.ndarray) -> np.ndarray:
    """Solve a three-coefficient NNLS problem by enumerating active sets."""

    # A feasible, full-rank unconstrained optimum also solves NNLS. Keep the
    # active-set search for boundary/rank-deficient cases and its tie behavior.
    unconstrained, _, rank, _ = np.linalg.lstsq(design, response, rcond=None)
    if rank == 3 and np.all(unconstrained > 1e-10):
        return unconstrained
    best_beta = np.zeros(3, dtype=float)
    best_sse = float(np.dot(response, response))
    for size in range(1, 4):
        for active in combinations(range(3), size):
            partial = unconstrained if size == 3 else np.linalg.lstsq(design[:, active], response, rcond=None)[0]
            if np.any(partial < -1e-10):
                continue
            beta = np.zeros(3, dtype=float)
            beta[list(active)] = np.maximum(partial, 0.0)
            residual = response - design @ beta
            sse = float(np.dot(residual, residual))
            if sse < best_sse - 1e-12:
                best_sse = sse
                best_beta = beta
    return best_beta


def fit_five_parameter(
    outdoor_temp_C: Iterable[float],
    average_daily_energy_kWh_day: Iterable[float],
    config: FiveParameterConfig | None = None,
) -> FiveParameterFit:
    """Fit the 5P model with grid-searched change points and bounded coefficients."""

    settings = (config or FiveParameterConfig()).validate()
    temperature = np.asarray(tuple(outdoor_temp_C), dtype=float)
    response = np.asarray(tuple(average_daily_energy_kWh_day), dtype=float)
    if temperature.shape != response.shape or temperature.ndim != 1:
        raise ValueError("temperature and response must be one-dimensional and aligned")
    if len(response) < settings.minimum_observations:
        raise ValueError(
            f"at least {settings.minimum_observations} valid calibration observations are required"
        )
    if not np.all(np.isfinite(temperature)) or not np.all(np.isfinite(response)):
        raise ValueError("temperature and response must be finite")
    if np.any(response < 0):
        raise ValueError("negative energy is not supported at this physical boundary")

    best: tuple[float, np.ndarray, float, float] | None = None
    for heating_cp in _grid(
        settings.heating_change_point_min_C,
        settings.heating_change_point_max_C,
        settings.change_point_step_C,
    ):
        heating = np.maximum(0.0, heating_cp - temperature)
        for cooling_cp in _grid(
            settings.cooling_change_point_min_C,
            settings.cooling_change_point_max_C,
            settings.change_point_step_C,
        ):
            if cooling_cp < heating_cp:
                continue
            cooling = np.maximum(0.0, temperature - cooling_cp)
            design = np.column_stack((np.ones_like(temperature), heating, cooling))
            beta = _nonnegative_least_squares_3(design, response)
            residual = response - design @ beta
            sse = float(np.dot(residual, residual))
            candidate = (sse, beta, float(heating_cp), float(cooling_cp))
            if best is None or candidate[0] < best[0] - 1e-12:
                best = candidate

    if best is None:
        raise ValueError("no admissible change-point pair was available")
    sse, beta, heating_cp, cooling_cp = best
    heating_count = int(np.sum(temperature < heating_cp))
    cooling_count = int(np.sum(temperature > cooling_cp))
    tolerance = max(1e-10, float(np.max(response)) * 1e-10)
    heating_active = beta[1] > tolerance and heating_count >= settings.minimum_regime_observations
    cooling_active = beta[2] > tolerance and cooling_count >= settings.minimum_regime_observations
    effective_parameters = 1 + (2 if heating_active else 0) + (2 if cooling_active else 0)

    warnings: list[str] = []
    if float(np.ptp(temperature)) < settings.minimum_temperature_span_C:
        warnings.append("INSUFFICIENT_TEMPERATURE_SPAN")
    if heating_count < settings.minimum_regime_observations:
        warnings.append("HEATING_REGIME_UNOBSERVED")
    if cooling_count < settings.minimum_regime_observations:
        warnings.append("COOLING_REGIME_UNOBSERVED")
    if beta[0] <= tolerance:
        warnings.append("BASE_COEFFICIENT_AT_LOWER_BOUND")
    if beta[1] <= tolerance:
        warnings.append("HEATING_COEFFICIENT_AT_LOWER_BOUND")
    if beta[2] <= tolerance:
        warnings.append("COOLING_COEFFICIENT_AT_LOWER_BOUND")
    if heating_cp in {
        settings.heating_change_point_min_C,
        settings.heating_change_point_max_C,
    }:
        warnings.append("HEATING_CHANGE_POINT_AT_BOUND")
    if cooling_cp in {
        settings.cooling_change_point_min_C,
        settings.cooling_change_point_max_C,
    }:
        warnings.append("COOLING_CHANGE_POINT_AT_BOUND")
    if effective_parameters >= len(response):
        warnings.append("NONPOSITIVE_DEGREES_OF_FREEDOM")

    return FiveParameterFit(
        beta_base_kWh_day=float(beta[0]),
        beta_heating_kWh_day_K=float(beta[1]),
        heating_change_point_C=heating_cp,
        beta_cooling_kWh_day_K=float(beta[2]),
        cooling_change_point_C=cooling_cp,
        sse_kWh_day_squared=sse,
        formal_parameter_count=5,
        effective_parameter_count=effective_parameters,
        heating_regime_observations=heating_count,
        cooling_regime_observations=cooling_count,
        fit_status="PASS" if not warnings else "REVIEW",
        warning_codes=tuple(warnings),
    )


def calculate_metrics(
    observed_average_power_kW: Iterable[float],
    predicted_average_power_kW: Iterable[float],
    parameter_count: int,
) -> dict[str, float]:
    """Return requested metrics using observed-minus-predicted residuals.

    RMSE, NMBE, and CV(RMSE) use ``n - parameter_count``.  NDBE is the net
    percentage error in total energy/power and intentionally has no parameter
    correction.  Undefined normalized or variance metrics are returned as NaN.
    """

    observed = np.asarray(tuple(observed_average_power_kW), dtype=float)
    predicted = np.asarray(tuple(predicted_average_power_kW), dtype=float)
    if observed.shape != predicted.shape or observed.ndim != 1:
        raise ValueError("observed and predicted values must be aligned")
    if not np.all(np.isfinite(observed)) or not np.all(np.isfinite(predicted)):
        raise ValueError("metric inputs must be finite")
    n = len(observed)
    denominator_dof = n - parameter_count
    residual = observed - predicted
    sse = float(np.dot(residual, residual))
    mean_observed = float(np.mean(observed)) if n else float("nan")
    sum_observed = float(np.sum(observed))
    sst = float(np.dot(observed - mean_observed, observed - mean_observed)) if n else 0.0
    rmse = float(np.sqrt(sse / denominator_dof)) if denominator_dof > 0 else float("nan")
    r2 = 1.0 - sse / sst if sst > 0 else float("nan")
    adjusted_r2 = (
        1.0 - (1.0 - r2) * (n - 1) / denominator_dof
        if denominator_dof > 0 and np.isfinite(r2)
        else float("nan")
    )
    nmbe = (
        100.0 * float(np.sum(residual)) / (denominator_dof * mean_observed)
        if denominator_dof > 0 and mean_observed != 0
        else float("nan")
    )
    cv_rmse = 100.0 * rmse / mean_observed if mean_observed != 0 else float("nan")
    ndbe = (
        100.0 * float(np.sum(residual)) / sum_observed
        if sum_observed != 0
        else float("nan")
    )
    return {
        "observations": n,
        "degrees_of_freedom": denominator_dof,
        "RMSE_average_power_kW": rmse,
        "R2": r2,
        "adjR2": adjusted_r2,
        "NMBE_pct": nmbe,
        "CV_RMSE_pct": cv_rmse,
        "NDBE_pct": ndbe,
    }


def validate_five_parameter_input(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate the canonical long-form regression input without mutating it."""

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required 5P input columns: {', '.join(missing)}")
    if frame.empty:
        raise ValueError('5P input must contain at least one observation')
    data = frame.copy()
    for column in (*GROUP_COLUMNS, 'period_id'):
        if data[column].isna().any() or data[column].astype(str).str.strip().eq('').any():
            raise ValueError(f'{column} must contain nonempty identifiers')
    splits = data['calibration_validation_flag'].astype(str).str.lower()
    if not splits.isin(('calibration', 'validation', 'excluded')).all():
        raise ValueError('calibration_validation_flag must be calibration, validation or excluded')
    if not data['source_type'].astype(str).str.lower().isin(('simulated', 'measured')).all():
        raise ValueError('source_type must be simulated or measured')
    key = [*GROUP_COLUMNS, "period_id"]
    duplicates = data.duplicated(key, keep=False)
    if duplicates.any():
        rendered = data.loc[duplicates, key].head(3).to_dict(orient="records")
        raise ValueError(f"duplicate 5P input keys: {rendered}")
    for column in ("energy_kWh", "days", "outdoor_temp_C"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    invalid_days = data["days"].notna() & ((data["days"] <= 0) | (data["days"] > 31))
    if invalid_days.any():
        raise ValueError("days must be positive and no greater than 31")
    return data


def _empty_metrics(prefix: str) -> dict[str, float]:
    return {
        f"{prefix}_observations": 0,
        f"{prefix}_degrees_of_freedom": 0,
        f"{prefix}_RMSE_average_power_kW": float("nan"),
        f"{prefix}_R2": float("nan"),
        f"{prefix}_adjR2": float("nan"),
        f"{prefix}_NMBE_pct": float("nan"),
        f"{prefix}_CV_RMSE_pct": float("nan"),
        f"{prefix}_NDBE_pct": float("nan"),
    }


def _prefixed_metrics(
    prefix: str,
    observed: np.ndarray,
    predicted: np.ndarray,
    parameter_count: int,
) -> dict[str, float]:
    if len(observed) == 0:
        return _empty_metrics(prefix)
    metrics = calculate_metrics(observed, predicted, parameter_count)
    return {f"{prefix}_{name}": value for name, value in metrics.items()}


def fit_five_parameter_portfolio(
    frame: pd.DataFrame,
    config: FiveParameterConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit each source/building/carrier series with per-series error isolation."""

    settings = (config or FiveParameterConfig()).validate()
    data = validate_five_parameter_input(frame)
    parameter_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []

    for group_key, unordered in data.groupby(list(GROUP_COLUMNS), sort=True, dropna=False):
        group = unordered.sort_values("period_id").copy()
        identity = dict(zip(GROUP_COLUMNS, group_key))
        quality_ok = group["data_quality_flag"].astype(str).str.lower().isin(_GOOD_QUALITY_FLAGS)
        finite = np.isfinite(group[["energy_kWh", "days", "outdoor_temp_C"]]).all(axis=1)
        usable = (quality_ok & finite & group['energy_kWh'].ge(0)
                  & ~group['calibration_validation_flag'].astype(str).str.lower().eq('excluded'))
        calibration = usable & group["calibration_validation_flag"].astype(str).str.lower().eq("calibration")
        validation = usable & group["calibration_validation_flag"].astype(str).str.lower().eq("validation")
        row: dict[str, object] = {
            **identity,
            "response_basis": "monthly_average_power",
            "residual_sign_convention": "observed_minus_predicted",
            "total_rows": len(group),
            "usable_rows": int(usable.sum()),
            "excluded_rows": int((~usable).sum()),
            "fit_status": "FAILED",
            "warning_codes": "",
            "formal_parameter_count": 5,
            "effective_parameter_count": 0,
        }
        interpretation = (
            str(group["interpretation_status"].iloc[0])
            if "interpretation_status" in group.columns
            else "DIRECTLY_COMPARABLE"
        )
        row["interpretation_status"] = interpretation
        try:
            fit = fit_five_parameter(
                group.loc[calibration, "outdoor_temp_C"],
                group.loc[calibration, "energy_kWh"] / group.loc[calibration, "days"],
                settings,
            )
        except (ValueError, np.linalg.LinAlgError) as exc:
            row.update(
                {
                    "warning_codes": f"FIT_FAILED:{str(exc).replace(',', ';')}",
                    **_empty_metrics("calibration"),
                    **_empty_metrics("validation"),
                }
            )
            parameter_rows.append(row)
            continue

        daily_prediction = fit.predict_daily_energy(group["outdoor_temp_C"])
        power_prediction = daily_prediction / 24.0
        power_observed = group["energy_kWh"].to_numpy(dtype=float) / (
            24.0 * group["days"].to_numpy(dtype=float)
        )
        warning_codes = list(fit.warning_codes)
        if (~usable).any():
            warning_codes.append("ROWS_EXCLUDED_BY_QUALITY_OR_MISSING_DATA")
        if not validation.any():
            warning_codes.append("NO_VALIDATION_OBSERVATIONS")
        row.update(asdict(fit))
        row["warning_codes"] = "|".join(dict.fromkeys(warning_codes))
        row["fit_status"] = "PASS" if not warning_codes else "REVIEW"
        row["beta_base_average_power_kW"] = fit.beta_base_kWh_day / 24.0
        row["beta_heating_average_power_kW_K"] = fit.beta_heating_kWh_day_K / 24.0
        row["beta_cooling_average_power_kW_K"] = fit.beta_cooling_kWh_day_K / 24.0
        row.update(
            _prefixed_metrics(
                "calibration",
                power_observed[calibration.to_numpy()],
                power_prediction[calibration.to_numpy()],
                fit.effective_parameter_count,
            )
        )
        row.update(
            _prefixed_metrics(
                "validation",
                power_observed[validation.to_numpy()],
                power_prediction[validation.to_numpy()],
                0,
            )
        )
        parameter_rows.append(row)

        for position, (_, source_row) in enumerate(group.iterrows()):
            observed_power = power_observed[position]
            predicted_power = power_prediction[position]
            prediction_rows.append(
                {
                    **identity,
                    "period_id": source_row["period_id"],
                    "calibration_validation_flag": source_row[
                        "calibration_validation_flag"
                    ],
                    "data_quality_flag": source_row["data_quality_flag"],
                    "days": source_row["days"],
                    "outdoor_temp_C": source_row["outdoor_temp_C"],
                    "observed_energy_kWh": source_row["energy_kWh"],
                    "predicted_energy_kWh": daily_prediction[position] * source_row["days"],
                    "residual_energy_kWh": source_row["energy_kWh"]
                    - daily_prediction[position] * source_row["days"],
                    "observed_average_power_kW": observed_power,
                    "predicted_average_power_kW": predicted_power,
                    "residual_average_power_kW": observed_power - predicted_power,
                    "included_in_fit": bool(calibration.iloc[position]),
                    "included_in_validation_metrics": bool(validation.iloc[position]),
                }
            )

    parameters = pd.DataFrame(parameter_rows)
    predictions = pd.DataFrame(prediction_rows, columns=[*GROUP_COLUMNS, 'period_id',
        'calibration_validation_flag', 'data_quality_flag', 'days', 'outdoor_temp_C',
        'observed_energy_kWh', 'predicted_energy_kWh', 'residual_energy_kWh',
        'observed_average_power_kW', 'predicted_average_power_kW', 'residual_average_power_kW',
        'included_in_fit', 'included_in_validation_metrics'])
    return parameters, predictions


_COMPARISON_QUANTITIES = {
    "beta_base_average_power_kW": "kW",
    "beta_heating_average_power_kW_K": "kW/K",
    "heating_change_point_C": "degC",
    "beta_cooling_average_power_kW_K": "kW/K",
    "cooling_change_point_C": "degC",
    "calibration_RMSE_average_power_kW": "kW",
    "calibration_R2": "1",
    "calibration_adjR2": "1",
    "calibration_NMBE_pct": "%",
    "calibration_CV_RMSE_pct": "%",
    "calibration_NDBE_pct": "%",
    "validation_RMSE_average_power_kW": "kW",
    "validation_R2": "1",
    "validation_adjR2": "1",
    "validation_NMBE_pct": "%",
    "validation_CV_RMSE_pct": "%",
    "validation_NDBE_pct": "%",
}

_COMPARISON_COLUMNS = (
    "building_id",
    "scenario_id",
    "weather_id",
    "carrier",
    "meter_boundary_id",
    "measured_source_id",
    "simulated_source_id",
    "quantity",
    "unit",
    "measured_value",
    "simulated_value",
    "simulated_minus_measured",
    "relative_difference_pct",
    "interpretation_status",
)


def build_simulated_measured_comparison(parameters: pd.DataFrame) -> pd.DataFrame:
    """Create a long-form like-for-like comparison when both source types exist."""

    rows: list[dict[str, object]] = []
    pairing = ["building_id", "scenario_id", "weather_id", "carrier", "meter_boundary_id"]
    for pair_key, group in parameters.groupby(pairing, sort=True, dropna=False):
        measured = group[group["source_type"].astype(str).str.lower().eq("measured")]
        simulated = group[group["source_type"].astype(str).str.lower().eq("simulated")]
        for _, measured_row in measured.iterrows():
            for _, simulated_row in simulated.iterrows():
                for quantity, unit in _COMPARISON_QUANTITIES.items():
                    measured_value = measured_row.get(quantity, float("nan"))
                    simulated_value = simulated_row.get(quantity, float("nan"))
                    absolute_difference = (
                        float(simulated_value) - float(measured_value)
                        if pd.notna(measured_value) and pd.notna(simulated_value)
                        else float("nan")
                    )
                    relative_difference = (
                        100.0 * absolute_difference / abs(float(measured_value))
                        if pd.notna(measured_value)
                        and float(measured_value) != 0
                        and pd.notna(simulated_value)
                        else float("nan")
                    )
                    rows.append(
                        {
                            **dict(zip(pairing, pair_key)),
                            "measured_source_id": measured_row["source_id"],
                            "simulated_source_id": simulated_row["source_id"],
                            "quantity": quantity,
                            "unit": unit,
                            "measured_value": measured_value,
                            "simulated_value": simulated_value,
                            "simulated_minus_measured": absolute_difference,
                            "relative_difference_pct": relative_difference,
                            "interpretation_status": (
                                "DIRECTLY_COMPARABLE"
                                if measured_row["meter_boundary_id"]
                                == simulated_row["meter_boundary_id"]
                                else "INVALID_CARRIER_BOUNDARY"
                            ),
                        }
                    )
    return pd.DataFrame(rows, columns=_COMPARISON_COLUMNS)


def build_simulated_signature_vs_measured_metrics(
    parameters: pd.DataFrame,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    """Evaluate each simulated fitted signature directly against measured points.

    The simulated signature is not re-fitted to measured observations here, so
    the comparison metrics use ``p=0``.  Calibration and validation subsets
    remain separate and are selected by the measured-series flags.
    """

    pairing = ["building_id", "scenario_id", "weather_id", "carrier", "meter_boundary_id"]
    rows: list[dict[str, object]] = []
    for pair_key, group in parameters.groupby(pairing, sort=True, dropna=False):
        measured = group[
            group["source_type"].astype(str).str.lower().eq("measured")
            & group["fit_status"].isin(("PASS", "REVIEW"))
        ]
        simulated = group[
            group["source_type"].astype(str).str.lower().eq("simulated")
            & group["fit_status"].isin(("PASS", "REVIEW"))
        ]
        for _, measured_row in measured.iterrows():
            observed_rows = predictions[
                predictions["source_type"].astype(str).str.lower().eq("measured")
                & predictions["source_id"].eq(measured_row["source_id"])
                & predictions["source_run_id"].eq(measured_row["source_run_id"])
            ]
            for column, value in zip(pairing, pair_key):
                observed_rows = observed_rows[observed_rows[column].eq(value)]
            for _, simulated_row in simulated.iterrows():
                temperature = observed_rows["outdoor_temp_C"].to_numpy(dtype=float)
                simulated_power = (
                    float(simulated_row["beta_base_average_power_kW"])
                    + float(simulated_row["beta_heating_average_power_kW_K"])
                    * np.maximum(
                        0.0,
                        float(simulated_row["heating_change_point_C"]) - temperature,
                    )
                    + float(simulated_row["beta_cooling_average_power_kW_K"])
                    * np.maximum(
                        0.0,
                        temperature - float(simulated_row["cooling_change_point_C"]),
                    )
                )
                observed_power = observed_rows["observed_average_power_kW"].to_numpy(
                    dtype=float
                )
                calibration = observed_rows["included_in_fit"].to_numpy(dtype=bool)
                validation = observed_rows[
                    "included_in_validation_metrics"
                ].to_numpy(dtype=bool)
                rows.append(
                    {
                        **dict(zip(pairing, pair_key)),
                        "measured_source_id": measured_row["source_id"],
                        "simulated_source_id": simulated_row["source_id"],
                        "metric_parameter_count": 0,
                        "residual_sign_convention": "measured_minus_simulated_signature",
                        **_prefixed_metrics(
                            "calibration",
                            observed_power[calibration],
                            simulated_power[calibration],
                            0,
                        ),
                        **_prefixed_metrics(
                            "validation",
                            observed_power[validation],
                            simulated_power[validation],
                            0,
                        ),
                    }
                )
    columns = [
        *pairing,
        "measured_source_id",
        "simulated_source_id",
        "metric_parameter_count",
        "residual_sign_convention",
        *_empty_metrics("calibration").keys(),
        *_empty_metrics("validation").keys(),
    ]
    return pd.DataFrame(rows, columns=columns)
