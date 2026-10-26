"""Strict configuration and bounded polynomial technology performance.

Coefficients are ascending powers of outdoor temperature in degrees Celsius.
Factors are dimensionless or per kWh of imported/exported carrier, as named.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import json
from pathlib import Path
import re

import numpy as np
from dt_prototype.common.json_io import load_json

SERVICES = ("zone_heating", "ahu_heating", "zone_cooling", "ahu_cooling", "dhw")
FACTOR_FIELDS = (
    "primary_nonrenewable", "primary_renewable", "carbon_kgCO2e_per_kWh",
    "import_price_per_kWh", "export_primary_nonrenewable", "export_primary_renewable",
    "export_carbon_kgCO2e_per_kWh", "export_price_per_kWh",
)


def keys(value, allowed, required, context):
    if not isinstance(value, dict):
        raise ValueError(f"{context}: expected object")
    extra, missing = set(value) - set(allowed), set(required) - set(value)
    if extra or missing:
        raise ValueError(f"{context}: unknown {sorted(extra)}, missing {sorted(missing)}")


def number(value, name, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
        raise ValueError(f"{name}: expected finite number")
    if low is not None and value < low or high is not None and value > high:
        raise ValueError(f"{name}: outside [{low}, {high}]")
    return float(value)


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: expected nonempty text")


def monthly_values(value, name, low=0.0, high=None):
    values = value if isinstance(value, list) else [value] * 12
    if len(values) != 12:
        raise ValueError(f"{name}: expected scalar or twelve January–December values")
    return np.array([number(v, name, low, high) for v in values])


@dataclass(frozen=True)
class PerformanceCurve:
    coefficients: tuple[float, ...]
    temperature_min_C: float
    temperature_max_C: float
    out_of_range: str
    source: str

    @classmethod
    def from_dict(cls, data):
        fields = {"coefficients", "temperature_min_C", "temperature_max_C", "out_of_range", "source"}
        keys(data, fields, fields, "performance")
        c = data["coefficients"]
        if not isinstance(c, list) or not 1 <= len(c) <= 6:
            raise ValueError("performance: require one to six ascending coefficients")
        c = tuple(number(v, "coefficient") for v in c)
        lo = number(data["temperature_min_C"], "temperature_min_C")
        hi = number(data["temperature_max_C"], "temperature_max_C")
        if hi <= lo or data["out_of_range"] not in ("clip", "error"):
            raise ValueError("performance: invalid temperature domain or out_of_range policy")
        text(data["source"], "performance.source")
        # Check the full polynomial domain, including internal extrema, not just endpoints.
        derivative = np.polynomial.polynomial.polyder(c)
        roots = np.polynomial.polynomial.polyroots(derivative) if np.any(derivative) else []
        probes = [lo, hi] + [float(r.real) for r in roots if abs(r.imag) < 1e-9 and lo < r.real < hi]
        values = np.polynomial.polynomial.polyval(probes, c)
        if not np.isfinite(values).all() or np.min(values) <= 0:
            raise ValueError("performance must be finite and strictly positive throughout its domain")
        return cls(c, lo, hi, data["out_of_range"], data["source"])

    def evaluate(self, temperature):
        t = np.asarray(temperature, dtype=float)
        if not np.isfinite(t).all():
            raise ValueError("nonfinite curve temperature")
        outside = (t < self.temperature_min_C) | (t > self.temperature_max_C)
        if outside.any() and self.out_of_range == "error":
            raise ValueError("temperature outside technology performance domain")
        result = np.polynomial.polynomial.polyval(
            np.clip(t, self.temperature_min_C, self.temperature_max_C), self.coefficients
        )
        if not np.isfinite(result).all() or (result <= 0).any():
            raise ValueError("invalid evaluated performance")
        return result, outside


@dataclass(frozen=True)
class EnergyConfig:
    data: dict
    sha256: str

    @classmethod
    def load(cls, path):
        return cls.from_dict(load_json(path))

    @classmethod
    def from_dict(cls, data):
        data = copy.deepcopy(data)
        fields = {"schema_version", "scenario_id", "description", "currency", "technologies", "carriers", "buildings"}
        keys(data, fields, fields, "energy configuration")
        if data["schema_version"] != "1.0":
            raise ValueError("Expected energy schema_version 1.0")
        for name in ("scenario_id", "description", "currency"):
            text(data[name], name)
        for name in ("technologies", "carriers", "buildings"):
            if not isinstance(data[name], dict) or not data[name]:
                raise ValueError(f"{name}: expected nonempty object")
        if "electricity" not in data["carriers"]:
            raise ValueError("electricity carrier factors are required")
        for carrier, factors in data["carriers"].items():
            if not re.fullmatch(r"[a-z][a-z0-9_]*", carrier):
                raise ValueError(f"Invalid carrier identifier: {carrier}")
            keys(factors, {*FACTOR_FIELDS, "source"}, {*FACTOR_FIELDS, "source"}, carrier)
            text(factors["source"], "factor source")
            for field in FACTOR_FIELDS:
                # Negative tariffs are legitimate; physical/impact factors are nonnegative here.
                monthly_values(factors[field], field, low=None if "price" in field else 0.0)
        for name, tech in data["technologies"].items():
            fields = {"carrier", "performance", "distribution_efficiency", "emission_efficiency",
                      "regulation_efficiency", "auxiliary_kWh_per_kWh_generated", "description"}
            keys(tech, fields, fields, f"technology {name}")
            text(tech["description"], "technology description")
            if tech["carrier"] not in data["carriers"]:
                raise ValueError(f"Missing factors for {tech['carrier']}")
            PerformanceCurve.from_dict(tech["performance"])
            for field in ("distribution_efficiency", "emission_efficiency", "regulation_efficiency"):
                if number(tech[field], field, 0, 1) == 0:
                    raise ValueError(f"{field} must be > 0")
            if np.prod([tech[k] for k in ("distribution_efficiency", "emission_efficiency", "regulation_efficiency")]) == 0:
                raise ValueError("Efficiency-chain product underflows to zero")
            number(tech["auxiliary_kWh_per_kWh_generated"], "auxiliary fraction", 0)
        for bid, building in data["buildings"].items():
            text(bid, "building ID")
            fields = {"services", "pv", "solar_thermal", "fan_W_per_m3_h", "base_auxiliary_W", "source"}
            keys(building, fields, fields, f"building {bid}")
            keys(building["services"], SERVICES, SERVICES, "services")
            for tech in building["services"].values():
                if tech not in data["technologies"]:
                    raise ValueError(f"Unknown service technology {tech}")
            for field in ("fan_W_per_m3_h", "base_auxiliary_W"):
                number(building[field], field, 0)
            text(building["source"], "building source")
            pv = building["pv"]
            fields = {"roof_coverage", "module_kWp_per_m2", "performance_ratio", "monthly_factor",
                      "factor_basis", "source"}
            keys(pv, fields, fields, "pv")
            number(pv["roof_coverage"], "pv coverage", 0, 1)
            number(pv["module_kWp_per_m2"], "PV module density", 0)
            number(pv["performance_ratio"], "PV performance ratio", 0, 1)
            monthly_values(pv["monthly_factor"], "PV monthly factor", 0, 1)
            if pv["factor_basis"] not in ("overlap", "generation"):
                raise ValueError("pv.factor_basis must be overlap or generation")
            text(pv["source"], "PV source")
            st = building["solar_thermal"]
            fields = {"roof_coverage", "eta0", "a1_W_m2K", "a2_W_m2K2", "mean_fluid_temperature_C",
                      "monthly_utilisation", "source"}
            keys(st, fields, fields, "solar_thermal")
            number(st["roof_coverage"], "ST coverage", 0, 1)
            number(st["eta0"], "ST optical efficiency", 0, 1)
            number(st["a1_W_m2K"], "ST a1", 0)
            number(st["a2_W_m2K2"], "ST a2", 0)
            number(st["mean_fluid_temperature_C"], "ST mean fluid temperature")
            monthly_values(st["monthly_utilisation"], "ST monthly utilisation", 0, 1)
            text(st["source"], "ST source")
            if pv["roof_coverage"] + st["roof_coverage"] > 1 + 1e-12:
                raise ValueError("PV and solar thermal exceed available roof area")
        digest = hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()
        return cls(data, digest)

    def building(self, building_id):
        if str(building_id) not in self.data["buildings"]:
            raise ValueError(f"No energy configuration for building {building_id}")
        return self.data["buildings"][str(building_id)]
