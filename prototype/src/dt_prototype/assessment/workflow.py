"""Downstream assessment workflow for static assets and operational results."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__
from .contract import AssessmentInputError, load_asset_results, validate_asset_results


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate_assets(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and aggregate declared assets; completeness refers to supplied rows.

    An absent asset/indicator row cannot be inferred. Explicit missing rows are
    required to represent gaps in the external assessment inventory.
    """
    frame = validate_asset_results(frame)
    records: list[dict[str, object]] = []
    group_columns = [
        "assessment_id", "building_id", "module", "metric_id", "life_cycle_stage",
        "unit", "value_basis", "study_period_years", "currency", "price_year",
    ]
    for key, group in frame.groupby(group_columns, dropna=False, sort=True):
        row = dict(zip(group_columns, key))
        applicable = group[group["status"] != "not_applicable"]
        missing_count = int((applicable["status"] == "missing").sum())
        complete = applicable[applicable["status"] == "complete"]
        row.update(
            asset_count=int(group["asset_id"].nunique()),
            complete_asset_count=int(complete["asset_id"].nunique()),
            missing_asset_count=missing_count,
            not_applicable_asset_count=int((group["status"] == "not_applicable").sum()),
        )
        if applicable.empty:
            row.update(value=np.nan, mass_kg=np.nan, status="not_applicable")
        elif missing_count or complete.empty:
            row.update(value=np.nan, mass_kg=np.nan, status="missing")
        elif row["module"] == "MCI":
            total_mass = float(complete["mass_kg"].sum())
            if not np.isfinite(total_mass):
                raise AssessmentInputError("MCI total mass overflowed")
            row.update(
                # Normalize first to avoid overflowing an otherwise valid weighted sum.
                value=float((complete["value"] * (complete["mass_kg"] / total_mass)).sum()),
                mass_kg=total_mass,
                status="complete",
            )
        else:
            row.update(value=float(complete["value"].sum()), mass_kg=np.nan, status="complete")
        if row["status"] == "complete" and not np.isfinite(row["value"]):
            raise AssessmentInputError("building asset aggregate overflowed")
        records.append(row)
    return pd.DataFrame.from_records(records)


OPERATIONAL_METRICS = {
    "grid_import_kWh": ("grid_import_energy", "kWh/year"),
    "grid_export_kWh": ("grid_export_energy", "kWh/year"),
    "pv_self_consumed_kWh": ("pv_self_consumed_energy", "kWh/year"),
    "import_primary_nonrenewable_kWh": ("import_primary_nonrenewable", "kWh primary/year"),
    "import_primary_renewable_kWh": ("import_primary_renewable", "kWh primary/year"),
    "net_primary_total_kWh": ("net_primary_total", "kWh primary/year"),
    "import_carbon_kgCO2e": ("import_carbon", "kg CO2e/year"),
    "export_carbon_kgCO2e": ("export_carbon_credit", "kg CO2e/year"),
    "net_carbon_kgCO2e": ("net_carbon", "kg CO2e/year"),
    "import_energy_cost": ("import_energy_cost", "{currency}/year"),
    "export_energy_credit": ("export_energy_credit", "{currency}/year"),
    "net_energy_cost": ("net_energy_cost", "{currency}/year"),
}


def _operational_results(energy: pd.DataFrame, currency: str, building_ids: set[str]) -> pd.DataFrame:
    required = {"building_id", "building_name", "year", "model", "representation", "resolution", *OPERATIONAL_METRICS}
    missing = sorted(required - set(energy.columns))
    if missing:
        raise AssessmentInputError(f"energy_annual.csv is missing columns: {missing}")
    energy = energy.copy()
    identity = ["building_id", "building_name", "year", "model", "representation", "resolution"]
    for column in identity:
        if energy[column].isna().any() or energy[column].astype(str).str.strip().eq("").any():
            raise AssessmentInputError(f"energy_annual.csv has blank {column}")
    energy["building_id"] = energy["building_id"].astype(str).str.strip()
    absent = sorted(building_ids - set(energy["building_id"]))
    if absent:
        raise AssessmentInputError(f"asset building_id values absent from energy results: {absent}")
    energy = energy[energy["building_id"].isin(building_ids)]
    if energy.duplicated(["building_id", "year", "model", "representation", "resolution"]).any():
        raise AssessmentInputError("energy_annual.csv contains duplicate annual case identities")
    if not energy["resolution"].isin(["dynamic", "monthly"]).all():
        raise AssessmentInputError("energy resolution must be dynamic or monthly")
    years = pd.to_numeric(energy["year"], errors="coerce")
    if (not np.isfinite(years).all() or (years % 1 != 0).any()
            or (years < 1).any() or (years > 9999).any()):
        raise AssessmentInputError("energy year must be an integer from 1 through 9999")
    records: list[dict[str, object]] = []
    for _, source in energy.iterrows():
        for column, (metric_id, unit_template) in OPERATIONAL_METRICS.items():
            value = source[column]
            try:
                numeric = float(value)
            except (TypeError, ValueError) as error:
                raise AssessmentInputError(f"{column} must be numeric") from error
            if isinstance(value, (bool, np.bool_)) or not np.isfinite(numeric):
                raise AssessmentInputError(f"{column} contains a non-finite value")
            row = {key: source[key] for key in identity}
            row.update(
                metric_id=metric_id,
                value=float(value),
                unit=unit_template.format(currency=currency),
                value_basis="annual_operation",
                source="Energy_carriers/energy_annual.csv",
            )
            records.append(row)
    return pd.DataFrame.from_records(records)


