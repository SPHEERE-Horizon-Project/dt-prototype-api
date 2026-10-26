"""Compare a fresh all-engine run with the accepted shared-energy result."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dt_prototype.common.output_paths import output_component


def canonical_inventory(root: Path) -> dict[Path, Path]:
    """Match the retained pre-rename folders to current component folders.

    Only exact, hashed path components from the documented naming migration
    are translated. Table contents, identifiers and all numeric values remain
    subject to normal exact/tolerant comparison. No fuzzy filename matching.
    """
    aliases = {
        "Dynamic 5R1C": "Dynamic_RC 5R1C", "Dynamic 7R2C": "Dynamic_RC 7R2C",
        "Monthly QSS": "Monthly_SS",
        "Simplified zone sum": "Monthly_SS_simplified zone sum",
        "Simplified collapsed": "Monthly_SS_simplified collapsed",
        "dynamic_5R1C": "Dynamic_RC_5R1C", "dynamic_7R2C": "Dynamic_RC_7R2C",
        "simplified_direct_monthly_balance": "Monthly_SS_simplified_direct_monthly_balance",
        "vbdd_temperature_linear_monthly_balance": "Monthly_SS_VBDD_temperature_linear_monthly_balance",
        **{f"VB {variant} {representation}": f"Monthly_SS_VBDD {variant} {representation}"
           for variant in ("monthly", "linear", "fixed") for representation in ("zone sum", "collapsed")},
    }
    parts = {output_component(old): output_component(new) for old, new in aliases.items()}
    inventory = {}
    for relative in relative_csvs(root):
        canonical = Path(*(parts.get(part, part) for part in relative.parts))
        if canonical in inventory:
            raise AssertionError(f"Ambiguous result path after component rename: {canonical}")
        inventory[canonical] = relative
    return inventory


def read_csv(path: Path) -> pd.DataFrame:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        columns = pd.read_csv(stream, nrows=0).columns
        stream.seek(0)
        identities = {name: str for name in columns if name.endswith(("_id", "_name")) or name in {"id", "period_id"}}
        return pd.read_csv(stream, dtype=identities)


def relative_csvs(root: Path) -> list[Path]:
    return sorted(path.relative_to(root) for path in root.rglob("*.csv")) + \
           sorted(path.relative_to(root) for path in root.rglob("*.csv.gz"))


def compare_frame(reference: pd.DataFrame, candidate: pd.DataFrame, name: str) -> float:
    if list(reference.columns) != list(candidate.columns) or len(reference) != len(candidate):
        raise AssertionError(f"Schema/row mismatch: {name}")
    # Portfolio tables were sorted under the former model names. Compare their
    # explicit identities, rather than the incidental lexical model ordering.
    # Interval-only tables keep their chronological sequence unchanged.
    if "model" in reference.columns:
        row_keys = [column for column in reference if not pd.api.types.is_numeric_dtype(reference[column])]
        row_keys += [column for column in ("year", "month", "overlap_factor")
                     if column in reference and column not in row_keys]
        reference = reference.sort_values(row_keys, kind="stable").reset_index(drop=True)
        candidate = candidate.sort_values(row_keys, kind="stable").reset_index(drop=True)
    max_difference = 0.0
    for column in reference:
        left, right = reference[column], candidate[column]
        if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
            a, b = left.to_numpy(float), right.to_numpy(float)
            if not np.array_equal(np.isnan(a), np.isnan(b)):
                raise AssertionError(f"Missing-value mismatch: {name} / {column}")
            if (not np.array_equal(np.isposinf(a), np.isposinf(b))
                    or not np.array_equal(np.isneginf(a), np.isneginf(b))):
                raise AssertionError(f"Infinity mismatch: {name} / {column}")
            finite = np.isfinite(a) & np.isfinite(b)
            if finite.any():
                difference = np.abs(a[finite] - b[finite])
                tolerance = 1e-6 + 1e-9 * np.abs(a[finite])
                if (difference > tolerance).any():
                    index = int(np.flatnonzero(difference > tolerance)[0])
                    raise AssertionError(f"Numeric mismatch: {name} / {column} / finite row {index}")
                max_difference = max(max_difference, float(difference.max()))
        else:
            if not np.array_equal(left.isna(), right.isna()):
                raise AssertionError(f"Missing-value mismatch: {name} / {column}")
            a = left.fillna("").astype(str).to_numpy()
            b = right.fillna("").astype(str).to_numpy()
            if not np.array_equal(a, b):
                raise AssertionError(f"Text/category mismatch: {name} / {column}")
    return max_difference


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-code-changes", action="store_true",
                        help="Compare numerical results across a reviewed source change and report every changed code hash")
    args = parser.parse_args()
    reference, candidate = args.reference.resolve(), args.candidate.resolve()
    if not reference.is_dir() or not candidate.is_dir():
        raise AssertionError("Reference and candidate must be existing run directories")
    ref_inventory, candidate_inventory = canonical_inventory(reference), canonical_inventory(candidate)
    ref_files, candidate_files = sorted(ref_inventory), sorted(candidate_inventory)
    if not ref_files:
        raise AssertionError("Reference contains no CSV results to verify")
    if ref_files != candidate_files:
        missing = sorted(set(ref_files) - set(candidate_files))
        extra = sorted(set(candidate_files) - set(ref_files))
        raise AssertionError(f"CSV inventory mismatch; missing={missing}, extra={extra}")
    maxima = {}
    for relative in ref_files:
        maxima[str(relative)] = compare_frame(read_csv(reference / ref_inventory[relative]),
                                              read_csv(candidate / candidate_inventory[relative]), str(relative))
    ref_manifest = json.loads((reference / "manifest.json").read_text(encoding="utf-8"))
    new_manifest = json.loads((candidate / "manifest.json").read_text(encoding="utf-8"))
    for key in ("status", "version", "input_hashes", "energy_config_sha256",
                "configuration", "thermal_boundary", "excluded_services"):
        if ref_manifest[key] != new_manifest[key]:
            raise AssertionError(f"Manifest mismatch: {key}")
    # The historical Markdown report was relabelled during the naming migration.
    # Its hash is provenance, not a calculation input. Compare all reconciled
    # historical CSV values and validation results, and disclose both hashes.
    validation_before, validation_after = dict(ref_manifest["validation"]), dict(new_manifest["validation"])
    historical_before = validation_before.pop("historical_source_sha256", None)
    historical_after = validation_after.pop("historical_source_sha256", None)
    if validation_before != validation_after:
        raise AssertionError("Manifest mismatch: validation")
    if ref_manifest["status"] != "complete":
        raise AssertionError("Both runs must have status=complete")
    before, after = ref_manifest["code_hashes"], new_manifest["code_hashes"]
    changed_code = {key: {"reference": before.get(key), "candidate": after.get(key)}
                    for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)}
    if changed_code and not args.allow_code_changes:
        raise AssertionError("Manifest mismatch: code_hashes; use --allow-code-changes only for a reviewed source change")
    outcome = {
        "status": "passed",
        "csv_files_compared": len(ref_files),
        "maximum_absolute_difference": max(maxima.values(), default=0.0),
        "reference": str(reference),
        "candidate": str(candidate),
        "code_changes_allowed": args.allow_code_changes,
        "changed_code_hashes": changed_code,
        "historical_report_hashes": {"reference": historical_before, "candidate": historical_after},
        "component_path_migrations": {
            str(ref_inventory[key]): str(candidate_inventory[key]) for key in ref_files
            if ref_inventory[key] != candidate_inventory[key]
        },
        "file_maxima": maxima,
    }
    output = args.output or candidate / "reproduction_comparison.json"
    output.write_text(json.dumps(outcome, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in outcome.items()
                      if key not in {"file_maxima", "component_path_migrations", "changed_code_hashes"}}
                     | {"component_path_migrations": len(outcome["component_path_migrations"]),
                        "changed_code_files": len(changed_code)}, indent=2))


if __name__ == "__main__":
    main()
