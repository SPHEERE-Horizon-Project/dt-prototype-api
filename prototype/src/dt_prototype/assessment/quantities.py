"""Resolve a common inventory before external LCC/LCA/MCI assessment.

Auto is estimate times factor. Direct is the entered quantity with factor one.
This module does not change geometry, equipment limits or carrier efficiencies.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .catalogue import (MODES, RULES, RULE_UNITS, fields, load_json, number, text,
                        validate_catalogue)
from .contract import AssessmentInputError, SCOPE_ACTIONS

QUANTITY_FIELDS = ["assessment_id", "building_id", "asset_id", "catalogue_id", "category_id",
    "asset_name", "building_layer", "scope_action", "quantity_mode", "quantity_unit",
    "quantity_basis", "estimated_quantity", "direct_quantity", "base_quantity", "sizing_factor",
    "assessed_quantity", "rule_id", "rule_version", "sizing_basis", "source", "status", "diagnostic"]
ASSET_INPUT_FIELDS = {"asset_id", "catalogue_id", "quantity_mode", "direct_quantity", "auto_factor",
                     "quantity_unit", "quantity_basis", "rule_id", "parameters", "scope_action", "source"}


class MissingEstimate(Exception):
    """An explicitly requested driver/input is unavailable; never use zero."""


class ProjectQuantityContext:
    """Lazy common geometry/sizing drivers, independent of the selected solver.

    Static preliminary sizing uses Monthly_SS parameter assembly and shared AHU
    recovery. No hidden 1.2 allowance is applied; the asset auto_factor owns it.
    """
    def __init__(self, config):
        from dt_prototype.common.project import ProjectInputs
        self.project = ProjectInputs.load(config)
        self.district = None
        self.cache = {}

    def __call__(self, building_id, driver):
        if self.district is None:
            self.district = self.project.preprocess()
        buildings = {str(b.geometry.building_id): b for b in self.district.buildings}
        if building_id not in buildings:
            raise AssessmentInputError(f"unknown project building_id {building_id!r}")
        if building_id not in self.cache:
            self.cache[building_id] = self._prepare(buildings[building_id])
        if driver not in self.cache[building_id]:
            raise MissingEstimate(f"driver {driver!r} unavailable for building {building_id}")
        return self.cache[building_id][driver], f"ProjectInputs {self.project.config_path.name}; {driver}; static_v1"

    def _prepare(self, building):
        from dt_prototype.common.constants import AIR_SPECIFIC_HEAT
        from dt_prototype.monthly_ss.simulation.models.model_5r1c import Model5R1C
        from dt_prototype.monthly_ss.simulation.config import SimulationConfig
        from dt_prototype.monthly_ss.simulation.quasi_steady_state import _ahu_sensible_balance
        from dt_prototype.dynamic_rc.simulation.zone import build_zone
        config = SimulationConfig(**self.project.configuration["operating"])
        weather = self.district.weather
        size = weather.n_steps
        cold, hot = float(weather.df.temp_air.min()), float(weather.df.temp_air.max())
        area = dict(opaque_wall_area=0.0, roof_area=0.0, ground_area=0.0, glazed_area=0.0,
                    floor_area=0.0, heating_design=0.0, cooling_design=0.0)
        daily_volume = np.zeros(size)
        dhw_power = np.zeros(size)
        for i, zi in enumerate(building.zones):
            area["floor_area"] += zi.geometry.net_floor_area
            for surface in zi.geometry.surfaces:
                # Inventory uses physical geometry, including adiabatic surfaces.
                wwr = zi.envelope.wwr if surface.surface_type == "ExtWall" else 0.0
                if surface.surface_type == "ExtWall":
                    area["opaque_wall_area"] += surface.area*(1-wwr)
                    area["glazed_area"] += surface.area*wwr
                elif surface.surface_type == "Roof":
                    area["roof_area"] += surface.area
                elif surface.surface_type == "GroundFloor":
                    area["ground_area"] += surface.area
            model = Model5R1C(building, weather, config, zone_index=i)
            zone = model.zone
            heat = zone.heating_setpoint[zone.heating_setpoint > 17]
            cool = zone.cooling_setpoint[zone.cooling_setpoint < 27]
            th = float(heat.max()) if heat.size else 20.0
            tc = float(cool.min()) if cool.size else 26.0
            hi = zone.infiltration_mass_flow * AIR_SPECIFIC_HEAT
            hv = zone.ventilation_mass_flow * AIR_SPECIFIC_HEAT
            active = np.ones(size, dtype=bool)
            inactive = ~active
            sup_h, coil_h, _ = _ahu_sensible_balance(zone, np.full(size,cold), active, inactive, th, tc, config)
            sup_c, coil_c, _ = _ahu_sensible_balance(zone, np.full(size,hot), inactive, active, th, tc, config)
            if heat.size:
                loss = model.UA_tot*(th-cold) + hi*(th-cold) + hv*(th-sup_h)
                area["heating_design"] += float((np.maximum(loss,0)+np.maximum(coil_h,0)).max())/1000
            if cool.size:
                # Deliberately conservative, non-coincident envelope/gain bound.
                gains = float(np.maximum(zone.gains_convective+zone.gains_radiative+model.phi_sol,0).max())
                load = model.UA_tot*(hot-tc) + hi*(hot-tc) + hv*(sup_c-tc) + gains
                area["cooling_design"] += float((np.maximum(load,0)+np.maximum(-coil_c,0)).max())/1000
            daily_volume += zi.schedule.dhw_volume_flow*zi.geometry.net_floor_area*weather.timestep_seconds*1000
            dhw_power += build_zone(building, weather, i).dhw_demand
        day = weather.df.index.normalize()
        area["dhw_daily_volume"] = float(pd.Series(daily_volume,index=day).groupby(level=0).sum().max())
        area["dhw_daily_energy"] = float(pd.Series(dhw_power*weather.timestep_seconds/3.6e6,index=day).groupby(level=0).sum().max())
        for key, value in area.items():
            number(value, f"derived driver {key}")
        return area


def resolve_quantities(inputs, catalogue, context=None):
    """Return one row per physical/virtual asset, not per thermal solver.

    Missing active quantities produce status=missing. Malformed inputs,
    incompatible units, cycles and duplicate identities are hard errors.
    """
    definitions = validate_catalogue(catalogue)
    fields(inputs, {"schema_version", "description", "default_mode", "buildings"}, "quantity inputs")
    if inputs.get("schema_version") != "1.0" or inputs.get("default_mode") not in MODES:
        raise AssessmentInputError("quantity inputs require schema_version=1.0 and default_mode=auto/direct")
    buildings = inputs.get("buildings")
    if not isinstance(buildings, list) or not buildings:
        raise AssessmentInputError("buildings must be a non-empty list")
    result, building_keys = [], set()
    for building in buildings:
        fields(building, {"assessment_id", "building_id", "default_mode", "assets"}, "quantity building")
        aid = text(building.get("assessment_id"), "assessment_id")
        bid = text(building.get("building_id"), "building_id")
        if (aid,bid) in building_keys:
            raise AssessmentInputError(f"duplicate assessment/building {(aid,bid)}")
        building_keys.add((aid,bid))
        default = building.get("default_mode", inputs["default_mode"])
        if default not in MODES:
            raise AssessmentInputError("building default_mode must be auto/direct")
        assets = building.get("assets")
        if not isinstance(assets,list) or not assets:
            raise AssessmentInputError(f"{bid}: assets must be a non-empty list")
        pending, resolved, visiting = {}, {}, set()
        for asset in assets:
            fields(asset, ASSET_INPUT_FIELDS, "quantity asset")
            key = text(asset.get("asset_id"), "asset_id")
            if key in pending:
                raise AssessmentInputError(f"{bid}: duplicate asset_id {key}")
            pending[key] = asset

        def resolve(key):
            if key in resolved:
                return resolved[key]
            if key in visiting:
                raise AssessmentInputError(f"{bid}: circular asset quantity dependency at {key}")
            if key not in pending:
                raise AssessmentInputError(f"{bid}: unknown referenced asset_id {key}")
            visiting.add(key)
            asset = pending[key]
            cid = text(asset.get("catalogue_id"), "catalogue_id")
            if cid not in definitions:
                raise AssessmentInputError(f"unknown catalogue_id {cid}")
            definition = definitions[cid]
            unit = definition["quantity_unit"]
            if asset.get("quantity_unit",unit) != unit:
                raise AssessmentInputError(f"{key}: quantity_unit must be {unit}; no implicit conversion")
            mode = asset.get("quantity_mode",default)
            if mode not in MODES:
                raise AssessmentInputError(f"{key}: quantity_mode must be auto/direct")
            action = asset.get("scope_action")
            if action not in SCOPE_ACTIONS:
                raise AssessmentInputError(f"{key}: explicit scope_action is required")
            basis = text(asset.get("quantity_basis", definition["quantity_basis"]), "quantity_basis")
            source = text(asset.get("source"), f"{key} source")
            row = dict(assessment_id=aid, building_id=bid, asset_id=key, catalogue_id=cid,
                category_id=definition["category_id"], asset_name=definition["asset_name"],
                building_layer=definition["building_layer"], scope_action=action,
                quantity_mode=mode, quantity_unit=unit, quantity_basis=basis,
                estimated_quantity=None, direct_quantity=None, base_quantity=None,
                sizing_factor=1.0, assessed_quantity=None, rule_id="direct", rule_version="1.0",
                sizing_basis="", source=source, status="complete", diagnostic="")
            try:
                if definition.get("requires_quantity_basis") and not asset.get("quantity_basis"):
                    raise MissingEstimate("quantity_basis must explicitly define this capacity proxy")
                if mode == "direct":
                    value = asset.get("direct_quantity")
                    if value is None:
                        raise MissingEstimate("direct_quantity is required; no auto fallback")
                    base = number(value, f"{key} direct_quantity")
                    row["direct_quantity"] = base
                    row["sizing_basis"] = f"direct input; unchanged; {basis}"
                else:
                    factor = number(asset.get("auto_factor",1.0), f"{key} auto_factor", positive=True)
                    row["sizing_factor"] = factor
                    rule = asset.get("rule_id",definition.get("default_rule"))
                    if rule is None:
                        raise MissingEstimate("an explicit automatic rule/estimate is required for this asset")
                    if rule not in RULES:
                        raise AssessmentInputError(f"{key}: unknown rule_id {rule}")
                    if rule in RULE_UNITS and RULE_UNITS[rule] != unit:
                        raise AssessmentInputError(f"{key}: rule/unit mismatch")
                    row["rule_id"] = rule
                    parameters = asset.get("parameters",{})
                    if not isinstance(parameters,dict):
                        raise AssessmentInputError(f"{key}: parameters must be an object")
                    base, detail = _estimate(rule, unit, parameters, bid, context, resolve)
                    base = number(base, f"{key} estimate")
                    row["estimated_quantity"] = base
                    row["sizing_basis"] = f"{rule} v1; {detail}; auto_factor={factor:g}; {basis}"
                row["base_quantity"] = base
                row["assessed_quantity"] = number(base*row["sizing_factor"], f"{key} sizing product")
            except MissingEstimate as error:
                row.update(status="missing", diagnostic=str(error))
                row["sizing_basis"] = f"{mode}; unresolved; {basis}"
            resolved[key] = row
            visiting.remove(key)
            return row
        for key in pending:
            resolve(key)
        result.extend(resolved[key] for key in pending)
    return pd.DataFrame(result, columns=QUANTITY_FIELDS)


def _estimate(rule, unit, p, bid, context, resolve):
    expected = {"fixed_estimate": {"estimate"}, "asset_multiple": {"asset_id","rate","rate_unit"},
                "asset_sum": {"asset_ids"}, "pv_roof_capacity": {"coverage","module_kW_m2"},
                "roof_fraction": {"coverage"}, "dhw_recovery": {"recovery_hours"}}.get(rule,set())
    fields(p, expected, f"{rule} parameters")
    missing = expected - set(p)
    if missing:
        raise MissingEstimate(f"{rule}: missing parameters {sorted(missing)}")
    def driver(name):
        if context is None:
            raise MissingEstimate(f"project context required for {name}")
        value, origin = context(bid,name)
        return number(value,f"driver {name}"), origin
    def reference(key):
        row = resolve(text(key,"referenced asset_id"))
        if row["status"] != "complete":
            raise MissingEstimate(f"referenced asset {key} has an unresolved quantity")
        return row
    if rule == "fixed_estimate":
        return number(p["estimate"],"estimate"), "explicit external estimate"
    if rule == "asset_multiple":
        ref = reference(p["asset_id"])
        if p["rate_unit"] != f"{unit}/{ref['quantity_unit']}":
            raise AssessmentInputError("asset_multiple rate_unit must match output/input units")
        rate = number(p["rate"],"reference rate")
        return ref["assessed_quantity"]*rate, f"{ref['asset_id']} resolved quantity * {rate:g} {p['rate_unit']}"
    if rule == "asset_sum":
        keys = p["asset_ids"]
        if not isinstance(keys,list) or not keys or any(not isinstance(k,str) for k in keys) or len(set(keys)) != len(keys):
            raise AssessmentInputError("asset_sum requires distinct asset_ids")
        refs = [reference(k) for k in keys]
        if any(r["quantity_unit"] != unit for r in refs):
            raise AssessmentInputError("asset_sum units must agree")
        return sum(r["assessed_quantity"] for r in refs), f"sum resolved quantities {keys}"
    if rule in {"pv_roof_capacity","roof_fraction"}:
        area, origin = driver("roof_area")
        coverage = number(p["coverage"],"roof coverage")
        if coverage > 1:
            raise AssessmentInputError("roof coverage must be in [0,1]")
        multiplier = number(p["module_kW_m2"],"module_kW_m2",positive=True) if rule == "pv_roof_capacity" else 1
        return area*coverage*multiplier, f"{origin} * coverage {coverage:g} * density {multiplier:g}"
    if rule == "dhw_recovery":
        energy, origin = driver("dhw_daily_energy")
        hours = number(p["recovery_hours"],"recovery_hours",positive=True)
        if hours > 24:
            raise AssessmentInputError("DHW daily recovery_hours must be <=24")
        return energy/hours, f"{origin} / {hours:g} recovery hours"
    return driver(rule)


def run_quantities(input_path, catalogue_path, output, project_config=None):
    """Resolve all declared building/scenario inventories and record provenance."""
    source, cat = Path(input_path).resolve(), Path(catalogue_path).resolve()
    out = Path(output).resolve()
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite {out}")
    data = load_quantity_inputs(source)
    catalogue = load_json(cat)
    context = ProjectQuantityContext(project_config) if project_config is not None else None
    result = resolve_quantities(data,catalogue,context)
    out.mkdir(parents=True)
    result.to_csv(out/"resolved_asset_quantities.csv",index=False)
    (out/"quantity_inputs_resolved.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
    (out/"catalogue_resolved.json").write_text(json.dumps(catalogue,indent=2),encoding="utf-8")
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = dict(status="complete" if result.status.eq("complete").all() else "incomplete",
        schema_version="1.0", timestamp_utc=datetime.now(timezone.utc).isoformat(),
        input_sha256=sha(source), catalogue_sha256=sha(cat),
        project_hashes=context.project.hashes() if context is not None else None,
        solver_independent_inventory=True, changes_simulation_configuration=False,
        asset_rows=len(result), missing_rows=int(result.status.eq("missing").sum()),
        code_hashes={p.name:sha(p) for p in Path(__file__).parent.glob("*.py")})
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return out


def load_quantity_inputs(path):
    """JSON is the native input. Excel input uses explicit editable cells only."""
    path = Path(path)
    if path.suffix.lower() == ".xlsx":
        from .quantity_workbook import read_quantity_workbook
        return read_quantity_workbook(path)
    return load_json(path)


def check_assessment_quantities(assets, path):
    """Optional strict join: external results must use the resolved inventory."""
    rows = pd.read_csv(path,dtype=str,keep_default_na=False)
    required = {"assessment_id","building_id","asset_id","category_id","quantity_unit","scope_action",
                "base_quantity","sizing_factor","assessed_quantity","status"}
    if not required.issubset(rows.columns):
        raise AssessmentInputError("resolved quantity CSV is missing required fields")
    keys = ["assessment_id","building_id","asset_id"]
    if rows.duplicated(keys).any():
        raise AssessmentInputError("duplicate resolved quantity keys")
    indexed = {tuple(row[k] for k in keys):row for row in rows.to_dict("records")}
    for row in assets.to_dict("records"):
        key = tuple(row[k] for k in keys)
        if key not in indexed or indexed[key]["status"] != "complete":
            raise AssessmentInputError(f"missing complete resolved quantity for {key}")
        resolved = indexed[key]
        for column in ("category_id","quantity_unit","scope_action"):
            if row[column] != resolved[column]:
                raise AssessmentInputError(f"external {column} differs from resolved inventory for {key}")
        for column in ("base_quantity","sizing_factor","assessed_quantity"):
            try:
                value = float(resolved[column])
            except ValueError as error:
                raise AssessmentInputError(f"invalid resolved {column}") from error
            if not math.isfinite(value) or abs(row[column]-value) > 1e-6+1e-9*abs(value):
                raise AssessmentInputError(f"external {column} differs from resolved inventory for {key}")
