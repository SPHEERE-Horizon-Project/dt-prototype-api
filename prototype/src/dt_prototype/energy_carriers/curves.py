"""Transparent least-squares approximation of supplied performance samples."""
import numpy as np
from .config import PerformanceCurve, text


def fit_performance_curve(temperature_C, performance, *, degree, source, out_of_range="error"):
    """Fit a constant, linear or polynomial curve and return coefficients plus diagnostics.

    Samples must describe the same service, supply-temperature regime and load
    conditions. This function does not infer missing equipment performance data.
    """
    t, y = np.asarray(temperature_C, dtype=float), np.asarray(performance, dtype=float)
    text(source, "performance sample source")
    if type(degree) is not int or not 0 <= degree <= 5:
        raise ValueError("degree must be an integer from zero through five")
    if t.ndim != 1 or y.shape != t.shape or len(t) < degree + 2:
        raise ValueError("Require paired samples and at least degree+2 observations")
    if not np.isfinite(t).all() or not np.isfinite(y).all() or (y <= 0).any():
        raise ValueError("Samples must be finite with strictly positive performance")
    if len(np.unique(t)) < degree + 2:
        raise ValueError("Insufficient distinct temperatures for the requested fit")
    polynomial = np.polynomial.Polynomial.fit(t, y, degree).convert()
    data = dict(coefficients=polynomial.coef.tolist(), temperature_min_C=float(t.min()),
                temperature_max_C=float(t.max()), out_of_range=out_of_range, source=source)
    curve = PerformanceCurve.from_dict(data)
    predicted, _ = curve.evaluate(t)
    residual = predicted-y
    variation = np.sum((y-y.mean())**2)
    diagnostics = dict(samples=len(t), degree=degree, RMSE=float(np.sqrt(np.mean(residual**2))),
        max_abs_error=float(np.max(np.abs(residual))),
        R_squared=float(1-np.sum(residual**2)/variation) if variation > 0 else None,
        temperature_C=t.tolist(), observed=y.tolist(), fitted=predicted.tolist(), residual=residual.tolist(),
        interpretation="in-sample approximation diagnostics; no independent validation")
    return data, diagnostics
