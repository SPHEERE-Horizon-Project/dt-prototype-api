import json
import math
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lca.model import LCAInputError, calculate_lca


class BenchmarkTests(unittest.TestCase):
    def test_source_cached_outputs_within_agreed_tolerance(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "benchmark_case.json").read_text(encoding="utf-8"))
        result = calculate_lca(case)
        values = result["intermediates"]
        for cell, reference in case["expected_outputs"].items():
            matching = next(value for key, value in values.items() if key.startswith(cell + "_"))
            self.assertTrue(math.isclose(matching, reference, rel_tol=1e-9, abs_tol=1e-6), cell)

    def test_arbitrary_indicator_is_calculated_per_item_and_aggregated(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "benchmark_case.json").read_text(encoding="utf-8"))
        case = deepcopy(case)
        case["indicator_definitions"] = [{
            "id": "ap", "name": "Acidification potential", "unit": "mol H+e",
            "factor_unit": "mol H+e per declared quantity unit",
        }]
        for index, technology in enumerate(case["technologies"], start=1):
            technology["indicator_factors"] = {"ap": float(index)}
        case["renovation"]["indicator_factors"] = {"ap": 0.5}

        result = calculate_lca(case)
        expected_annual = sum(
            index * technology["size"] / technology["lifetime_years"]
            for index, technology in enumerate(case["technologies"], start=1)
        ) + 0.5 * case["project"]["net_floor_area_m2"] / case["project"]["lifetime_years"]
        expected_total = sum(
            math.ceil(case["project"]["lifetime_years"] / technology["lifetime_years"])
            * index * technology["size"]
            for index, technology in enumerate(case["technologies"], start=1)
        ) + 0.5 * case["project"]["net_floor_area_m2"]
        self.assertTrue(math.isclose(result["indicator_results"]["ap"]["annual"], expected_annual))
        self.assertTrue(math.isclose(result["indicator_results"]["ap"]["project_total"], expected_total))
        self.assertEqual(len(result["technology_details"]), len(case["technologies"]))

    def test_missing_indicator_factor_is_reported_without_false_zero(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "benchmark_case.json").read_text(encoding="utf-8"))
        case = deepcopy(case)
        case["indicator_definitions"] = [{"id": "wdp", "name": "Water deprivation", "unit": "m3 world-e deprived"}]
        result = calculate_lca(case)
        self.assertEqual(result["indicator_results"]["wdp"]["status"], "missing factors")
        self.assertIsNone(result["indicator_results"]["wdp"]["project_total"])

    def test_explicit_sizing_and_clarified_asset_names(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "benchmark_case.json").read_text(encoding="utf-8"))
        result = calculate_lca(case)
        by_id = {row["asset_id"]: row for row in result["technology_details"]}
        self.assertEqual(by_id["heat_pump_system"]["name"], "Heat pump system")
        self.assertEqual(by_id["heat_pump_system"]["base_size"], 3)
        self.assertEqual(by_id["dhw_heat_pump"]["name"], "DHW heat pump")
        self.assertEqual(by_id["pv_system"]["size_unit"], "kW")

        invalid = deepcopy(case)
        invalid["technologies"][0]["sizing_factor"] = 0
        with self.assertRaises(LCAInputError):
            calculate_lca(invalid)

    def test_zero_quantity_with_missing_factor_does_not_crash_or_block_totals(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "benchmark_case.json").read_text(encoding="utf-8"))
        expected = calculate_lca(case)["indicator_results"]["gwp_total"]["project_total"]
        unused = next(item for item in case["technologies"] if item["size"] == 0)
        unused.pop("embodied_carbon_kg_per_unit")
        unused["indicator_factors"] = {"gwp_total": None}
        result = calculate_lca(case)
        self.assertAlmostEqual(result["indicator_results"]["gwp_total"]["project_total"], expected)
        row = next(item for item in result["technology_details"] if item["asset_id"] == unused["asset_id"])
        self.assertEqual(row["impacts"]["gwp_total"]["project_total"], 0)
        self.assertIsNone(row["impacts"]["gwp_total"]["factor_per_unit"])

    def test_empty_technology_cli_and_catalog_provenance(self):
        from lca.cli import main
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "benchmark_case.json").read_text(encoding="utf-8"))
        case["technologies"] = []
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "case.json"
            output = Path(directory) / "results"
            source.write_text(json.dumps(case), encoding="utf-8")
            main(["--input", str(source), "--indicator-catalog", str(root / "indicator_catalog.json"), "--output", str(output)])
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertTrue(manifest["indicator_catalog_sha256"])
            self.assertTrue(manifest["resolved_input_sha256"])
            self.assertEqual(len((output / "technology_impacts.csv").read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
