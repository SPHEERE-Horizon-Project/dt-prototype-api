"""Standalone, extensible LCA calculations.

The original ENERGY MODEL-DSS rows 565-600 remain available through legacy
output keys. Embodied impacts use a generic indicator engine: each declared
indicator is evaluated for every technology, then aggregated for the building.
"""

from __future__ import annotations

from math import ceil, isfinite
from typing import Any, Mapping


class LCAInputError(ValueError):
    """Raised for invalid LCA inputs or the known source formula error."""


NO_FUEL = "electricity-no fuel"
LEGACY_INDICATORS = (
    {"id": "primary_energy", "name": "Embodied primary energy", "unit": "kWh", "factor_unit": "kWh per declared quantity unit", "legacy_factor_key": "embodied_energy_kwh_per_unit", "legacy_renovation_key": "embodied_energy_kwh_per_m2_inferred_from_formula"},
    {"id": "gwp_total", "name": "Global warming potential - total", "unit": "kg CO2e", "factor_unit": "kg CO2e per declared quantity unit", "legacy_factor_key": "embodied_carbon_kg_per_unit", "legacy_renovation_key": "embodied_carbon_kg_per_m2"},
)


def _number(value: Any, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LCAInputError(f"{name} must be a finite number")
    number = float(value)
    if not isfinite(number):
        raise LCAInputError(f"{name} must be a finite number")
    if minimum is not None and number < minimum:
        raise LCAInputError(f"{name} must be >= {minimum}")
    return number


def _assessed_size(item: Mapping[str, Any], name: str) -> tuple[float, float, float, str]:
    """Resolve an explicit sizing factor while preserving legacy ``size`` cases."""
    factor = _number(item.get("sizing_factor", 1.0), f"{name}.sizing_factor", minimum=1e-12)
    if "base_size" in item:
        base = _number(item["base_size"], f"{name}.base_size", minimum=0)
        assessed = _number(base * factor, f"{name}.assessed_size", minimum=0)
        if "size" in item:
            declared = _number(item["size"], f"{name}.size", minimum=0)
            if abs(declared - assessed) > 1e-6 + 1e-9 * abs(assessed):
                raise LCAInputError(f"{name}.size must equal base_size * sizing_factor")
    else:
        if factor != 1.0:
            raise LCAInputError(f"{name}.base_size is required when sizing_factor is not 1")
        assessed = _number(item["size"], f"{name}.size", minimum=0)
        base = assessed
    basis = str(item.get("sizing_basis", "legacy assessed size" if "base_size" not in item else "declared base quantity"))
    if not basis.strip():
        raise LCAInputError(f"{name}.sizing_basis must be non-empty")
    return base, factor, assessed, basis


def _indicator_definitions(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = inputs.get("indicator_definitions", LEGACY_INDICATORS)
    definitions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        indicator_id = str(item.get("id", "")).strip()
        if not indicator_id or indicator_id in seen:
            raise LCAInputError(f"indicator_definitions[{index}].id must be non-empty and unique")
        seen.add(indicator_id)
        unit = str(item.get("unit", "")).strip()
        if not unit:
            raise LCAInputError(f"indicator {indicator_id!r} must declare a result unit")
        definitions.append({
            "id": indicator_id,
            "name": str(item.get("name", indicator_id)),
            "unit": unit,
            "factor_unit": str(item.get("factor_unit", f"{unit} per declared quantity unit")),
            "source": item.get("source"),
            "legacy_factor_key": item.get("legacy_factor_key"),
            "legacy_renovation_key": item.get("legacy_renovation_key"),
        })
    if not definitions:
        raise LCAInputError("at least one indicator definition is required")
    return definitions


def _factor_value(owner: Mapping[str, Any], definition: Mapping[str, Any], path: str, *, renovation: bool = False) -> float | None:
    indicator_id = str(definition["id"])
    factors = owner.get("indicator_factors", {})
    if indicator_id in factors:
        raw = factors[indicator_id]
        if isinstance(raw, Mapping):
            declared_unit = raw.get("unit")
            if declared_unit and str(declared_unit) != str(definition["factor_unit"]):
                raise LCAInputError(f"{path}.indicator_factors.{indicator_id}.unit does not match {definition['factor_unit']!r}")
            raw = raw.get("value")
        # JSON null is a declared missing factor, rather than a numeric zero.
        return None if raw is None else _number(raw, f"{path}.indicator_factors.{indicator_id}")
    legacy_key = definition.get("legacy_renovation_key") if renovation else definition.get("legacy_factor_key")
    if legacy_key and legacy_key in owner:
        return _number(owner[legacy_key], f"{path}.{legacy_key}")
    return None


def _fuel(fuel_type: str, fuels: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    matches = [row for row in fuels if str(row["fuel_type"]).casefold() == fuel_type.casefold()]
    if len(matches) != 1:
        raise LCAInputError(f"fuel type {fuel_type!r} must match exactly one LCA fuel factor row")
    return matches[0]


def _fuel_primary(quantity: float, fuel_type: str, fuels: list[Mapping[str, Any]]) -> float:
    if fuel_type.casefold() == NO_FUEL.casefold():
        return 0.0
    factor = _fuel(fuel_type, fuels)
    return quantity * _number(factor["lower_heating_value_kwh_per_unit"], f"{fuel_type}.LHV", minimum=0) * _number(factor["primary_energy_factor"], f"{fuel_type}.primary_energy_factor", minimum=0)


def _fuel_carbon(quantity: float, fuel_type: str, fuels: list[Mapping[str, Any]]) -> float:
    if fuel_type.casefold() == NO_FUEL.casefold():
        return 0.0
    factor = _fuel(fuel_type, fuels)
    return quantity * _number(factor["lower_heating_value_kwh_per_unit"], f"{fuel_type}.LHV", minimum=0) * _number(factor["carbon_factor_kgco2_per_kwh"], f"{fuel_type}.carbon_factor_kgco2_per_kwh", minimum=0)


def calculate_lca(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate item and building impacts for any declared indicator set.

    Annual impact is ``factor * quantity / service_life``. Project impact is
    ``factor * quantity * installations``. A building indicator remains
    unavailable when a non-zero item or renovation factor is missing.
    """
    project = inputs["project"]
    lifetime = _number(project["lifetime_years"], "project.lifetime_years", minimum=1e-12)
    area = _number(project["net_floor_area_m2"], "project.net_floor_area_m2", minimum=1e-12)
    definitions = _indicator_definitions(inputs)

    technology_rows: list[dict[str, Any]] = []
    missing_by_indicator: dict[str, list[str]] = {item["id"]: [] for item in definitions}
    for tech_index, tech in enumerate(inputs["technologies"]):
        name = str(tech["name"])
        service_life = _number(tech["lifetime_years"], f"{name}.lifetime_years", minimum=1e-12)
        base_size, sizing_factor, size, sizing_basis = _assessed_size(tech, name)
        installations = ceil(lifetime / service_life)
        impacts: dict[str, dict[str, Any]] = {}
        for definition in definitions:
            indicator_id = definition["id"]
            factor = _factor_value(tech, definition, f"technologies[{tech_index}]")
            if factor is None:
                if size > 0:
                    missing_by_indicator[indicator_id].append(name)
                # An absent asset contributes zero even when its unit factor is
                # unknown. A non-zero asset remains unavailable and blocks totals.
                contribution = 0.0 if size == 0 else None
                impacts[indicator_id] = {"factor_per_unit": None, "factor_unit": definition["factor_unit"], "annual": contribution, "project_total": contribution, "unit": definition["unit"]}
            else:
                impacts[indicator_id] = {
                    "factor_per_unit": factor,
                    "factor_unit": definition["factor_unit"],
                    "annual": factor * size / service_life,
                    "project_total": installations * factor * size,
                    "unit": definition["unit"],
                }
        row = {
            "code_energy": tech.get("code_energy"), "code_carbon": tech.get("code_carbon"), "code": tech.get("code"),
            "name": name, "asset_id": tech.get("asset_id", tech.get("code", tech.get("code_energy"))),
            "category_id": tech.get("category_id"), "building_layer": tech.get("building_layer"),
            "scope_action": tech.get("scope_action"), "base_size": base_size,
            "sizing_factor": sizing_factor, "sizing_basis": sizing_basis,
            "size": size, "size_unit": tech.get("size_unit"), "service_life_years": service_life,
            "installations_in_project": installations, "replacements_in_project": installations - 1,
            "residual_lifetime_years": service_life * installations - lifetime, "impacts": impacts,
        }
        if "primary_energy" in impacts and impacts["primary_energy"]["factor_per_unit"] is not None:
            impact = impacts["primary_energy"]
            row.update(embodied_energy_factor=impact["factor_per_unit"], embodied_energy_unit=tech.get("embodied_energy_unit", impact["factor_unit"]), annual_embodied_energy_kwh_per_year=impact["annual"], total_embodied_energy_kwh=impact["project_total"])
        if "gwp_total" in impacts and impacts["gwp_total"]["factor_per_unit"] is not None:
            impact = impacts["gwp_total"]
            row.update(embodied_carbon_factor=impact["factor_per_unit"], embodied_carbon_unit=tech.get("embodied_carbon_unit", impact["factor_unit"]), annual_embodied_carbon_kg_per_year=impact["annual"], total_embodied_carbon_kg=impact["project_total"])
        technology_rows.append(row)

    renovation = inputs.get("renovation", {})
    renovation_impacts: dict[str, dict[str, Any]] = {}
    for definition in definitions:
        indicator_id = definition["id"]
        factor = _factor_value(renovation, definition, "renovation", renovation=True)
        if factor is None:
            missing_by_indicator[indicator_id].append("renovation")
            renovation_impacts[indicator_id] = {"factor_per_m2": None, "annual": None, "project_total": None}
        else:
            renovation_impacts[indicator_id] = {"factor_per_m2": factor, "annual": factor * area / lifetime, "project_total": factor * area}

    indicator_results: dict[str, dict[str, Any]] = {}
    for definition in definitions:
        indicator_id = definition["id"]
        missing = missing_by_indicator[indicator_id]
        if missing:
            annual = total = intensity = None
            status = "missing factors"
        else:
            annual = sum(row["impacts"][indicator_id]["annual"] for row in technology_rows) + renovation_impacts[indicator_id]["annual"]
            total = sum(row["impacts"][indicator_id]["project_total"] for row in technology_rows) + renovation_impacts[indicator_id]["project_total"]
            intensity = annual / area
            status = "complete"
        indicator_results[indicator_id] = {"name": definition["name"], "unit": definition["unit"], "annual": annual, "project_total": total, "annual_per_m2": intensity, "status": status, "missing_factors": missing}

    factors = inputs["electricity_factors"]
    electricity_primary_factor = _number(factors["primary_energy_factor"], "electricity.primary_energy_factor", minimum=0)
    electricity_carbon_factor = _number(factors["carbon_kgco2_per_kwh"], "electricity.carbon_kgco2_per_kwh", minimum=0)
    prior = inputs["pre_retrofit"]
    electricity = _number(prior["electricity_kwh"], "pre_retrofit.electricity_kwh", minimum=0)
    heat_fuel_quantity = _number(prior["heating_fuel_quantity"], "pre_retrofit.heating_fuel_quantity", minimum=0)
    dhw_fuel_quantity = _number(prior["dhw_fuel_quantity"], "pre_retrofit.dhw_fuel_quantity", minimum=0)
    heating_fuel, dhw_fuel, fuels = str(prior["heating_fuel_type"]), str(prior["dhw_fuel_type"]), inputs["fuel_factors"]
    heating_fuel_primary = _fuel_primary(heat_fuel_quantity, heating_fuel, fuels)
    heating_fuel_carbon = _fuel_carbon(heat_fuel_quantity, heating_fuel, fuels)
    if dhw_fuel.casefold() == NO_FUEL.casefold():
        dhw_fuel_primary = 0.0
    else:
        raise LCAInputError('Source formula ENERGY MODEL-DSS!T595 multiplies the text literal "T553"; non-electricity DHW fuel therefore returns #VALUE! in the workbook.')
    dhw_fuel_carbon = _fuel_carbon(dhw_fuel_quantity, dhw_fuel, fuels)
    electricity_primary, electricity_carbon = electricity * electricity_primary_factor, electricity * electricity_carbon_factor

    intermediate: dict[str, Any] = {
        "T577_residual_lifetime_by_technology_years": [r["residual_lifetime_years"] for r in technology_rows],
        "T591_pre_retrofit_electricity_primary_energy_kwh": electricity_primary,
        "T592_pre_retrofit_electricity_carbon_kg": electricity_carbon,
        "T593_pre_retrofit_heating_fuel_primary_energy_kwh": heating_fuel_primary,
        "T594_pre_retrofit_heating_fuel_carbon_kg": heating_fuel_carbon,
        "T595_pre_retrofit_dhw_fuel_primary_energy_kwh": dhw_fuel_primary,
        "T596_pre_retrofit_dhw_fuel_carbon_kg": dhw_fuel_carbon,
        "T597_pre_retrofit_total_primary_energy_kwh": electricity_primary + heating_fuel_primary + dhw_fuel_primary,
        "T598_pre_retrofit_total_carbon_kg": electricity_carbon + heating_fuel_carbon + dhw_fuel_carbon,
    }
    if indicator_results.get("primary_energy", {}).get("status") == "complete":
        result = indicator_results["primary_energy"]
        intermediate.update(T573_annual_embodied_energy_by_technology_kwh=[r["impacts"]["primary_energy"]["annual"] for r in technology_rows], T575_total_embodied_energy_by_technology_kwh=[r["impacts"]["primary_energy"]["project_total"] for r in technology_rows], T578_renovation_embodied_energy_kwh_per_year=renovation_impacts["primary_energy"]["annual"], T580_renovation_embodied_energy_total_kwh=renovation_impacts["primary_energy"]["project_total"], T582_total_embodied_energy_kwh_per_year=result["annual"], T584_total_embodied_energy_kwh=result["project_total"], T599_embodied_energy_kwh_per_m2_per_year=result["annual_per_m2"])
    if indicator_results.get("gwp_total", {}).get("status") == "complete":
        result = indicator_results["gwp_total"]
        intermediate.update(T574_annual_embodied_carbon_by_technology_kg=[r["impacts"]["gwp_total"]["annual"] for r in technology_rows], T576_total_embodied_carbon_by_technology_kg=[r["impacts"]["gwp_total"]["project_total"] for r in technology_rows], T579_renovation_embodied_carbon_kg_per_year=renovation_impacts["gwp_total"]["annual"], T581_renovation_embodied_carbon_total_kg=renovation_impacts["gwp_total"]["project_total"], T583_total_embodied_carbon_kg_per_year=result["annual"], T585_total_embodied_carbon_kg=result["project_total"], T600_embodied_carbon_kg_per_m2_per_year=result["annual_per_m2"])

    keys = ("T582_total_embodied_energy_kwh_per_year", "T583_total_embodied_carbon_kg_per_year", "T584_total_embodied_energy_kwh", "T585_total_embodied_carbon_kg", "T597_pre_retrofit_total_primary_energy_kwh", "T598_pre_retrofit_total_carbon_kg", "T599_embodied_energy_kwh_per_m2_per_year", "T600_embodied_carbon_kg_per_m2_per_year")
    return {"case_id": inputs.get("case_id"), "project_lifetime_years": lifetime, "net_floor_area_m2": area, "indicator_definitions": definitions, "technology_details": technology_rows, "renovation_impacts": renovation_impacts, "indicator_results": indicator_results, "intermediates": intermediate, "outputs": {key: intermediate[key] for key in keys if key in intermediate}}
