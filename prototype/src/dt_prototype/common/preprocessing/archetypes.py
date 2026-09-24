"""Building envelope archetypes, TABULA / URBEM style (FR-07).

Migrated from ``reference_ubem.envelope_types`` and the data-side of
``reference_building.construction`` / ``material`` / ``window``. The Excel
archetype databases are replaced by open JSON files (see
``data/examples/archetypes_tabula_like.json``): each archetype gives, per
envelope element, a U-value, a mass class and a solar absorptance. An
equivalent single-layer construction is derived exactly as the retained reference's
``Construction.from_U_value`` (ISO 13786 mass classes), which is what both
RC models need downstream.

Two element forms are accepted, per envelope element:

- ``u_value`` + ``mass_class`` — the equivalent-single-layer form described
  above (illustrative TABULA-style databases);
- ``layers`` — an explicit list of ``thickness``/``conductivity``/
  ``density``/``specific_heat`` dicts, ordered **outside → inside**, used by
  the 1:1 port of the retained reference's ``Materials.xlsx``
  (``data/examples/archetypes.json``). Takes precedence when both
  are present.

EXTENSION POINT (new archetypes, NFR-06): add entries to the JSON database —
no code changes required, in either form.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from dt_prototype.common.constants import SURFACE_HEAT_TRANSFER_COEF

# ISO 13786 A.2.3 equivalent-layer densities per mass class [kg/m3]
# (thickness 0.30 m, specific heat 1000 J/(kg K)), as in the retained reference.
_MASS_CLASS_DENSITY = {
    "Very heavy": 1495.0,
    "Heavy": 1226.0,
    "Medium": 933.0,
    "Light": 622.0,
    "Very light": 453.0,
}
_EQUIVALENT_THICKNESS = 0.3  # [m]
_EQUIVALENT_SPEC_HEAT = 1000.0  # [J/(kg K)]

# JSON keys of the opaque envelope elements -> construction types
_OPAQUE_ELEMENTS = {
    "ext_wall": "ExtWall",
    "roof": "Roof",
    "ground_floor": "GroundFloor",
    "int_wall": "IntWall",
    "int_ceiling": "IntCeiling",
    "int_floor": "IntFloor",
}


@dataclass
class Layer:
    """One homogeneous material layer (SI units)."""

    thickness: float  # [m]
    conductivity: float  # [W/(m K)]
    density: float  # [kg/m3]
    specific_heat: float  # [J/(kg K)]

    @property
    def thermal_resistance(self) -> float:
        """Conductive resistance of the layer [m2 K / W]."""
        return self.thickness / self.conductivity

    @property
    def areal_heat_capacity(self) -> float:
        """Heat capacity per unit area [J/(m2 K)]."""
        return self.thickness * self.density * self.specific_heat


@dataclass
class ConstructionSpec:
    """Multi-layer opaque construction, listed outside → inside (SI units).

    Carries everything the simulation layer needs to derive both ISO 13790
    and VDI 6007 dynamic parameters.
    """

    name: str
    construction_type: str  # ExtWall / Roof / GroundFloor / IntWall / IntCeiling / IntFloor
    layers: list[Layer]
    solar_absorptance: float = 0.6

    @property
    def r_si(self) -> float:
        """Internal surface (film) resistance [m2 K / W]."""
        return 1.0 / SURFACE_HEAT_TRANSFER_COEF[self.construction_type]["inside"]

    @property
    def r_se(self) -> float:
        """External surface (film) resistance [m2 K / W]."""
        return 1.0 / SURFACE_HEAT_TRANSFER_COEF[self.construction_type]["outside"]

    @property
    def net_resistance(self) -> float:
        """Conductive (surface-to-surface) resistance [m2 K / W]."""
        return sum(layer.thermal_resistance for layer in self.layers)

    @property
    def u_value(self) -> float:
        """Air-to-air thermal transmittance [W/(m2 K)].

        GroundFloor U is reduced by 0.7 as in the retained reference to approximate the
        ground contact (ISO 13370 simplification).
        """
        u = 1.0 / (self.net_resistance + self.r_si + self.r_se)
        return u * 0.7 if self.construction_type == "GroundFloor" else u

    @property
    def u_value_net(self) -> float:
        """Surface-to-surface transmittance [W/(m2 K)] (no film resistances)."""
        return 1.0 / self.net_resistance

    def to_dict(self) -> dict:
        """Plain-dict representation for JSON serialisation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ConstructionSpec":
        """Rebuild from :meth:`to_dict` output."""
        data = dict(data)
        data["layers"] = [Layer(**layer) for layer in data["layers"]]
        return cls(**data)

    @classmethod
    def from_u_value(
        cls,
        name: str,
        u_value: float,
        mass_class: str = "Medium",
        construction_type: str = "ExtWall",
        solar_absorptance: float = 0.6,
    ) -> "ConstructionSpec":
        """Equivalent single-layer construction from U-value and mass class
        (the retained reference ``Construction.from_U_value``, ISO 13786 A.2.3).

        Parameters
        ----------
        name : str
            Construction name.
        u_value : float
            Air-to-air transmittance [W/(m2 K)].
        mass_class : str
            One of ``Very heavy``, ``Heavy``, ``Medium``, ``Light``,
            ``Very light``.
        construction_type : str
            Envelope element type (keys of ``SURFACE_HEAT_TRANSFER_COEF``).
        solar_absorptance : float
            External solar absorptance [-].
        """
        if mass_class not in _MASS_CLASS_DENSITY:
            raise ValueError(f"Unknown mass class '{mass_class}' for construction '{name}'")
        coefs = SURFACE_HEAT_TRANSFER_COEF[construction_type]
        net_resistance = 1.0 / u_value - 1.0 / coefs["outside"] - 1.0 / coefs["inside"]
        if net_resistance <= 0.0:
            raise ValueError(f"Construction '{name}': U-value {u_value} too high to be physical")
        layer = Layer(
            thickness=_EQUIVALENT_THICKNESS,
            conductivity=_EQUIVALENT_THICKNESS / net_resistance,
            density=_MASS_CLASS_DENSITY[mass_class],
            specific_heat=_EQUIVALENT_SPEC_HEAT,
        )
        return cls(name, construction_type, [layer], solar_absorptance)


