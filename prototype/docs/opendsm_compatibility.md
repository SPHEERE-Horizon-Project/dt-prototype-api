# OpenDSM 1.2.7 hourly metrics compatibility

The native hourly fitter counts nonzero regression coefficients for the full
model and each hour. Some hours legitimately select zero coefficients. Version
1.2.7 then constructs `BaselineMetrics(num_model_params=0)`, whose Pydantic field
requires `ge=1`, and raises after fitting. This caused both hourly variants to
fail for buildings 1 and 18 in the supplied case studies.

[opendsm_compat.py](../src/dt_prototype/inverse_models/opendsm_compat.py) provides
a narrow worker-only context manager. It subclasses the installed metric class
and permits the actual nonnegative count (`ge=0`); all metric computations remain
in the installed class. Thus degrees of freedom are computed using the native
`n-p` rule with `p=0`, without fabricating a coefficient or setting `p=1`.
This preserves the native coefficient-count convention; it does not introduce
a new effective-degrees-of-freedom method or re-estimate an intercept count.

The adapter changes only the hourly module's metric binding for the duration of
one fit and restores it even on failure. It rejects other OpenDSM versions or an
unexpected original field constraint. It does not modify `site-packages`, fitted
coefficients, training data, predictions, library-wide billing metrics, temporal
features or solver equations. Workers execute tasks sequentially, so this local
context does not race other fits. A future parallel worker must preserve that
isolation or replace the context design.

Artifacts and manifests record patch ID
`opendsm-1.2.7-hourly-zero-coefficients-v1` and the number of zero-count metric
constructions. Affected models expose
`HOURLY_ZERO_COEFFICIENT_METRICS_COMPATIBILITY` and remain marked for review.
Native warnings/disqualifications are retained; `allow_disqualified` keeps its
existing explicit semantics. Older saved models can still be loaded without
inventing compatibility metadata.

The five-building rerun completes all 20 requested models. Every one of the
52,680 previously available predictions is unchanged. The four additional
hourly fits now produce inspectable predictions and scores. All native
uncertainty entries in this supplied comparison remain missing, as before;
the fix does **not** establish uncertainty calibration or supply missing values.
Single-year simulation fitting does not establish observed-building accuracy.

Regression tests reproduce the original metric exception, verify true-zero
counts, compare all serialized metrics for a positive count, reject negative
counts, check restoration after exceptions, and fit/reload the former failure
fixture. Full five-building evidence and plots are linked from the
[implementation report](reliability_improvements_20261023.md).

Upstream development includes broader hourly uncertainty/metric changes in the
[OpenDSM changelog](https://github.com/opendsm/opendsm/blob/master/CHANGELOG.md).
A wholesale upgrade would require separate validation of predictions and
uncertainty; this release retains the pinned dependency and the scoped fix.
