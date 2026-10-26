"""Narrow, reversible OpenDSM 1.2.7 hourly metrics compatibility.

Native hourly fitting counts nonzero coefficients, which can legitimately be
zero. Its BaselineMetrics field rejects zero before it can calculate n - p.
Accept the actual count; do not invent a parameter or change fitted predictions.
Only the worker's hourly module binding is changed, for one fit, then restored.
"""
from contextlib import contextmanager
from importlib.metadata import version

PATCH_ID = "opendsm-1.2.7-hourly-zero-coefficients-v1"


@contextmanager
def hourly_metrics_compatibility():
    import opendsm.eemeter.models.hourly.model as hourly_module
    from pydantic import Field

    if version("opendsm") != "1.2.7":
        raise RuntimeError("hourly metrics compatibility is reviewed only for OpenDSM 1.2.7")
    original = hourly_module.BaselineMetrics
    if not any(getattr(item, "ge", None) == 1
               for item in original.model_fields["num_model_params"].metadata):
        raise RuntimeError("OpenDSM metric contract changed; review compatibility before use")
    evidence = {"patch_id": PATCH_ID, "zero_parameter_metric_calls": 0,
                "parameter_count_policy": "native nonzero coefficient count, including zero"}

    class ZeroCoefficientMetrics(original):
        num_model_params: int = Field(ge=0, validate_default=True)

        def model_post_init(self, context):
            super().model_post_init(context)
            if self.num_model_params == 0:
                evidence["zero_parameter_metric_calls"] += 1

    hourly_module.BaselineMetrics = ZeroCoefficientMetrics
    try:
        yield evidence
    finally:
        hourly_module.BaselineMetrics = original
