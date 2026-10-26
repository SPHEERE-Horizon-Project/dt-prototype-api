import json
import math
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lcc.model import LCCInputError, calculate_lcc


class BenchmarkTests(unittest.TestCase):
    def test_source_cached_outputs_within_agreed_tolerance(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "benchmark_case.json").read_text(encoding="utf-8"))
        result = calculate_lcc(case)
        values = result["intermediates"]
        for cell, reference in case["expected_outputs"].items():
            actual = next(value for key, value in values.items() if key.startswith(cell + "_"))
            self.assertTrue(math.isclose(actual, reference, rel_tol=1e-9, abs_tol=1e-6), cell)

    def test_explicit_sizing_is_exposed_without_changing_benchmark(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "benchmark_case.json").read_text(encoding="utf-8"))
        result = calculate_lcc(case)
        heat_pump = next(row for row in result["technology_details"] if row["asset_id"] == "heat_pump_system")
        self.assertEqual(heat_pump["base_size"], 3)
        self.assertEqual(heat_pump["sizing_factor"], 1)
        self.assertEqual(heat_pump["size"], 3)

        invalid = deepcopy(case)
        invalid["technologies"][0]["sizing_factor"] = 1.1
        with self.assertRaises(LCCInputError):
            calculate_lcc(invalid)

    def test_invalid_rates_fail_before_real_discount_division(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "benchmark_case.json").read_text(encoding="utf-8"))
        for field in ("market_inflation_rate", "market_interest_rate_nominal", "product_inflation_rate"):
            with self.subTest(field=field):
                invalid = deepcopy(case)
                invalid["assumptions"][field] = -1
                with self.assertRaises(LCCInputError):
                    calculate_lcc(invalid)

    def test_renovation_only_cli_exports_empty_detail(self):
        from lcc.cli import main
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "benchmark_case.json").read_text(encoding="utf-8"))
        case["technologies"] = []
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "case.json", Path(directory) / "results"
            source.write_text(json.dumps(case), encoding="utf-8")
            main(["--input", str(source), "--output", str(output)])
            self.assertEqual(json.loads((output / "manifest.json").read_text())["status"], "complete")
            self.assertEqual(len((output / "technology_costs.csv").read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
