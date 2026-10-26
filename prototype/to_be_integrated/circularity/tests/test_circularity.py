import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from circularity.model import CircularityInputError, aggregate_building_mci, calculate_component_mci, calculate_material_mci


class CircularityTests(unittest.TestCase):
    def test_supplied_worked_example_is_0775(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "component_case.json").read_text(encoding="utf-8"))
        result = calculate_material_mci(case["materials"][0])
        self.assertTrue(math.isclose(result["virgin_input_kg"], 500.0))
        self.assertTrue(math.isclose(result["unrecovered_mass_kg"], 100.0))
        self.assertTrue(math.isclose(result["linear_flow_index"], 0.3))
        self.assertTrue(math.isclose(result["utility_factor"], 1.2))
        self.assertTrue(math.isclose(result["mci"], 0.775))

    def test_component_score_is_material_mass_weighted(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "component_case.json").read_text(encoding="utf-8"))
        result = calculate_component_mci(case)
        component = next(row for row in result["components"] if row["component_id"] == "C02")
        rows = [row for row in result["materials"] if row["component_id"] == "C02"]
        expected = sum(row["mass_kg"] * row["mci"] for row in rows) / sum(row["mass_kg"] for row in rows)
        self.assertTrue(math.isclose(component["mci"], expected))

    def test_building_score_is_component_mass_weighted(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "building_case.json").read_text(encoding="utf-8"))
        result = aggregate_building_mci(case)
        expected = (1000 * 0.775 + 600 * 0.62 + 2400 * 0.35) / 4000
        self.assertTrue(math.isclose(result["building"]["mci"], expected))

    def test_fraction_double_counting_is_rejected(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "component_case.json").read_text(encoding="utf-8"))
        row = dict(case["materials"][0], recycled_input_fraction=0.8, reused_input_fraction=0.4)
        with self.assertRaises(CircularityInputError):
            calculate_material_mci(row)

    def test_duplicate_building_assets_are_rejected(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "building_case.json").read_text(encoding="utf-8"))
        case["components"].append(dict(case["components"][0]))
        with self.assertRaisesRegex(CircularityInputError, "duplicate component_id"):
            aggregate_building_mci(case)

    def test_duplicate_material_rows_are_rejected(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "component_case.json").read_text(encoding="utf-8"))
        case["materials"].append(dict(case["materials"][0]))
        with self.assertRaisesRegex(CircularityInputError, "duplicate component/material"):
            calculate_component_mci(case)

    def test_null_component_identity_is_rejected(self):
        root = Path(__file__).resolve().parents[1]
        case = json.loads((root / "building_case.json").read_text(encoding="utf-8"))
        case["components"][0]["component_id"] = None
        with self.assertRaisesRegex(CircularityInputError, "non-empty"):
            aggregate_building_mci(case)


if __name__ == "__main__":
    unittest.main()
