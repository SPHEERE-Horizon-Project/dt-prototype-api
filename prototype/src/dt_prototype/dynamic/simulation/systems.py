"""HVAC plant (system) models: zone + DHW loads → fuel and electricity use.

Migrated from ``reference_building.systems`` / ``systems_info``:

- :class:`Boiler` — gas boilers with the **UNI-TS 11300-2 part-load loss
  model** (corrected efficiencies at nominal/intermediate power, no-load
  losses, quadratic loss interpolation, auxiliary power), ported faithfully
  from the retained reference ``CondensingBoiler`` / ``TraditionalBoiler`` including their
  size tables;
- :class:`HeatPump` — Staffell COP curves (air/ground source) with the
  EN 15316 emission/distribution chain;
- :class:`FuelHeating` — EN 15316-style constant-efficiency generators for
  oil/coal/stove/district-heating (as the retained reference ``Heating_EN15316``);
- :class:`ElectricChiller` — part-load EER interpolation from the the retained reference
  system tables;
- :class:`HeatingFromParams` / :class:`CoolingFromParams` — systems built
  from explicit template parameters (the retained reference ``Systems.xlsx`` rows, see the
  ``systems_templates.json`` database);
- all heating systems serve the **domestic hot water** load through the
  EN 15316 DHW distribution efficiency; EXTENDED: when a
  :class:`dt_prototype.dynamic.simulation.dhw_tank.DhwTank` is attached
  (``SimulationConfig.dhw_tank``), the generator sees the tank's smoothed
  thermostat charge power instead of the instantaneous draw-off.

System names from the GeoJSON attributes are resolved by
:func:`resolve_heating_system` / :func:`resolve_cooling_system` in two
steps, as in the retained reference: (1) template lookup against the loaded
``systems_templates.json`` database (short codes like ``s19``); (2)
catalog-name parsing of descriptive names such as
``"A-W Heat Pump, Single, Fan coil"``. Only names found in neither fall
back to :class:`IdealLoad`, reported as a structured warning (attached by
the runner to ``DataFrame.attrs["warnings"]``).

Emission/distribution efficiencies and convective fractions are the retained reference's
EN 15316 tables (``systems_info``). Radiative/convective sigma splits are
provided to the zone solver exactly as in the retained reference.

EXTENSION POINT (new plants, NFR-06): subclass :class:`HeatingSystem` or
:class:`CoolingSystem` and add a branch to the catalog factories — or, for
parametric systems, just add a row to ``systems_templates.json`` (no code
changes).
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass

import numpy as np

from dt_prototype.dynamic.simulation.dhw_tank import DhwTank

# ------------------------------------------------------------------ #
# EN 15316 tables (the retained reference systems_info)
# ------------------------------------------------------------------ #
# emitter type -> (efficiency [-], convective fraction [-], water temp [°C])
_EMITTERS_HEATING = {
    "High Temp Radiator": (0.820, 0.65, 70.0),
    "Low Temp Radiator": (0.882, 0.60, 60.0),
    "Fan coil": (0.862, 1.00, 40.0),
    "Radiant surface": (0.857, 0.35, 35.0),
}
_EMITTERS_COOLING = {
    "Fan coil": (0.748, 1.00),
    "Radiant surface": (0.777, 0.35),
    "Split system": (0.842, 1.00),
}
_DISTRIBUTION_HEATING = {"Centralized": 0.92, "Single": 0.97}
_DISTRIBUTION_COOLING = {"Centralized": 0.97, "Single": 0.97}
_DHW_DISTRIBUTION_EFF = 0.97  # EN 15316 emission+distribution for DHW

# constant seasonal generation efficiencies (EN 15316 table, ~100 kW column)
_GENERATION_EFF = {
    "oil": 0.92,
    "coal": 0.83,
    "wood": 0.83,
    "district_heat": 1.0,
}

_DEFAULT_EMITTER = "Fan coil"
_DEFAULT_DISTRIBUTION = "Single"

# ------------------------------------------------------------------ #
# UNI-TS 11300-2 boiler tables (the retained reference systems_info), one row per size class:
# (size [kW], eta_nom [%], eta_int [%], T_gn_w [°C], f_cor_Pn [-],
#  P_int [% of Pn], T_gn_Pint [°C], f_cor_Pint [-], location)
# ------------------------------------------------------------------ #
_BOILER_TABLES = {
    "condensing": {
        "rows": [
            (10, 98.6, 103.9, 70.0, 0.2, 0.3, 35.0, 0.2, "internal"),
            (30, 98.3, 104.5, 70.0, 0.2, 0.3, 35.0, 0.2, "internal"),
            (100, 99.1, 104.9, 70.0, 0.2, 0.3, 35.0, 0.2, "tech_room"),
            (300, 99.2, 105.0, 70.0, 0.2, 0.3, 35.0, 0.2, "tech_room"),
        ],
        "theta_test_pn": 70.0,
        "theta_test_pint": 35.0,
    },
    "traditional": {
        "rows": [
            (10, 92.4, 89.6, 70.0, 0.04, 0.3, 50.0, 0.05, "internal"),
            (30, 95.0, 91.0, 70.0, 0.04, 0.3, 50.0, 0.05, "internal"),
            (100, 95.2, 94.0, 70.0, 0.04, 0.3, 50.0, 0.05, "tech_room"),
            (300, 96.0, 98.0, 70.0, 0.04, 0.3, 50.0, 0.05, "tech_room"),
        ],
        "theta_test_pn": 70.0,
        "theta_test_pint": 50.0,
    },
}
_THETA_A_TEST = 20.0  # [°C] test room temperature (UNI-TS)

# Part-load EER table of the the retained reference split/chiller systems:
# load factor -> EER
_EER_LOAD_FACTORS = np.array([0.25, 0.50, 0.75, 1.00])
_EER_VALUES = np.array([2.83, 2.94, 2.68, 2.35])


@dataclass
class SystemOutput:
    """Energy carriers consumed in one time step, as average power [W]."""

    electric: float = 0.0
    gas: float = 0.0  # fuel energy (LHV)
    district_heat: float = 0.0
    other_fuel: float = 0.0  # oil / coal / wood (LHV)


class _System(abc.ABC):
    """Common base: sigma split, capacity setting, load → carriers."""

    #: convective fraction of the heat emission [-]
    convective_fraction: float = 0.65
    #: optional DHW storage tank between generator and draw-off (EXTENDED)
    dhw_tank: DhwTank | None = None

    def _dhw_generator_load(self, dhw: float) -> float:
        """DHW load seen by the generator [W]: routed through the storage
        tank when one is attached (smoothed thermostat charge power),
        instantaneous draw-off otherwise."""
        if self.dhw_tank is None:
            return dhw
        return self.dhw_tank.step(dhw)

    def sigma(self, n: int) -> tuple[float, ...]:
        """Load split for a thermal model with ``n`` sigma components:
        2 → (radiative, convective) [5R1C]; 3 → (rad IW, rad AW, convective)
        [7R2C], as in the retained reference."""
        cf = self.convective_fraction
        if n == 2:
            return (1.0 - cf, cf)
        return ((1.0 - cf) / 2.0, (1.0 - cf) / 2.0, cf)

    def set_capacity(self, design_power: float) -> None:
        """Set the design (nominal) power [W]; default: no sizing needed."""

    @abc.abstractmethod
    def solve(self, load: float, t_ext: float, dhw: float = 0.0) -> SystemOutput:
        """Convert the delivered thermal loads [W] into carrier consumption.

        Parameters
        ----------
        load : float
            Space conditioning load delivered to the zone [W] (heating
            positive, cooling negative).
        t_ext : float
            Outdoor air temperature [°C] (source/sink temperature).
        dhw : float
            Domestic hot water thermal demand [W] (heating systems only).
        """


class HeatingSystem(_System, abc.ABC):
    """Base class for heating plants."""


class CoolingSystem(_System, abc.ABC):
    """Base class for cooling plants."""


class IdealLoad(HeatingSystem, CoolingSystem):
    """Ideal system: delivers the load with no consumption accounting."""

    convective_fraction = 0.65

    def solve(self, load: float, t_ext: float, dhw: float = 0.0) -> SystemOutput:
        """Ideal load: no carrier consumption."""
        return SystemOutput()


class Boiler(HeatingSystem):
    """Gas boiler with the UNI-TS 11300-2 part-load loss model
    (port of the retained reference ``CondensingBoiler`` / ``TraditionalBoiler``).

    Parameters
    ----------
    kind : str
        ``"condensing"`` or ``"traditional"``.
    emitter, distribution : str or None
        EN 15316 emission/distribution chain applied to the zone load; None
        reproduces the retained reference's bare ``CondensingBoiler``/``TraditionalBoiler``
        behaviour (generator only, convective fraction 0.5).
    """

    def __init__(
        self,
        kind: str = "condensing",
        emitter: str | None = None,
        distribution: str | None = None,
    ) -> None:
        self.kind = kind
        self._table = _BOILER_TABLES[kind]
        if emitter is None:
            self.emission_distribution_eff = 1.0
            self.convective_fraction = 0.5
        else:
            eff, conv, _ = _EMITTERS_HEATING[emitter]
            self.emission_distribution_eff = eff * _DISTRIBUTION_HEATING[
                distribution or _DEFAULT_DISTRIBUTION
            ]
            self.convective_fraction = conv
        self.design_power: float | None = None

    def set_capacity(self, design_power: float) -> None:
        """Size the boiler: select the size class and derive the UNI-TS
        quantities (intermediate power, no-load losses, auxiliaries)."""
        self.design_power = max(design_power, 1000.0)
        rows = self._table["rows"]
        # size-class selection as in the retained reference (smallest class covering Pn)
        self._row = rows[-1]
        prev_size = 0.0
        for row in rows:
            if prev_size < self.design_power <= row[0] * 1000.0:
                self._row = row
                break
            prev_size = row[0] * 1000.0
        size, eta_nom, eta_int, t_gn_w, f_cor_pn, p_int_frac, t_gn_pint, f_cor_pint, location = (
            self._row
        )
        self.p_int = p_int_frac * self.design_power  # [W]
        self.theta_a_gn = 20.0 if location == "internal" else 15.0

        p_check = min(self.design_power, 400_000.0)
        if self.kind == "condensing":
            self.phi_p0 = p_check * 4.8 / 100.0 * (p_check / 1000.0) ** (-0.35)  # [W]
        else:
            self.phi_p0 = (p_check / 1000.0) * 10.0 * 8.5 * (p_check / 1000.0) ** (-0.4)  # [W]

        # corrected efficiencies/losses at nominal and intermediate power
        eta_pn_cor = eta_nom + f_cor_pn * (self._table["theta_test_pn"] - t_gn_w)
        self.phi_pn_cor = (100.0 - eta_pn_cor) / eta_pn_cor * self.design_power  # [W]
        eta_pint_cor = eta_int + f_cor_pint * (self._table["theta_test_pint"] - t_gn_pint)
        self.phi_pint_cor = (100.0 - eta_pint_cor) / eta_pint_cor * self.p_int  # [W]
        # corrected no-load losses
        self.phi_p0_cor = self.phi_p0 * (
            (t_gn_w - self.theta_a_gn) / (self._table["theta_test_pn"] - _THETA_A_TEST)
        ) ** 1.25

        # auxiliary electric powers (UNI-TS)
        kw = self.design_power / 1000.0
        self.w_aux_pn = 45.0 * kw**0.48
        self.w_aux_pint = 15.0 * kw**0.48
        self.w_aux_p0 = 15.0
        self.fc_pint = self.p_int / self.design_power

    def solve(self, load: float, t_ext: float, dhw: float = 0.0) -> SystemOutput:
        """UNI-TS 11300-2 generation losses and auxiliaries at part load."""
        if self.design_power is None:
            raise RuntimeError("Boiler.set_capacity must be called before solve")
        heat_flow = (
            max(load, 0.0) / self.emission_distribution_eff
            + self._dhw_generator_load(dhw) / _DHW_DISTRIBUTION_EFF
        )
        if heat_flow <= 0.0:
            return SystemOutput()

        pn, pint = self.design_power / 1000.0, self.p_int / 1000.0
        p0, ppn, ppint = self.phi_p0_cor / 1000.0, self.phi_pn_cor / 1000.0, self.phi_pint_cor / 1000.0
        px = heat_flow / 1000.0
        # quadratic interpolation of the generation losses (UNI-TS 11300-2)
        denom = pn * pint * (pn - pint)
        phi_1 = px**2 * (pint * (ppn - p0) - pn * (ppint - p0)) / denom
        phi_2 = px * (pn**2 * (ppint - p0) - pint**2 * (ppn - p0)) / denom
        losses = (phi_1 + phi_2 + p0) * 1000.0  # [W]

        # auxiliary power (piecewise linear in the load factor)
        fc = min(heat_flow / self.design_power, 1.0)
        if fc <= self.fc_pint:
            w_aux = self.w_aux_p0 + fc / self.fc_pint * (self.w_aux_pint - self.w_aux_p0)
        else:
            w_aux = self.w_aux_pint + (fc - self.fc_pint) * (self.w_aux_pn - self.w_aux_pint) / (
                1.0 - self.fc_pint
            )

        return SystemOutput(electric=w_aux, gas=heat_flow + losses)


class FuelHeating(HeatingSystem):
    """Constant-efficiency generator for oil/coal/stove/district heating
    (EN 15316 chain, as the retained reference ``Heating_EN15316``)."""

    def __init__(
        self,
        generation_efficiency: float,
        carrier: str = "other_fuel",
        emitter: str = _DEFAULT_EMITTER,
        distribution: str = _DEFAULT_DISTRIBUTION,
        aux_electric_fraction: float = 0.005,
    ) -> None:
        emission_eff, conv_frac, _ = _EMITTERS_HEATING[emitter]
        self.generation_efficiency = generation_efficiency
        self.emission_distribution_eff = emission_eff * _DISTRIBUTION_HEATING[distribution]
        self.carrier = carrier
        self.convective_fraction = conv_frac
        self.aux_electric_fraction = aux_electric_fraction

    def solve(self, load: float, t_ext: float, dhw: float = 0.0) -> SystemOutput:
        """Fuel energy for the space heating + DHW loads."""
        gen_load = (
            max(load, 0.0) / self.emission_distribution_eff
            + self._dhw_generator_load(dhw) / _DHW_DISTRIBUTION_EFF
        )
        if gen_load <= 0.0:
            return SystemOutput()
        fuel = gen_load / self.generation_efficiency
        out = SystemOutput(electric=self.aux_electric_fraction * gen_load)
        setattr(out, self.carrier, getattr(out, self.carrier) + fuel)
        return out


class ElectricHeater(HeatingSystem):
    """Direct electric heating (generation efficiency 1)."""

    convective_fraction = 0.6

    def solve(self, load: float, t_ext: float, dhw: float = 0.0) -> SystemOutput:
        """Electric demand equals the delivered load (+ DHW)."""
        demand = max(load, 0.0) + self._dhw_generator_load(dhw) / _DHW_DISTRIBUTION_EFF
        return SystemOutput(electric=demand)


class HeatPump(HeatingSystem):
    """Air-/ground-source water-based heat pump, Staffell COP curve
    (faithful port of the retained reference ``HP_Staffell``).

    COP = 6.81 - 0.121 dT + 0.000630 dT^2   (air-water)
    COP = 8.77 - 0.150 dT + 0.000734 dT^2   (ground-water)
    with dT = T_emitter - T_source. DHW is produced at 60 °C.
    """

    _DHW_TEMPERATURE = 60.0  # [°C]

    def __init__(
        self,
        source: str = "air",  # "air" or "ground"
        emitter: str = _DEFAULT_EMITTER,
        distribution: str = _DEFAULT_DISTRIBUTION,
        ground_temperature: float = 12.0,
    ) -> None:
        emission_eff, conv_frac, t_emitter = _EMITTERS_HEATING[emitter]
        self.source = source
        self.t_emitter = t_emitter
        self.ground_temperature = ground_temperature
        self.emission_distribution_eff = emission_eff * _DISTRIBUTION_HEATING[distribution]
        self.convective_fraction = conv_frac

    def cop(self, t_source: float, t_emitter: float) -> float:
        """Staffell regression COP for the given source/sink temperatures."""
        dt = t_emitter - t_source
        if self.source == "ground":
            return max(8.77 - 0.150 * dt + 0.000734 * dt**2, 1.0)
        return max(6.81 - 0.121 * dt + 0.000630 * dt**2, 1.0)

    def solve(self, load: float, t_ext: float, dhw: float = 0.0) -> SystemOutput:
        """Electric demand via COP at the current source temperature."""
        t_source = t_ext if self.source == "air" else self.ground_temperature
        electric = 0.0
        if load > 0.0:
            electric += load / self.emission_distribution_eff / self.cop(t_source, self.t_emitter)
        dhw_gen = self._dhw_generator_load(dhw)
        if dhw_gen > 0.0:
            electric += dhw_gen / _DHW_DISTRIBUTION_EFF / self.cop(t_source, self._DHW_TEMPERATURE)
        return SystemOutput(electric=electric)


class ElectricChiller(CoolingSystem):
    """Vapour-compression cooling with the the retained reference part-load EER table
    (``SplitAirCooler`` / ``ChillerAirtoWater`` system data).

    The EER is interpolated on the load factor (EER_25..EER_100) and
    additionally derated linearly with the outdoor temperature above the
    35 °C rating point (simplification of the original's temperature
    polynomials).
    """

    def __init__(self, emitter: str = "Split system", distribution: str = _DEFAULT_DISTRIBUTION) -> None:
        emission_eff, conv_frac = _EMITTERS_COOLING[emitter]
        self.emission_distribution_eff = emission_eff * _DISTRIBUTION_COOLING[distribution]
        self.convective_fraction = conv_frac
        self.design_power: float | None = None  # positive magnitude [W]

    def set_capacity(self, design_power: float) -> None:
        """Set the nominal cooling capacity (positive magnitude [W])."""
        self.design_power = max(abs(design_power), 1000.0)

    def eer(self, load_factor: float, t_ext: float) -> float:
        """Part-load EER with outdoor-temperature derating."""
        eer_pl = float(np.interp(load_factor, _EER_LOAD_FACTORS, _EER_VALUES))
        derating = 1.0 - 0.01 * max(t_ext - 35.0, 0.0)
        return max(eer_pl * derating, 1.0)

    def solve(self, load: float, t_ext: float, dhw: float = 0.0) -> SystemOutput:
        """Electric demand for the delivered cooling load (negative)."""
        if load >= 0.0:
            return SystemOutput()
        if self.design_power is None:
            raise RuntimeError("ElectricChiller.set_capacity must be called before solve")
        gen_load = -load / self.emission_distribution_eff
        load_factor = min(gen_load / self.design_power, 1.0)
        return SystemOutput(electric=gen_load / self.eer(load_factor, t_ext))


class HeatingFromParams(HeatingSystem):
    """Heating system from an explicit template (the retained reference ``HeatingFromParams``
    / ``Systems.xlsx`` row): EN 15316 chain
    emission x regulation x distribution x generation, separate DHW chain,
    optional COP for electric generation (heat pumps).

    Parameters
    ----------
    params : dict
        One entry of the ``heating_systems`` template database
        (see ``dt_prototype.common.preprocessing.system_templates``).
    """

    def __init__(self, params: dict) -> None:
        self.description = params.get("description", "")
        self.convective_fraction = float(params["convective_fraction"])
        self.total_efficiency = (
            params["emission_efficiency"]
            * params["regulation_efficiency"]
            * params["distribution_efficiency"]
            * params["generation_efficiency"]
        )
        self.cop = params.get("cop") or 1.0
        self.fuel = params["fuel"]
        self.dhw_total_efficiency = (
            params["dhw_emission_efficiency"]
            * params["dhw_regulation_efficiency"]
            * params["dhw_distribution_efficiency"]
            * params["dhw_generation_efficiency"]
        )
        self.dhw_cop = params.get("dhw_cop") or 1.0
        self.dhw_fuel = params["dhw_fuel"]

    def solve(self, load: float, t_ext: float, dhw: float = 0.0) -> SystemOutput:
        """Carrier consumption via the template efficiency chains."""
        out = SystemOutput()
        if load > 0.0:
            energy = load / self.total_efficiency
            if self.fuel == "electric":
                energy /= self.cop
            setattr(out, self.fuel, getattr(out, self.fuel) + energy)
        dhw_gen = self._dhw_generator_load(dhw)  # EXTENDED: via storage tank
        if dhw_gen > 0.0:
            energy = dhw_gen / self.dhw_total_efficiency
            if self.dhw_fuel == "electric":
                energy /= self.dhw_cop
            setattr(out, self.dhw_fuel, getattr(out, self.dhw_fuel) + energy)
        return out


class CoolingFromParams(CoolingSystem):
    """Cooling system from an explicit template (the retained reference ``CoolingFromParams``
    / ``Systems.xlsx`` row): EN 15316 chain with a constant EER.

    Parameters
    ----------
    params : dict
        One entry of the ``cooling_systems`` template database.
    """

    def __init__(self, params: dict) -> None:
        self.description = params.get("description", "")
        self.convective_fraction = float(params["convective_fraction"])
        self.total_efficiency = (
            params["emission_efficiency"]
            * params["regulation_efficiency"]
            * params["distribution_efficiency"]
        )
        self.eer = float(params["eer"])
        self.fuel = params["fuel"]

    def solve(self, load: float, t_ext: float, dhw: float = 0.0) -> SystemOutput:
        """Carrier consumption for the delivered cooling load (negative)."""
        if load >= 0.0:
            return SystemOutput()
        energy = -load / self.total_efficiency / self.eer
        out = SystemOutput()
        setattr(out, self.fuel, energy)
        return out


# ------------------------------------------------------------------ #
# Resolvers: template lookup → catalog-name parsing → IdealLoad
# ------------------------------------------------------------------ #
def _parse_parts(name: str, emitters: dict) -> tuple[str, str | None]:
    """Extract (distribution, emitter) from an the retained reference-style system name."""
    parts = [p.strip() for p in name.split(",")]
    distribution = next(
        (p for p in parts if p in _DISTRIBUTION_HEATING), _DEFAULT_DISTRIBUTION
    )
    emitter = next((p for p in parts if p in emitters), None)
    return distribution, emitter


def _catalog_heating_system(name: str) -> HeatingSystem | None:
    """Parse a descriptive catalog name into a heating system; None if the
    name matches no known pattern."""
    distribution, emitter = _parse_parts(name, _EMITTERS_HEATING)
    low = name.lower()
    if "heat pump" in low or low.startswith(("a-w hp", "g-w hp", "hp ")):
        source = "ground" if name.startswith("G-W") else "air"
        return HeatPump(source=source, emitter=emitter or _DEFAULT_EMITTER, distribution=distribution)
    if "condensing" in low:  # incl. exact "CondensingBoiler"
        return Boiler("condensing", emitter=emitter, distribution=distribution)
    if "traditional" in low:  # incl. exact "TraditionalBoiler"
        return Boiler("traditional", emitter=emitter, distribution=distribution)
    if "oil" in low:
        return FuelHeating(_GENERATION_EFF["oil"], "other_fuel", emitter or "High Temp Radiator", distribution)
    if "coal" in low or "stove" in low:
        return FuelHeating(_GENERATION_EFF["coal"], "other_fuel", emitter or "High Temp Radiator", distribution)
    if "district heating" in low:
        return FuelHeating(_GENERATION_EFF["district_heat"], "district_heat", emitter or _DEFAULT_EMITTER, distribution)
    if "electric" in low:
        return ElectricHeater()
    return None


def _catalog_cooling_system(name: str) -> CoolingSystem | None:
    """Parse a descriptive catalog name into a cooling system; None if the
    name matches no known pattern."""
    low = name.lower()
    if "a-a" in low or "split" in low:
        return ElectricChiller(emitter="Split system")
    if "chiller" in low:
        distribution, emitter = _parse_parts(name, _EMITTERS_COOLING)
        return ElectricChiller(emitter=emitter or "Fan coil", distribution=distribution)
    return None


def resolve_heating_system(
    name: str, templates: dict | None = None
) -> tuple[HeatingSystem, str | None]:
    """Resolve a heating system name: template DB → catalog parsing →
    :class:`IdealLoad`.

    Parameters
    ----------
    name : str
        GeoJSON ``Heating System`` attribute (template code, catalog name,
        ``"IdealLoad"`` or empty).
    templates : dict, optional
        Loaded template database
        (``dt_prototype.common.preprocessing.system_templates.load_system_templates``).

    Returns
    -------
    tuple
        ``(system, warning)`` — ``warning`` is None when the name resolved,
        otherwise a message explaining the IdealLoad fallback.
    """
    n = name.strip()
    if n in ("", "IdealLoad"):
        return IdealLoad(), None
    if templates and n in templates.get("heating_systems", {}):
        return HeatingFromParams(templates["heating_systems"][n]), None
    system = _catalog_heating_system(n)
    if system is not None:
        return system, None
    return IdealLoad(), f"unknown heating system '{name}': falling back to IdealLoad"


def resolve_cooling_system(
    name: str, templates: dict | None = None
) -> tuple[CoolingSystem, str | None]:
    """Resolve a cooling system name: template DB → catalog parsing →
    :class:`IdealLoad`. See :func:`resolve_heating_system`."""
    n = name.strip()
    if n in ("", "IdealLoad"):
        return IdealLoad(), None
    if templates and n in templates.get("cooling_systems", {}):
        return CoolingFromParams(templates["cooling_systems"][n]), None
    system = _catalog_cooling_system(n)
    if system is not None:
        return system, None
    return IdealLoad(), f"unknown cooling system '{name}': falling back to IdealLoad"


def heating_system_from_name(name: str, templates: dict | None = None) -> HeatingSystem:
    """Resolve a heating system name into a :class:`HeatingSystem`;
    unknown names → :class:`IdealLoad` with a logged warning."""
    system, warning = resolve_heating_system(name, templates)
    if warning:
        logging.warning(warning)
    return system


def cooling_system_from_name(name: str, templates: dict | None = None) -> CoolingSystem:
    """Resolve a cooling system name into a :class:`CoolingSystem`;
    unknown names → :class:`IdealLoad` with a logged warning."""
    system, warning = resolve_cooling_system(name, templates)
    if warning:
        logging.warning(warning)
    return system
