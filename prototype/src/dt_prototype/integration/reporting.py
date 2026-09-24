"""Immutable, auditable tabular reports for completed comparison runs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

from dt_prototype.integration.project_paths import example_data_dir
from dt_prototype.common.output_paths import validate_run_id


_KEYS = ["building_id", "scenario_id", "weather_id", "period_id", "zone_id"]
_MONTHLY_QUANTITIES = [
    "H_total_W_K",
    "total_gain_kWh",
    "useful_heating_kWh",
    "useful_cooling_kWh",
]
_ENERGY_QUANTITIES = ["total_gain_kWh", "useful_heating_kWh", "useful_cooling_kWh"]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise_zone_ids(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["zone_id"] = result["zone_id"].fillna("__building_aggregate__").astype(str)
    return result


def _building_names(project_root: Path | None) -> dict[str, str]:
    """Read names from the supplied immutable example geometry, when available."""

    path = example_data_dir(project_root) / "example_district.geojson"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(feature["properties"]["id"]): str(feature["properties"].get("Name", ""))
        for feature in data.get("features", [])
    }


def _relative_difference_pct(reference: pd.Series, comparison: pd.Series) -> pd.Series:
    difference = comparison - reference
    return difference.where(reference != 0).div(reference.where(reference != 0)).mul(100.0)


def _prepare_monthly_table(reference: pd.DataFrame, comparison: pd.DataFrame) -> pd.DataFrame:
    reference = _normalise_zone_ids(reference)
    comparison = _normalise_zone_ids(comparison)
    for label, frame in (("reference", reference), ("comparison", comparison)):
        if frame.duplicated(_KEYS).any():
            raise ValueError(f"{label} physics output has duplicate comparison keys")

    ref = reference[_KEYS + _MONTHLY_QUANTITIES].rename(
        columns={name: f"semi_stationary_{name}" for name in _MONTHLY_QUANTITIES}
    )
    new = comparison[_KEYS + _MONTHLY_QUANTITIES].rename(
        columns={name: f"integrated_model3_{name}" for name in _MONTHLY_QUANTITIES}
    )
    monthly = ref.merge(new, on=_KEYS, how="outer", validate="one_to_one", indicator=True)
    if not (monthly["_merge"] == "both").all():
        missing = monthly.loc[monthly["_merge"] != "both", _KEYS + ["_merge"]]
        raise ValueError(f"Physics outputs do not share a complete key set: {missing.to_dict('records')}")
    monthly = monthly.drop(columns="_merge")
    for quantity in _MONTHLY_QUANTITIES:
        reference_name = f"semi_stationary_{quantity}"
        comparison_name = f"integrated_model3_{quantity}"
        monthly[f"difference_{quantity}"] = monthly[comparison_name] - monthly[reference_name]
        monthly[f"difference_{quantity}_pct"] = _relative_difference_pct(
            monthly[reference_name], monthly[comparison_name]
        )
    return monthly.sort_values(_KEYS).reset_index(drop=True)


def _case_scope(zone_id: str) -> str:
    return "building_aggregate" if zone_id == "__building_aggregate__" else f"individual_zone:{zone_id}"


def _annual_table(monthly: pd.DataFrame, building_names: dict[str, str]) -> pd.DataFrame:
    case_keys = ["building_id", "scenario_id", "weather_id", "zone_id"]
    records: list[dict[str, object]] = []
    for key, case in monthly.groupby(case_keys, sort=True, dropna=False):
        building_id, scenario_id, weather_id, zone_id = key
        record: dict[str, object] = {
            "building_id": building_id,
            "building_name": building_names.get(str(building_id), ""),
            "case_scope": _case_scope(zone_id),
            "scenario_id": scenario_id,
            "weather_id": weather_id,
            "months": int(len(case)),
        }
        for quantity in _ENERGY_QUANTITIES:
            ref_name = f"semi_stationary_{quantity}"
            new_name = f"integrated_model3_{quantity}"
            ref_value = float(case[ref_name].sum())
            new_value = float(case[new_name].sum())
            record[ref_name] = ref_value
            record[new_name] = new_value
            record[f"difference_{quantity}"] = new_value - ref_value
            record[f"difference_{quantity}_pct"] = (
                None if ref_value == 0.0 else (new_value - ref_value) / ref_value * 100.0
            )

        # H_total is a static coefficient for the current cases.  An hours-weighted
        # mean keeps this definition correct if a future input varies it by month.
        # Every period represents one month; this is an ordinary mean until the
        # report contract adds an explicit per-period weighting field.
        for engine in ("semi_stationary", "integrated_model3"):
            record[f"{engine}_H_total_W_K"] = float(case[f"{engine}_H_total_W_K"].mean())
        record["difference_H_total_W_K"] = (
            record["integrated_model3_H_total_W_K"] - record["semi_stationary_H_total_W_K"]
        )
        ref_h = float(record["semi_stationary_H_total_W_K"])
        record["difference_H_total_W_K_pct"] = (
            None
            if ref_h == 0.0
            else float(record["difference_H_total_W_K"]) / ref_h * 100.0
        )
        record["comparison_interpretation"] = (
            "APPROXIMATE: independent two-zone aggregate is collapsed to one Model 3 zone; "
            "use individual-zone rows for the closest comparison."
            if zone_id == "__building_aggregate__" and str(building_id) in {"1", "18", "19", "20"}
            else "APPROXIMATE: Model 3 uses mapped annual-mean air exchange, constant setpoints, "
            "nearest mass class, and prescribed reference total gains."
        )
        records.append(record)
    return pd.DataFrame(records).sort_values(["building_id", "case_scope"]).reset_index(drop=True)


def _markdown_table(annual: pd.DataFrame, comparison_label: str) -> str:
    """Return a compact human-readable table without rounding the CSV values."""

    display = annual[
        [
            "building_id",
            "building_name",
            "case_scope",
            "semi_stationary_useful_heating_kWh",
            "integrated_model3_useful_heating_kWh",
            "difference_useful_heating_kWh_pct",
            "semi_stationary_useful_cooling_kWh",
            "integrated_model3_useful_cooling_kWh",
            "difference_useful_cooling_kWh_pct",
        ]
    ].copy()
    display.columns = [
        "Building ID",
        "Building",
        "Case",
        "Semi-stationary heating (kWh)",
        "Integrated Model 3 heating (kWh)",
        "Heating difference (%)",
        "Semi-stationary cooling (kWh)",
        "Integrated Model 3 cooling (kWh)",
        "Cooling difference (%)",
    ]
    for name in display.columns[3:]:
        display[name] = display[name].map(lambda value: "—" if pd.isna(value) else f"{value:,.1f}")
    markdown_columns = list(display.columns)
    markdown_rows = [
        "| " + " | ".join(markdown_columns) + " |",
        "| " + " | ".join("---" for _ in markdown_columns) + " |",
    ]
    for row in display.itertuples(index=False, name=None):
        markdown_rows.append("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |")
    return "\n".join(
        [
            "# Side-by-side annual useful-energy comparison",
            "",
            "Reference: validated ISO 13790-style semi-stationary implementation. "
            f"Comparison: {comparison_label}.",
            "",
            *markdown_rows,
            "",
            "The values are a cross-model comparison, not empirical validation. Model 3 values are approximate "
            "because of the documented input and calculation-boundary mappings.",
            "",
        ]
    )


def build_side_by_side_report(
    source_run_dir: Path,
    outputs_root: Path,
    report_run_id: str,
    project_root: Path | None = None,
) -> Path:
    """Create a new immutable table report from a completed verification run."""
    validate_run_id(report_run_id)
    source_run_dir = Path(source_run_dir)
    outputs_root = Path(outputs_root)
    report_dir = outputs_root / report_run_id
    if report_dir.exists():
        raise FileExistsError(f"Refusing to overwrite completed or existing report: {report_dir}")

    reference_path = source_run_dir / "physics_full_monthly.csv"
    comparison_path = source_run_dir / "physics_model3_comparison_monthly.csv"
    source_manifest_path = source_run_dir / "manifest.json"
    for required in (reference_path, comparison_path, source_manifest_path):
        if not required.is_file():
            raise FileNotFoundError(f"Required completed-run artifact is missing: {required}")

    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    comparison_mode = source_manifest.get("comparison_mode", "legacy")
    comparison_label = (
        "integrated, independently calculated Model 3 seasonal/AHU mode"
        if comparison_mode == "seasonal_ahu"
        else "integrated, independently calculated Model 3 legacy adapter"
    )
    monthly = _prepare_monthly_table(pd.read_csv(reference_path), pd.read_csv(comparison_path))
    annual = _annual_table(monthly, _building_names(project_root))
    if len(annual) != 13 or len(monthly) != 156:
        raise ValueError(
            "Unexpected supplied-case report shape; expected 13 annual cases and 156 monthly rows, "
            f"received {len(annual)} and {len(monthly)}."
        )

    report_dir.mkdir(parents=True)
    monthly.to_csv(report_dir / "monthly_side_by_side_outputs.csv", index=False)
    annual.to_csv(report_dir / "annual_side_by_side_outputs.csv", index=False)
    (report_dir / "annual_side_by_side_outputs.md").write_text(
        _markdown_table(annual, comparison_label), encoding="utf-8"
    )
    manifest = {
        "run_id": report_run_id,
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete",
        "report_type": "side_by_side_output_comparison",
        "source_run_id": source_manifest["run_id"],
        "source_run_manifest_sha256": _sha256_file(source_manifest_path),
        "comparison_mode": comparison_mode,
        "reference_engine": source_manifest["engine_names_versions"]["semi_stationary"],
        "comparison_engine": source_manifest["engine_names_versions"]["model3_legacy"],
        "annual_cases": int(len(annual)),
        "monthly_rows": int(len(monthly)),
        "comparison_statement": (
            "This report is a cross-model comparison. It is not empirical validation. "
            "Model 3 values retain the source run's approximate mapping limitations."
        ),
        "files": [
            "annual_side_by_side_outputs.csv",
            "annual_side_by_side_outputs.md",
            "monthly_side_by_side_outputs.csv",
        ],
    }
    (report_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return report_dir
