"""Material Circularity Indicator calculations for materials, components and buildings."""

from __future__ import annotations

from collections import defaultdict
from math import isfinite
from typing import Any, Mapping


class CircularityInputError(ValueError):
    """Raised when an MCI input is missing or outside the methodology domain."""


def _number(value: Any, name: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CircularityInputError(f"{name} must be a finite number")
    number = float(value)
    if not isfinite(number):
        raise CircularityInputError(f"{name} must be a finite number")
    if minimum is not None and number < minimum:
        raise CircularityInputError(f"{name} must be >= {minimum}")
    if maximum is not None and number > maximum:
        raise CircularityInputError(f"{name} must be <= {maximum}")
    return number


def _fraction(row: Mapping[str, Any], key: str, label: str) -> float:
    return _number(row[key], f"{label}.{key}", minimum=0, maximum=1)


def _identifier(value: Any, field: str) -> str:
    """Preserve stable textual IDs; null is never the asset named 'None'."""
    if value is None or isinstance(value, bool) or not str(value).strip():
        raise CircularityInputError(f"{field} must be non-empty")
    return str(value).strip()


def calculate_material_mci(material: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate MCI and all traceable intermediate flows for one material row."""
    label = str(material.get("material_name", material.get("material_id", "material")))
    mass = _number(material["mass_kg"], f"{label}.mass_kg", minimum=1e-12)
    recycled_input = _fraction(material, "recycled_input_fraction", label)
    reused_input = _fraction(material, "reused_input_fraction", label)
    collected_recycling = _fraction(material, "collected_for_recycling_fraction", label)
    collected_reuse = _fraction(material, "collected_for_reuse_fraction", label)
    if recycled_input + reused_input > 1 + 1e-12:
        raise CircularityInputError(f"{label}: recycled and reused input fractions must sum to <= 1")
    if collected_recycling + collected_reuse > 1 + 1e-12:
        raise CircularityInputError(f"{label}: recycling and reuse collection fractions must sum to <= 1")
    feedstock_efficiency = _fraction(material, "recycled_feedstock_efficiency", label)
    collection_efficiency = _fraction(material, "end_of_use_recycling_efficiency", label)
    if recycled_input > 0 and feedstock_efficiency <= 0:
        raise CircularityInputError(f"{label}: recycled_feedstock_efficiency must be > 0 when recycled input is used")
    service_life = _number(material["service_life_years"], f"{label}.service_life_years", minimum=1e-12)
    average_life = _number(material["industry_average_life_years"], f"{label}.industry_average_life_years", minimum=1e-12)
    use_intensity = _number(material.get("use_intensity", 1), f"{label}.use_intensity", minimum=1e-12)
    average_intensity = _number(material.get("industry_average_use_intensity", 1), f"{label}.industry_average_use_intensity", minimum=1e-12)

    virgin_input = mass * (1 - recycled_input - reused_input)
    unrecovered = mass * (1 - collected_recycling - collected_reuse)
    feedstock_loss = 0.0 if recycled_input == 0 else mass * recycled_input * (1 - feedstock_efficiency) / feedstock_efficiency
    end_of_use_loss = mass * collected_recycling * (1 - collection_efficiency)
    attributed_waste = unrecovered + (feedstock_loss + end_of_use_loss) / 2
    denominator = 2 * mass + (feedstock_loss - end_of_use_loss) / 2
    if denominator <= 0:
        raise CircularityInputError(f"{label}: LFI denominator must be positive")
    linear_flow_index = (virgin_input + attributed_waste) / denominator
    utility = (service_life / average_life) * (use_intensity / average_intensity)
    raw_mci = 1 - linear_flow_index * 0.9 / utility
    mci = min(1.0, max(0.0, raw_mci))
    return {
        "component_id": material.get("component_id"), "component_name": material.get("component_name"),
        "material_id": material.get("material_id"), "material_name": label, "mass_kg": mass,
        "virgin_input_kg": virgin_input, "unrecovered_mass_kg": unrecovered,
        "feedstock_recycling_loss_kg": feedstock_loss, "end_of_use_recycling_loss_kg": end_of_use_loss,
        "attributed_waste_kg": attributed_waste, "linear_flow_index": linear_flow_index,
        "utility_factor": utility, "raw_mci": raw_mci, "mci": mci, "mci_percent": 100 * mci,
    }


def calculate_component_mci(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate material scores and mass-weight them into component scores."""
    materials = []
    identities: set[tuple[str, str]] = set()
    component_names: dict[str, str] = {}
    for index, raw in enumerate(inputs["materials"]):
        raw = dict(raw)
        for field in ("component_id", "component_name", "material_id", "material_name"):
            raw[field] = _identifier(raw.get(field), f"materials[{index}].{field}")
        key = raw["component_id"], raw["material_id"]
        if key in identities:
            raise CircularityInputError(f"duplicate component/material identity: {key}")
        identities.add(key)
        if raw["component_id"] in component_names and component_names[raw["component_id"]] != raw["component_name"]:
            raise CircularityInputError("component_name must agree within a component")
        component_names[raw["component_id"]] = raw["component_name"]
        materials.append(calculate_material_mci(raw))
    if not materials:
        raise CircularityInputError("materials must contain at least one row")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in materials:
        component_id = str(row.get("component_id") or "").strip()
        if not component_id:
            raise CircularityInputError("every material row must declare component_id")
        groups[component_id].append(row)
    components = []
    for component_id, rows in groups.items():
        total_mass = sum(row["mass_kg"] for row in rows)
        score = sum(row["mass_kg"] * row["mci"] for row in rows) / total_mass
        components.append({
            "component_id": component_id, "component_name": rows[0].get("component_name"),
            "material_count": len(rows), "mass_kg": total_mass, "mci": score, "mci_percent": 100 * score,
        })
    return {"case_id": inputs.get("case_id"), "materials": materials, "components": components}


def aggregate_building_mci(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Mass-weight pre-computed component MCI values into layer and building scores."""
    rows = []
    identities: set[str] = set()
    for index, component in enumerate(inputs["components"]):
        component_id = _identifier(component.get("component_id"), f"components[{index}].component_id")
        if component_id in identities:
            raise CircularityInputError(f"duplicate component_id: {component_id}")
        identities.add(component_id)
        mass = _number(component["mass_kg"], f"{component_id}.mass_kg", minimum=1e-12)
        mci = _number(component["mci"], f"{component_id}.mci", minimum=0, maximum=1)
        rows.append({"component_id": component_id, "component_name": component.get("component_name"), "building_layer": str(component.get("building_layer", "Unassigned")), "mass_kg": mass, "mci": mci, "weighted_mci_mass_kg": mass * mci})
    if not rows:
        raise CircularityInputError("components must contain at least one row")
    total_mass = sum(row["mass_kg"] for row in rows)
    building_score = sum(row["weighted_mci_mass_kg"] for row in rows) / total_mass
    layer_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        layer_groups[row["building_layer"]].append(row)
    layers = []
    for layer, components in layer_groups.items():
        layer_mass = sum(row["mass_kg"] for row in components)
        layer_score = sum(row["weighted_mci_mass_kg"] for row in components) / layer_mass
        layers.append({"building_layer": layer, "component_count": len(components), "mass_kg": layer_mass, "mci": layer_score, "mci_percent": 100 * layer_score})
    return {"case_id": inputs.get("case_id"), "components": rows, "layers": layers, "building": {"mass_kg": total_mass, "mci": building_score, "mci_percent": 100 * building_score}}
