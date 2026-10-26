"""Explicit migration of supplied system templates into the shared schema.

No catalogue fallback, plant autosizing or technology guessing is used here.
Example factor values are deliberately labelled assumptions, not regulatory data.
"""
from copy import deepcopy
from .config import EnergyConfig


def example_configuration(district):
    """Build a reviewable demonstration config using each building's supplied systems."""
    source = "Illustrative test factors/prices, not national factors, tariffs or ISO validation"
    factors = {}
    for carrier, nren, ren, carbon, price in (
        ("electricity", 2.0, .4, .25, .25), ("natural_gas", 1.1, 0, .2, .09),
        ("district_heat", 1.0, 0, .15, .10), ("other_fuel", 1.1, 0, .27, .11),
    ):
        factors[carrier] = dict(primary_nonrenewable=nren, primary_renewable=ren,
            carbon_kgCO2e_per_kWh=carbon, import_price_per_kWh=price,
            export_primary_nonrenewable=0, export_primary_renewable=0,
            export_carbon_kgCO2e_per_kWh=0, export_price_per_kWh=.06 if carrier == "electricity" else 0,
            source=source)
    data = dict(schema_version="1.0", scenario_id="supplied_templates_factor_demo",
                description="Supplied constant-efficiency templates; illustrative PV/ST matching and carrier factors",
                currency="EUR", carriers=factors, technologies={}, buildings={})
    fuels = {"gas": "natural_gas", "electric": "electricity", "district_heat": "district_heat", "other_fuel": "other_fuel"}

    def resolve(kind, name):
        catalog = district.system_templates[kind]
        matches = [(key, value) for key, value in catalog.items() if key == name or value["description"] == name]
        if len(matches) != 1:
            raise ValueError(f"Unresolved or ambiguous {kind} template {name!r}")
        return matches[0]

    for building in district.buildings:
        hk, h = resolve("heating_systems", building.geometry.heating_system)
        ck, c = resolve("cooling_systems", building.geometry.cooling_system)
        services = {}
        for service in ("zone_heating", "ahu_heating", "zone_cooling", "ahu_cooling", "dhw"):
            cool, water, ahu = "cooling" in service, service == "dhw", service.startswith("ahu")
            template, key = (c, ck) if cool else (h, hk)
            prefix = "dhw_" if water else ""
            generation = (template["eer"] if cool else
                          template[prefix + "generation_efficiency"] * (template[prefix + "cop"] or 1))
            tech_id = f"{service}_{key}"
            data["technologies"][tech_id] = dict(
                carrier=fuels[template[prefix + "fuel"]],
                performance=dict(coefficients=[generation], temperature_min_C=-30, temperature_max_C=50,
                                 out_of_range="clip", source=f"supplied systems_templates.json / {key} / {service}"),
                distribution_efficiency=template[prefix + "distribution_efficiency"],
                emission_efficiency=1.0 if ahu else template[prefix + "emission_efficiency"],
                regulation_efficiency=1.0 if ahu else template[prefix + "regulation_efficiency"],
                auxiliary_kWh_per_kWh_generated=0.0,
                description=template["description"] + ("; AHU coil: generation/distribution only" if ahu else ""),
            )
            services[service] = tech_id
        tags = {tag.strip().upper() for tag in building.geometry.solar_technologies.split(",")}
        data["buildings"][str(building.geometry.building_id)] = dict(
            services=services, fan_W_per_m3_h=.4434, base_auxiliary_W=0.0,
            source="Supplied geometry/system templates. Fan coefficient from existing AHU model. No unspecified pump/standby load.",
            pv=dict(roof_coverage=.45 if "PV" in tags else 0, module_kWp_per_m2=.4/1.7,
                    performance_ratio=.85, factor_basis="overlap", monthly_factor=[.65]*12,
                    source="PV tags and 45% roof coverage/module density from existing PV model; PR=.85 and overlap factor=.65 are illustrative assumptions"),
            solar_thermal=dict(roof_coverage=.05 if "ST" in tags else 0, eta0=.8, a1_W_m2K=3.5,
                a2_W_m2K2=.015, mean_fluid_temperature_C=50, monthly_utilisation=[.6]*12,
                source="Supplied ST tags; illustrative 5% roof collector area, loss coefficients, fluid temperature and monthly utilisation=.6; no tank model"),
        )
    return EnergyConfig.from_dict(data)


def linear_sensitivity(config):
    """Historical Model 3 curves, used only as a labelled sensitivity scenario."""
    data = deepcopy(config.data)
    data["scenario_id"] = "model3_linear_curve_sensitivity"
    data["description"] = "Sensitivity: historical Model 3 heat-pump/chiller curves; not fitted to case-study equipment"
    for name, technology in data["technologies"].items():
        if "cooling" in name:
            coefficients, lo, hi = [5.2, -.09], -10, 45
        elif "heating" in name and "Heat Pump" in technology["description"]:
            coefficients, lo, hi = [2.2, .09], -10, 35
        else:
            continue
        technology["performance"] = dict(coefficients=coefficients, temperature_min_C=lo, temperature_max_C=hi,
            out_of_range="clip", source="integration/model3/example_data/systems.csv configuration 2; illustrative transfer only")
    return EnergyConfig.from_dict(data)