def run_assessment(asset_results: str | Path, output: str | Path, energy_results: str | Path | None = None,
                   asset_quantities: str | Path | None = None) -> Path:
    """Validate, aggregate and export assessment results to a new directory."""
    source = Path(asset_results).resolve()
    out = Path(output).resolve()
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite {out}")
    assets = load_asset_results(source)
    if asset_quantities is not None:
        from .quantities import check_assessment_quantities
        check_assessment_quantities(assets, asset_quantities)
    out.mkdir(parents=True)
    manifest: dict[str, object] = {
        "status": "running",
        "schema_version": "1.0",
        "component_version": __version__,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "asset_results_sha256": _sha256(source),
        "asset_result_rows": len(assets),
        "building_count": int(assets["building_id"].nunique()),
        "assessment_count": int(assets["assessment_id"].nunique()),
        "static_results_are_solver_independent": True,
        "sizing_rule": "assessed_quantity = base_quantity * sizing_factor",
        "aggregated_values_are_not_rescaled": True,
        "asset_coverage": "declared_rows_only; absent asset/metric combinations are not inferred",
        "code_hashes": {path.name: _sha256(path) for path in sorted(Path(__file__).parent.glob("*.py"))},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    try:
        if asset_quantities is not None:
            manifest["asset_quantities_sha256"] = _sha256(Path(asset_quantities))
        assets.to_csv(out / "validated_asset_results.csv", index=False)
        aggregate = aggregate_assets(assets)
        aggregate.to_csv(out / "building_asset_results.csv", index=False)
        if energy_results is not None:
            energy_input = Path(energy_results).resolve()
            energy_file = energy_input / "energy_annual.csv" if energy_input.is_dir() else energy_input
            if not energy_file.is_file():
                raise AssessmentInputError(f"energy annual results do not exist: {energy_file}")
            config = energy_file.parent / "energy_config_resolved.json"
            if not config.is_file():
                raise AssessmentInputError("energy_config_resolved.json is required to identify operational currency")
            currency = json.loads(config.read_text(encoding="utf-8")).get("currency")
            if not isinstance(currency, str) or not currency.strip():
                raise AssessmentInputError("energy configuration requires non-empty currency")
            energy_manifest = energy_file.parent / "manifest.json"
            if energy_manifest.is_file():
                if json.loads(energy_manifest.read_text(encoding="utf-8")).get("status") != "complete":
                    raise AssessmentInputError("Energy_carriers manifest must have status=complete")
                manifest["energy_manifest_sha256"] = _sha256(energy_manifest)
            # Treat identifiers as text even when all values look like numbers.
            energy = pd.read_csv(energy_file, dtype={"building_id": str}, keep_default_na=False)
            operational = _operational_results(energy, currency, set(assets["building_id"].astype(str)))
            operational.to_csv(out / "building_operational_results.csv", index=False)
            manifest.update(
                energy_results_sha256=_sha256(energy_file),
                energy_result_rows=len(operational),
                energy_currency=currency,
                energy_config_sha256=_sha256(config),
            )
        manifest.update(
            status="complete",
            building_asset_result_rows=len(aggregate),
            completed_utc=datetime.now(timezone.utc).isoformat(),
        )
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return out
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(error).__name__}: {error}"
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        raise