@dataclass
class WindowSpec:
    """Glazing system description (SI units).

    Simplification vs the retained reference: a constant solar heat gain coefficient with a
    fixed diffuse correction, instead of spline-interpolated angular SHGC
    (extension point).
    """

    u_value: float  # [W/(m2 K)]
    shgc: float  # solar heat gain coefficient at normal incidence [-]
    frame_factor: float = 0.2  # frame fraction of the window area [-]
    shading_coef: float = 1.0  # external+internal shading reduction [-]

    def to_dict(self) -> dict:
        """Plain-dict representation for JSON serialisation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "WindowSpec":
        """Rebuild from :meth:`to_dict` output."""
        return cls(**data)


@dataclass
class EnvelopeArchetype:
    """Complete envelope archetype: one construction per element + window.

    ``constructions`` is keyed by construction type (``ExtWall``, ``Roof``,
    ...). ``wwr`` is the window-to-wall ratio applied to external walls;
    ``infiltration_ach`` the envelope airtightness [1/h].
    """

    name: str
    constructions: dict[str, ConstructionSpec]
    window: WindowSpec
    wwr: float = 0.15
    infiltration_ach: float = 0.3

    def to_dict(self) -> dict:
        """Plain-dict representation for JSON serialisation."""
        return {
            "name": self.name,
            "constructions": {k: c.to_dict() for k, c in self.constructions.items()},
            "window": self.window.to_dict(),
            "wwr": self.wwr,
            "infiltration_ach": self.infiltration_ach,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EnvelopeArchetype":
        """Rebuild from :meth:`to_dict` output."""
        return cls(
            name=data["name"],
            constructions={
                k: ConstructionSpec.from_dict(c) for k, c in data["constructions"].items()
            },
            window=WindowSpec.from_dict(data["window"]),
            wwr=data["wwr"],
            infiltration_ach=data["infiltration_ach"],
        )


def load_envelope_archetypes(path: str | Path) -> dict[str, EnvelopeArchetype]:
    """Load a TABULA/URBEM-style envelope archetype JSON database (FR-07).

    See ``data/examples/archetypes_tabula_like.json`` for the schema: for each
    archetype, every opaque element gives ``u_value``, ``mass_class`` and
    optionally ``absorptance``; ``window`` gives ``u_value``, ``shgc`` and
    optionally ``frame_factor``; plus ``wwr`` and ``infiltration_ach``.
    Missing internal elements (``int_floor``) are derived by flipping
    ``int_ceiling``, as in the retained reference.

    Parameters
    ----------
    path : str or pathlib.Path
        JSON archetype database.

    Returns
    -------
    dict
        Archetype name → :class:`EnvelopeArchetype`.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    archetypes: dict[str, EnvelopeArchetype] = {}
    for name, spec in data.get("envelopes", data).items():
        if name.startswith("_"):  # comment keys
            continue
        constructions: dict[str, ConstructionSpec] = {}
        for key, ctype in _OPAQUE_ELEMENTS.items():
            if key not in spec:
                continue
            element = spec[key]
            if "layers" in element:
                # Explicit multi-layer stratigraphy, outside -> inside (e.g.
                # the 1:1 port of the retained reference's Materials.xlsx). Preferred over
                # the U-value + mass-class form when both are present.
                constructions[ctype] = ConstructionSpec(
                    name=f"{name}_{ctype}",
                    construction_type=ctype,
                    layers=[Layer(**layer) for layer in element["layers"]],
                    solar_absorptance=float(element.get("absorptance", 0.6)),
                )
            else:
                constructions[ctype] = ConstructionSpec.from_u_value(
                    name=f"{name}_{ctype}",
                    u_value=float(element["u_value"]),
                    mass_class=element.get("mass_class", "Medium"),
                    construction_type=ctype,
                    solar_absorptance=float(element.get("absorptance", 0.6)),
                )
        # IntFloor defaults to the flipped IntCeiling stratigraphy (single
        # equivalent layer -> same layer, different film coefficients type)
        if "IntFloor" not in constructions and "IntCeiling" in constructions:
            ceiling = constructions["IntCeiling"]
            constructions["IntFloor"] = ConstructionSpec(
                name=f"{name}_IntFloor",
                construction_type="IntFloor",
                layers=list(reversed(ceiling.layers)),
                solar_absorptance=ceiling.solar_absorptance,
            )
        missing = {"ExtWall", "Roof", "GroundFloor", "IntWall", "IntCeiling"} - set(constructions)
        if missing:
            raise ValueError(f"Archetype '{name}': missing envelope elements {sorted(missing)}")
        window = spec["window"]
        archetypes[name] = EnvelopeArchetype(
            name=name,
            constructions=constructions,
            window=WindowSpec(
                u_value=float(window["u_value"]),
                shgc=float(window["shgc"]),
                frame_factor=float(window.get("frame_factor", 0.2)),
                shading_coef=float(window.get("shading_coef", 1.0)),
            ),
            wwr=float(spec.get("wwr", 0.15)),
            infiltration_ach=float(spec.get("infiltration_ach", 0.3)),
        )
    return archetypes
