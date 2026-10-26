"""Standalone translation of ENERGY MODEL-DSS rows 506–564.

The input contract accepts only the assumptions and upstream annual energy
quantities consumed by this spreadsheet block. It does not import or call any
DT-Prototype thermal solver.
"""

from __future__ import annotations

from math import ceil, isfinite
from typing import Any, Mapping


class LCCInputError(ValueError):
    """Raised when an LCC input is missing, invalid or outside its domain."""


def _number(value: Any, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LCCInputError(f"{name} must be a finite number")
    number = float(value)
    if not isfinite(number):
        raise LCCInputError(f"{name} must be a finite number")
    if minimum is not None and number < minimum:
        raise LCCInputError(f"{name} must be >= {minimum}")
    return number


def _assessed_size(item: Mapping[str, Any], name: str) -> tuple[float, float, float, str]:
    """Return base quantity, sizing factor, assessed quantity and its basis.

    Legacy cases with only ``size`` retain exactly the previous calculation.
    New cases may declare ``base_size`` and ``sizing_factor``; ``size`` then
    acts as an optional check on their product rather than a second multiplier.
    """
    factor = _number(item.get("sizing_factor", 1.0), f"{name}.sizing_factor", minimum=1e-12)
    if "base_size" in item:
        base = _number(item["base_size"], f"{name}.base_size", minimum=0)
        assessed = _number(base * factor, f"{name}.assessed_size", minimum=0)
        if "size" in item:
            declared = _number(item["size"], f"{name}.size", minimum=0)
            if abs(declared - assessed) > 1e-6 + 1e-9 * abs(assessed):
                raise LCCInputError(f"{name}.size must equal base_size * sizing_factor")
    else:
        if factor != 1.0:
            raise LCCInputError(f"{name}.base_size is required when sizing_factor is not 1")
        assessed = _number(item["size"], f"{name}.size", minimum=0)
        base = assessed
    basis = str(item.get("sizing_basis", "legacy assessed size" if "base_size" not in item else "declared base quantity"))
    if not basis.strip():
        raise LCCInputError(f"{name}.sizing_basis must be non-empty")
    return base, factor, assessed, basis


def _annuity_factor(years: float, discount: float, growth: float, *, starts_year_one: bool) -> float:
    """Translate rows 548–552, including their equal-rate branches."""
    if discount <= -1 or growth <= -1:
        raise LCCInputError("discount and escalation rates must be greater than -100%")
    if discount == growth:
        return years if starts_year_one else years / (1 + discount)
    return (
        ((1 + growth) / (discount - growth))
        * (1 - ((1 + growth) ** years) / ((1 + discount) ** years))
        if starts_year_one
        else (1 / (discount - growth))
        * (1 - ((1 + growth) ** years) / ((1 + discount) ** years))
    )


def calculate_lcc(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate LCC totals and cell-traceable intermediates.

    ``inputs`` follows ``benchmark_case.json``. Costs are in EUR, energy in
    kWh/year and area in m². The source equations price imported/exported
    electricity at one annual amount; they do not derive fuel consumption cost
    inside rows 506–564.
    """
    a = inputs["assumptions"]
    energy = inputs["annual_energy"]
    renovation = inputs["renovation"]
    years = _number(a["project_lifetime_years"], "project_lifetime_years", minimum=1e-12)
    nominal = _number(a["market_interest_rate_nominal"], "market_interest_rate_nominal")
    market_inflation = _number(a["market_inflation_rate"], "market_inflation_rate")
    product_inflation = _number(a["product_inflation_rate"], "product_inflation_rate")
    electricity_inflation = _number(a["electricity_inflation_rate"], "electricity_inflation_rate")
    maintenance_inflation = _number(a["maintenance_inflation_rate"], "maintenance_inflation_rate")
    # Check the domain before division/exponentiation: -100% makes a price
    # index zero and invalidates real discounting and source annuity formulas.
    for label, rate in (
        ("market_interest_rate_nominal", nominal), ("market_inflation_rate", market_inflation),
        ("product_inflation_rate", product_inflation), ("electricity_inflation_rate", electricity_inflation),
        ("maintenance_inflation_rate", maintenance_inflation),
    ):
        if rate <= -1:
            raise LCCInputError(f"{label} must be greater than -100%")
    discount = (nominal - market_inflation) / (1 + market_inflation)
    product_factor = (1 + product_inflation) / (1 + discount)

    technology_rows: list[dict[str, Any]] = []
    for tech in inputs["technologies"]:
        name = str(tech["name"])
        cost = _number(tech["cost_per_unit"], f"{name}.cost_per_unit", minimum=0)
        base_size, sizing_factor, size, sizing_basis = _assessed_size(tech, name)
        life = _number(tech["lifetime_years"], f"{name}.lifetime_years", minimum=1e-12)
        replacement_fraction = _number(tech["replacement_cost_fraction"], f"{name}.replacement_cost_fraction", minimum=0)
        maintenance_rate = _number(tech["maintenance_rate_per_year"], f"{name}.maintenance_rate_per_year", minimum=0)
        initial_cost = cost * size
        replacement_count = ceil(years / life) - 1
        replacement_year = replacement_count * life
        remaining_life = (replacement_year + life) - years
        base = product_factor**life
        if base == 1:
            # Source row 533 has no equal-rate branch; Excel returns #DIV/0!.
            raise LCCInputError(
                f"{name}: source row 533 divides by zero when the product escalation/discount factor is 1"
            )
        replacement_cost = initial_cost * replacement_fraction
        replacement_pv = replacement_cost * base * (base**replacement_count - 1) / (base - 1)
        residual_value = (
            initial_cost
            * (1 + product_inflation) ** replacement_year
            * (remaining_life / life)
            / (1 + discount) ** years
        )
        demolition_cost = initial_cost * _number(a["demolition_cost_fraction"], "demolition_cost_fraction", minimum=0)
        annual_maintenance = initial_cost * maintenance_rate
        technology_rows.append(
            {
                "code": tech["code"],
                "name": name,
                "cost_per_unit": cost,
                "cost_unit": tech.get("cost_unit"),
                "asset_id": tech.get("asset_id", tech["code"]),
                "category_id": tech.get("category_id"),
                "building_layer": tech.get("building_layer"),
                "scope_action": tech.get("scope_action"),
                "base_size": base_size,
                "sizing_factor": sizing_factor,
                "sizing_basis": sizing_basis,
                "size": size,
                "size_unit": tech.get("size_unit"),
                "initial_cost_eur": initial_cost,
                "lifetime_years": life,
                "replacement_count": replacement_count,
                "replacement_year": replacement_year,
                "remaining_lifetime_years": remaining_life,
                "replacement_cost_fraction": replacement_fraction,
                "replacement_cost_eur": replacement_cost,
                "replacement_present_value_eur": replacement_pv,
                "residual_value_eur": residual_value,
                "demolition_cost_eur": demolition_cost,
                "maintenance_rate_per_year": maintenance_rate,
                "annual_maintenance_eur": annual_maintenance,
            }
        )

    area = _number(renovation["area_m2"], "renovation.area_m2", minimum=0)
    other_cost = _number(renovation["other_installation_cost_eur_per_m2"], "renovation.other_installation_cost_eur_per_m2", minimum=0) * area
    initial_investment = sum(row["initial_cost_eur"] for row in technology_rows) + other_cost
    investment_and_replacements = (
        initial_investment
        + sum(row["replacement_present_value_eur"] for row in technology_rows)
        - sum(row["residual_value_eur"] for row in technology_rows)
        + sum(row["demolition_cost_eur"] for row in technology_rows)
    )
    maintenance = sum(row["annual_maintenance_eur"] for row in technology_rows)
    exported = _number(energy["exported_electricity_kwh"], "annual_energy.exported_electricity_kwh", minimum=0)
    imported = _number(energy["imported_electricity_kwh"], "annual_energy.imported_electricity_kwh", minimum=0)
    export_price = _number(a["export_price_eur_per_kwh"], "export_price_eur_per_kwh", minimum=0)
    import_price = _number(a["import_price_eur_per_kwh"], "import_price_eur_per_kwh", minimum=0)
    export_cost_credit = exported * export_price
    import_cost = imported * import_price
    net_energy_cost = import_cost - export_cost_credit
    energy_factor_first = _annuity_factor(years, discount, electricity_inflation, starts_year_one=True)
    energy_factor_second = _annuity_factor(years, discount, electricity_inflation, starts_year_one=False)
    maintenance_factor_first = _annuity_factor(years, discount, maintenance_inflation, starts_year_one=True)
    maintenance_factor_second = _annuity_factor(years, discount, maintenance_inflation, starts_year_one=False)
    energy_cost_first = net_energy_cost * energy_factor_first
    energy_cost_second = net_energy_cost * energy_factor_second
    maintenance_cost_first = maintenance * maintenance_factor_first
    maintenance_cost_second = maintenance * maintenance_factor_second
    annualized_operation_cost = energy_cost_first + maintenance_cost_first
    global_cost = investment_and_replacements + annualized_operation_cost
    net_area = _number(renovation["net_floor_area_m2"], "renovation.net_floor_area_m2", minimum=1e-12)
    baseline_bill = _number(energy["baseline_electricity_bill_eur"], "baseline_electricity_bill_eur") + _number(energy["baseline_fuel_bill_eur"], "baseline_fuel_bill_eur")

    intermediates = {
        "T509_real_discount_rate": discount,
        "T517_product_escalation_discount_factor": product_factor,
        "T539_other_installation_cost_eur": other_cost,
        "T540_initial_investment_eur": initial_investment,
        "T541_investment_and_replacements_eur": investment_and_replacements,
        "T542_annual_maintenance_eur": maintenance,
        "T543_exported_electricity_kwh": exported,
        "T544_imported_electricity_kwh": imported,
        "T545_export_cost_credit_eur": export_cost_credit,
        "T546_import_energy_cost_eur": import_cost,
        "T547_net_energy_cost_eur_per_year": net_energy_cost,
        "T548_energy_annuity_factor_first_year": energy_factor_first,
        "T549_energy_annuity_factor_second_year": energy_factor_second,
        "T550_maintenance_cost_eur_per_year": maintenance,
        "T551_maintenance_annuity_factor_first_year": maintenance_factor_first,
        "T552_maintenance_annuity_factor_second_year": maintenance_factor_second,
        "T553_energy_cost_with_growth_first_year_eur": energy_cost_first,
        "T554_energy_cost_with_growth_second_year_eur": energy_cost_second,
        "T555_maintenance_cost_with_growth_first_year_eur": maintenance_cost_first,
        "T556_maintenance_cost_with_growth_second_year_eur": maintenance_cost_second,
        "T557_yearly_energy_operation_cost_savings_eur": baseline_bill - net_energy_cost,
        "T558_investment_and_replacement_cost_eur": investment_and_replacements,
        "T559_annualized_operation_cost_eur": annualized_operation_cost,
        "T560_global_cost_eur": global_cost,
        "T561_initial_investment_eur_per_m2": initial_investment / net_area,
        "T562_investment_and_replacement_eur_per_m2": investment_and_replacements / net_area,
        "T563_annualized_operation_cost_eur_per_m2": annualized_operation_cost / net_area,
        "T564_global_cost_eur_per_m2": investment_and_replacements / net_area + annualized_operation_cost / net_area,
    }
    return {
        "case_id": inputs.get("case_id"),
        "project_lifetime_years": years,
        "currency": "EUR",
        "technology_details": technology_rows,
        "intermediates": intermediates,
        "outputs": {key: intermediates[key] for key in ("T540_initial_investment_eur", "T541_investment_and_replacements_eur", "T542_annual_maintenance_eur", "T547_net_energy_cost_eur_per_year", "T557_yearly_energy_operation_cost_savings_eur", "T558_investment_and_replacement_cost_eur", "T559_annualized_operation_cost_eur", "T560_global_cost_eur", "T561_initial_investment_eur_per_m2", "T562_investment_and_replacement_eur_per_m2", "T563_annualized_operation_cost_eur_per_m2", "T564_global_cost_eur_per_m2")},
    }
