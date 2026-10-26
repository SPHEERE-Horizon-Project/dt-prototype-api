"""Verify standalone benchmarks and cached formula companions without Excel.

This checks saved formula results and source agreement. Native Excel input
perturbation and normative/empirical validation are separate verification tasks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
for module in ("LCC", "LCA", "Circularity"):
    sys.path.insert(0, str(ROOT / "to_be_integrated" / module.lower() / "src"))

from lcc.model import calculate_lcc
from lca.model import calculate_lca
from circularity.model import aggregate_building_mci, calculate_component_mci


def verify() -> dict:
    report = {"status": "passed", "modules": {}, "workbook_engine": "saved cached values; no native Excel automation"}
    for module, calculate in (("LCC", calculate_lcc), ("LCA", calculate_lca)):
        folder = ROOT / "to_be_integrated" / module.lower()
        source = folder / "benchmark_case.json"
        case = json.loads(source.read_text(encoding="utf-8"))
        result = calculate(case)
        maximum = 0.0
        for cell, expected in case["expected_outputs"].items():
            actual = next(value for key, value in result["intermediates"].items() if key.startswith(cell + "_"))
            error = abs(actual - expected)
            if not math.isfinite(actual) or error > 1e-6 + 1e-9 * abs(expected):
                raise AssertionError(f"{module}: {cell} differs from source benchmark")
            maximum = max(maximum, error)

        workbook_path = folder / f"{module.lower()}_calculation.xlsx"
        workbook = openpyxl.load_workbook(workbook_path, data_only=True, read_only=True)
        checks = 0
        for row in workbook["Check"].iter_rows(values_only=True):
            if not row or row[0] not in case["expected_outputs"]:
                continue
            _, _, actual, expected, status, *_ = row
            if not isinstance(actual, (int, float)) or not math.isfinite(actual):
                raise AssertionError(f"{module}: unavailable cached workbook result {row[0]}")
            if abs(actual - expected) > 1e-6 + 1e-9 * abs(expected) or status is not True:
                raise AssertionError(f"{module}: failed cached workbook check {row[0]}")
            checks += 1
        workbook.close()
        if checks != len(case["expected_outputs"]):
            raise AssertionError(f"{module}: incomplete workbook benchmark coverage")
        report["modules"][module] = {
            "python_source_comparisons": len(case["expected_outputs"]),
            "maximum_absolute_difference": maximum,
            "cached_workbook_comparisons": checks,
            "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "workbook_sha256": hashlib.sha256(workbook_path.read_bytes()).hexdigest(),
        }

    folder = ROOT / "to_be_integrated/circularity"
    component = calculate_component_mci(json.loads((folder / "component_case.json").read_text(encoding="utf-8")))
    building = aggregate_building_mci(json.loads((folder / "building_case.json").read_text(encoding="utf-8")))
    if abs(component["materials"][0]["mci"] - 0.775) > 1e-12 or abs(building["building"]["mci"] - 0.49675) > 1e-12:
        raise AssertionError("Circularity: worked examples differ")
    report["modules"]["Circularity"] = {"material_example_mci": 0.775, "building_example_mci": 0.49675}
    report["code_hashes"] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for directory in (ROOT / "src/dt_prototype/assessment", ROOT / "to_be_integrated")
        for path in sorted(directory.rglob("*.py"))
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "code_hashes"}, indent=2))


if __name__ == "__main__":
    main()
