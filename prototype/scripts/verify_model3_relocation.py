"""Verify the embedded Model 3 pipeline against pre-relocation evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "20260917_model3_relocation_verification"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_csv(before: Path, after: Path, keys: list[str]) -> dict:
    left = pd.read_csv(before).sort_values(keys).reset_index(drop=True)
    right = pd.read_csv(after).sort_values(keys).reset_index(drop=True)
    if list(left.columns) != list(right.columns) or len(left) != len(right):
        raise AssertionError(f"CSV structure changed: {before} -> {after}")
    if not left[keys].equals(right[keys]):
        raise AssertionError(f"CSV keys changed: {before} -> {after}")
    numeric = list(left.select_dtypes(include="number").columns)
    delta = float((left[numeric] - right[numeric]).abs().max().max())
    np.testing.assert_allclose(
        left[numeric].to_numpy(),
        right[numeric].to_numpy(),
        rtol=1e-12,
        atol=1e-7,
        equal_nan=True,
    )
    return {
        "before": str(before.relative_to(ROOT)),
        "after": str(after.relative_to(ROOT)),
        "rows": len(left),
        "numeric_columns": len(numeric),
        "maximum_absolute_difference": delta,
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.mkdir(parents=True)

    old_root = ROOT / "archive" / "previous_layout" / "third_party" / "model3_legacy"
    new_root = ROOT / "src" / "dt_prototype" / "integration" / "model3"
    unchanged = []
    for relative in [
        Path("model3.py"),
        *sorted(path.relative_to(old_root) for path in (old_root / "example_data").glob("*.csv")),
        *sorted(path.relative_to(old_root) for path in (old_root / "reference_outputs").glob("*.csv")),
    ]:
        before = old_root / relative
        after = new_root / relative
        before_hash = sha256(before)
        after_hash = sha256(after)
        if before_hash != after_hash:
            raise AssertionError(f"Model 3 file changed: {relative}")
        unchanged.append({"file": str(relative), "sha256": after_hash})

    comparisons = []
    comparisons.append(
        compare_csv(
            ROOT / "outputs/20260917_dt_prototype_entry_points/simplified_sum/monthly.csv",
            ROOT / "outputs/20260917_model3_embedded_sum/monthly.csv",
            ["building_id", "period_id"],
        )
    )
    comparisons.append(
        compare_csv(
            ROOT / "outputs/20260917_dt_prototype_entry_points/simplified_collapsed/monthly.csv",
            ROOT / "outputs/20260917_model3_embedded_collapsed/monthly.csv",
            ["building_id", "period_id"],
        )
    )
    for name in ("physics_full_monthly.csv", "physics_model3_comparison_monthly.csv"):
        comparisons.append(
            compare_csv(
                ROOT / "outputs/20260917_dt_prototype_verification_001/seasonal_ahu" / name,
                ROOT / "outputs/20260917_model3_embedded_comparison" / name,
                ["building_id", "zone_id", "period_id"],
            )
        )

    result = {
        "status": "PASS",
        "model3_source_sha256": sha256(new_root / "model3.py"),
        "unchanged_pipeline_files": unchanged,
        "result_comparisons": comparisons,
        "maximum_absolute_difference": max(
            item["maximum_absolute_difference"] for item in comparisons
        ),
        "note": "Display/runtime metadata such as run_id and source path are intentionally excluded; all numeric result columns and stable keys are compared.",
    }
    (OUTPUT / "verification.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
