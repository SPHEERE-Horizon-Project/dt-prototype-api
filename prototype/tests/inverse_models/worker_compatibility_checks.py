"""Execute in the isolated worker, using unittest rather than adding pytest there."""
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd
from pydantic import ValidationError
import opendsm.eemeter.models.hourly.model as hourly_module

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/dt_prototype/inverse_models"))
from opendsm_compat import hourly_metrics_compatibility


class CompatibilityContract(unittest.TestCase):
    def test_zero_count_and_restoration(self):
        original = hourly_module.BaselineMetrics
        x = np.arange(100, dtype=float)
        data = pd.DataFrame({"observed": 10+x, "predicted": 11+x})
        with self.assertRaises(ValidationError):
            original(df=data, num_model_params=0)
        with hourly_metrics_compatibility() as evidence:
            metric = hourly_module.BaselineMetrics(df=data, num_model_params=0)
            self.assertEqual(metric.num_model_params, 0)
            self.assertEqual(metric.ddof, 100)
            self.assertEqual(metric.rmse, 1)
            self.assertEqual(evidence["zero_parameter_metric_calls"], 1)
            with self.assertRaises(ValidationError):
                hourly_module.BaselineMetrics(df=data, num_model_params=-1)
            a = original(df=data, num_model_params=2).model_dump_json()
            b = hourly_module.BaselineMetrics(df=data, num_model_params=2).model_dump_json()
            self.assertEqual(json.loads(a), json.loads(b))
        self.assertIs(hourly_module.BaselineMetrics, original)
        with self.assertRaisesRegex(RuntimeError, "deliberate"):
            with hourly_metrics_compatibility():
                raise RuntimeError("deliberate")
        self.assertIs(hourly_module.BaselineMetrics, original)


if __name__ == "__main__":
    unittest.main()
