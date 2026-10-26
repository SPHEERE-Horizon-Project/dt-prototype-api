"""Regression tests for audit comparisons that previously accepted bad results."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from scripts.verify_reproduction import canonical_inventory, compare_frame, read_csv
from dt_prototype.common.output_paths import output_component


@pytest.mark.parametrize("reference,candidate", [(1.0, np.inf), (np.inf, 1.0), (np.inf, -np.inf)])
def test_infinity_mismatches_fail(reference, candidate):
    with pytest.raises(AssertionError, match="Infinity"):
        compare_frame(pd.DataFrame({"value": [reference]}), pd.DataFrame({"value": [candidate]}), "test")


def test_numeric_tolerance_preserves_explicit_missing_values():
    left = pd.DataFrame({"value": [1.0, np.nan, np.inf]})
    right = pd.DataFrame({"value": [1.0 + 1e-7, np.nan, np.inf]})
    assert compare_frame(left, right, "test") < 1e-6


def test_missing_text_does_not_match_a_literal_missing_marker():
    with pytest.raises(AssertionError, match="Missing-value"):
        compare_frame(pd.DataFrame({"name": [None]}), pd.DataFrame({"name": ["<NA>"]}), "test")


def test_csv_identifiers_are_exact_text(tmp_path):
    reference, candidate = tmp_path / "before.csv", tmp_path / "after.csv"
    reference.write_text("building_id,energy_kWh\n001,1.0\n", encoding="utf-8")
    candidate.write_text("building_id,energy_kWh\n1,1.0\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="Text/category"):
        compare_frame(read_csv(reference), read_csv(candidate), "test")


def test_pre_rename_folder_names_match_without_modifying_table_values(tmp_path):
    old = tmp_path / "cases" / output_component("Dynamic 5R1C")
    old.mkdir(parents=True)
    (old / "energy_monthly.csv").write_text("building_id,energy_kWh\n001,1\n")
    inventory = canonical_inventory(tmp_path)
    canonical = Path("cases") / output_component("Dynamic_RC 5R1C") / "energy_monthly.csv"
    assert inventory[canonical] == (old / "energy_monthly.csv").relative_to(tmp_path)


def test_component_path_alias_collisions_fail(tmp_path):
    for label in ("Dynamic 5R1C", "Dynamic_RC 5R1C"):
        directory = tmp_path / output_component(label)
        directory.mkdir()
        (directory / "results.csv").write_text("value\n1\n")
    with pytest.raises(AssertionError, match="Ambiguous"):
        canonical_inventory(tmp_path)


def test_model_tables_align_by_identity_after_a_lexical_order_change():
    frame = pd.DataFrame({"building_id": ["001", "001"], "model": ["Monthly_SS_VBDD", "Monthly_SS_simplified"],
                          "energy_kWh": [10.0, 20.0]})
    assert compare_frame(frame, frame.iloc[::-1], "test") == 0
    invalid = frame.iloc[::-1].copy()
    invalid["energy_kWh"] = [10.0, 20.0]
    with pytest.raises(AssertionError, match="Numeric mismatch"):
        compare_frame(frame, invalid, "test")
