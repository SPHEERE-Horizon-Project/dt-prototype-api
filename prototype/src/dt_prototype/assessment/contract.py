"""Strict long-form contract for externally calculated asset assessments.

The external workbook or web application owns item pricing and impact factors.
This module verifies identities, explicit sizing and result metadata before the
DT-Prototype aggregates the already-assessed asset values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from pandas.api.types import is_bool


class AssessmentInputError(ValueError):
    """Raised when an external assessment table violates the data contract."""


REQUIRED_COLUMNS = (
    "assessment_id", "building_id", "asset_id", "category_id", "asset_name",
    "building_layer", "scope_action", "base_quantity", "sizing_factor",
    "assessed_quantity", "quantity_unit", "sizing_basis", "module",
    "metric_id", "life_cycle_stage", "value", "unit", "value_basis",
    "study_period_years", "currency", "price_year", "mass_kg", "status", "source",
)
TEXT_COLUMNS = tuple(column for column in REQUIRED_COLUMNS if column not in {
    "base_quantity", "sizing_factor", "assessed_quantity", "value",
    "study_period_years", "price_year", "mass_kg",
})
NUMERIC_COLUMNS = (
    "base_quantity", "sizing_factor", "assessed_quantity", "value",
    "study_period_years", "price_year", "mass_kg",
)
MODULES = {"LCC", "LCA", "MCI"}
STATUSES = {"complete", "missing", "not_applicable"}
SCOPE_ACTIONS = {"existing", "retained", "installed", "replaced", "removed"}
VALUE_BASES = {"full_study_period", "current_asset"}


def _blank(value: object) -> bool:
    return pd.isna(value) or (isinstance(value, str) and not value.strip())


def _require_nonblank(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    for column in columns:
        bad = frame[column].map(_blank)
        if bad.any():
            rows = (frame.index[bad] + 2).tolist()
            raise AssessmentInputError(f"{column} is blank at CSV row(s) {rows}")


def load_asset_results(path: str | Path) -> pd.DataFrame:
    """Load UTF-8 CSV and return a normalized, validated table."""
    source = Path(path)
    if not source.is_file():
        raise AssessmentInputError(f"asset result file does not exist: {source}")
    try:
        # pandas otherwise silently renames duplicate headers (for example value.1).
        import csv
        with source.open(encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream), [])
        if len(header) != len(set(header)):
            raise AssessmentInputError("duplicate assessment CSV column names")
        frame = pd.read_csv(source, dtype=str, keep_default_na=False)
    except Exception as exc:  # pandas supplies the useful parser detail
        raise AssessmentInputError(f"cannot read asset result CSV: {exc}") from exc
    return validate_asset_results(frame)


def validate_asset_results(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize external asset results without changing values."""
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    extra = [column for column in frame.columns if column not in REQUIRED_COLUMNS]
    if missing or extra:
        raise AssessmentInputError(f"assessment columns mismatch; missing={missing}, extra={extra}")
    if frame.empty:
        raise AssessmentInputError("assessment table must contain at least one row")

    if frame.columns.duplicated().any():
        raise AssessmentInputError("duplicate assessment column names")
    # Reset labels so diagnostics consistently identify physical CSV row numbers.
    clean = frame.loc[:, REQUIRED_COLUMNS].copy().reset_index(drop=True)
    for column in TEXT_COLUMNS:
        clean[column] = clean[column].map(lambda value: "" if _blank(value) else str(value).strip())
    _require_nonblank(clean, (
        "assessment_id", "building_id", "asset_id", "category_id", "asset_name",
        "building_layer", "scope_action", "quantity_unit", "sizing_basis", "module",
        "metric_id", "life_cycle_stage", "unit", "value_basis", "status", "source",
    ))

    numeric_was_blank: dict[str, pd.Series] = {}
    for column in NUMERIC_COLUMNS:
        numeric_was_blank[column] = clean[column].map(_blank)
        if clean[column].map(is_bool).any():
            raise AssessmentInputError(f"{column} must be numeric, not boolean")
        clean[column] = clean[column].map(lambda value: np.nan if _blank(value) else value)
        clean[column] = pd.to_numeric(clean[column].replace("", np.nan), errors="coerce")
        invalid = ~numeric_was_blank[column] & clean[column].isna()
        if invalid.any():
            raise AssessmentInputError(f"{column} is not numeric at CSV row(s) {(clean.index[invalid] + 2).tolist()}")
        if (~np.isfinite(clean[column].dropna().to_numpy(dtype=float))).any():
            raise AssessmentInputError(f"{column} must be finite when supplied")
    for column in ("base_quantity", "sizing_factor", "assessed_quantity"):
        bad = ~np.isfinite(clean[column].to_numpy(dtype=float))
        if bad.any():
            raise AssessmentInputError(f"{column} must be finite at CSV row(s) {(clean.index[bad] + 2).tolist()}")
    if (clean["base_quantity"] < 0).any() or (clean["assessed_quantity"] < 0).any():
        raise AssessmentInputError("base_quantity and assessed_quantity must be non-negative")
    if (clean["sizing_factor"] <= 0).any():
        raise AssessmentInputError("sizing_factor must be greater than zero")
    expected = clean["base_quantity"] * clean["sizing_factor"]
    if not np.isfinite(expected).all():
        raise AssessmentInputError("base_quantity * sizing_factor must be finite")
    tolerance = 1e-6 + 1e-9 * expected.abs()
    mismatch = (clean["assessed_quantity"] - expected).abs() > tolerance
    if mismatch.any():
        raise AssessmentInputError(
            "assessed_quantity must equal base_quantity * sizing_factor at CSV row(s) "
            f"{(clean.index[mismatch] + 2).tolist()}"
        )

    invalid_modules = sorted(set(clean["module"]) - MODULES)
    invalid_statuses = sorted(set(clean["status"]) - STATUSES)
    invalid_scopes = sorted(set(clean["scope_action"]) - SCOPE_ACTIONS)
    invalid_bases = sorted(set(clean["value_basis"]) - VALUE_BASES)
    if invalid_modules:
        raise AssessmentInputError(f"unknown module value(s): {invalid_modules}")
    if invalid_statuses:
        raise AssessmentInputError(f"unknown status value(s): {invalid_statuses}")
    if invalid_scopes:
        raise AssessmentInputError(f"unknown scope_action value(s): {invalid_scopes}")
    if invalid_bases:
        raise AssessmentInputError(f"unknown value_basis value(s): {invalid_bases}")

    complete = clean["status"] == "complete"
    incomplete = ~complete
    if (~np.isfinite(clean.loc[complete, "value"].to_numpy(dtype=float))).any():
        raise AssessmentInputError("complete rows require a finite value")
    if (~numeric_was_blank["value"].loc[incomplete]).any():
        raise AssessmentInputError("missing and not_applicable rows must leave value blank")

    lcc_lca = clean["module"].isin(["LCC", "LCA"])
    if (clean.loc[lcc_lca, "value_basis"] != "full_study_period").any():
        raise AssessmentInputError("LCC and LCA asset results must use value_basis=full_study_period")
    if clean.loc[lcc_lca, "study_period_years"].isna().any() or (clean.loc[lcc_lca, "study_period_years"] <= 0).any():
        raise AssessmentInputError("LCC and LCA rows require positive study_period_years")
    if clean.loc[clean["module"] == "LCC", "currency"].eq("").any():
        raise AssessmentInputError("LCC rows require currency")
    lcc = clean["module"] == "LCC"
    if clean.loc[lcc, "price_year"].isna().any():
        raise AssessmentInputError("LCC rows require price_year")
    supplied_year = clean["price_year"].dropna()
    if ((supplied_year % 1 != 0) | (supplied_year < 1) | (supplied_year > 9999)).any():
        raise AssessmentInputError("price_year must be an integer from 1 through 9999")
    if (clean.loc[lcc, "unit"] != clean.loc[lcc, "currency"]).any():
        raise AssessmentInputError("LCC unit must match currency; supply total monetary amounts")
    if (clean["mass_kg"].dropna() < 0).any():
        raise AssessmentInputError("mass_kg must be non-negative when supplied")

    mci = clean["module"] == "MCI"
    if (clean.loc[mci, "metric_id"] != "mci").any() or (clean.loc[mci, "unit"] != "1").any():
        raise AssessmentInputError("MCI rows require metric_id=mci and unit=1")
    if (clean.loc[mci, "value_basis"] != "current_asset").any():
        raise AssessmentInputError("MCI rows require value_basis=current_asset")
    complete_mci = mci & complete
    if ((clean.loc[complete_mci, "value"] < 0) | (clean.loc[complete_mci, "value"] > 1)).any():
        raise AssessmentInputError("complete MCI values must be in [0, 1]")
    if clean.loc[complete_mci, "mass_kg"].isna().any() or (clean.loc[complete_mci, "mass_kg"] <= 0).any():
        raise AssessmentInputError("complete MCI rows require mass_kg > 0")
    if clean.loc[mci].duplicated(["assessment_id", "building_id", "asset_id"]).any():
        raise AssessmentInputError("each asset may declare only one current-asset MCI result")

    duplicate_key = ["assessment_id", "building_id", "asset_id", "module", "metric_id", "life_cycle_stage"]
    duplicated = clean.duplicated(duplicate_key, keep=False)
    if duplicated.any():
        raise AssessmentInputError(f"duplicate result keys at CSV row(s) {(clean.index[duplicated] + 2).tolist()}")

    asset_key = ["assessment_id", "building_id", "asset_id"]
    metadata = [
        "category_id", "asset_name", "building_layer", "scope_action", "base_quantity",
        "sizing_factor", "assessed_quantity", "quantity_unit", "sizing_basis",
    ]
    for column in metadata:
        counts = clean.groupby(asset_key, dropna=False)[column].nunique(dropna=False)
        if (counts > 1).any():
            raise AssessmentInputError(f"{column} is inconsistent within an asset")

    # Units and study metadata must not change inside one additive result group.
    group = ["assessment_id", "building_id", "module", "metric_id", "life_cycle_stage"]
    for column in ("unit", "value_basis", "study_period_years", "currency", "price_year"):
        counts = clean.groupby(group, dropna=False)[column].nunique(dropna=False)
        if (counts > 1).any():
            raise AssessmentInputError(f"{column} is inconsistent within an aggregate result group")

    # One scenario cannot mix different study horizons or monetary price bases.
    scenario = ["assessment_id", "building_id"]
    if (clean.loc[lcc_lca].groupby(scenario)["study_period_years"].nunique() > 1).any():
        raise AssessmentInputError("study_period_years must agree across LCC and LCA within an assessment/building")
    for column in ("currency", "price_year"):
        if (clean.loc[lcc].groupby(scenario)[column].nunique() > 1).any():
            raise AssessmentInputError(f"{column} must agree across LCC metrics within an assessment/building")

    return clean
