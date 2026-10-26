"""Data-driven asset definitions; no prices, impact factors or device guessing."""
from __future__ import annotations

import json
import math
from pathlib import Path

from .contract import AssessmentInputError

UNITS = {"m2", "kW", "kWh", "L"}
MODES = {"auto", "direct"}
CATALOGUE_FIELDS = {"catalogue_id", "category_id", "asset_name", "building_layer", "kind",
                    "quantity_unit", "quantity_basis", "default_rule", "requires_quantity_basis"}
RULE_UNITS = {"opaque_wall_area": "m2", "roof_area": "m2", "ground_area": "m2",
              "glazed_area": "m2", "floor_area": "m2", "heating_design": "kW",
              "cooling_design": "kW", "dhw_recovery": "kW", "dhw_daily_volume": "L",
              "pv_roof_capacity": "kW", "roof_fraction": "m2"}
RULES = set(RULE_UNITS) | {"fixed_estimate", "asset_multiple", "asset_sum"}


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise AssessmentInputError(f"{label} must be non-empty text")
    return value.strip()


def number(value, label, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise AssessmentInputError(f"{label} must be a finite number")
    if value < 0 or (positive and value == 0):
        raise AssessmentInputError(f"{label} must be {'positive' if positive else 'non-negative'}")
    return float(value)


def fields(data, allowed, label):
    if not isinstance(data, dict):
        raise AssessmentInputError(f"{label} must be an object")
    extra = set(data) - allowed
    if extra:
        raise AssessmentInputError(f"{label}: unknown fields {sorted(extra)}")


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise AssessmentInputError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result
    def bad_constant(value):
        raise AssessmentInputError(f"non-finite JSON number {value}")
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique,
                      parse_constant=bad_constant)


def validate_catalogue(data):
    fields(data, {"schema_version", "description", "assets"}, "catalogue")
    if data.get("schema_version") != "1.0":
        raise AssessmentInputError("catalogue schema_version must be 1.0")
    assets = data.get("assets")
    if not isinstance(assets, list) or not assets:
        raise AssessmentInputError("catalogue assets must be a non-empty list")
    result = {}
    for row in assets:
        fields(row, CATALOGUE_FIELDS, "catalogue asset")
        row = dict(row)
        for key in CATALOGUE_FIELDS - {"default_rule", "requires_quantity_basis"}:
            row[key] = text(row.get(key), key)
        if not isinstance(row.get("requires_quantity_basis", False), bool):
            raise AssessmentInputError("requires_quantity_basis must be boolean")
        key = row["catalogue_id"]
        if key in result:
            raise AssessmentInputError(f"duplicate catalogue_id {key}")
        if row["quantity_unit"] not in UNITS or row["kind"] not in {"physical", "virtual"}:
            raise AssessmentInputError(f"{key}: invalid unit or asset kind")
        rule = row.get("default_rule")
        if rule is not None and rule not in RULES:
            raise AssessmentInputError(f"{key}: unknown default_rule {rule}")
        if rule in RULE_UNITS and RULE_UNITS[rule] != row["quantity_unit"]:
            raise AssessmentInputError(f"{key}: rule/unit mismatch")
        result[key] = dict(row)
    return result
