"""End-use schedule archetypes (FR-05).

Migrated from ``reference_ubem.end_uses`` / ``reference_building.schedule`` /
``internal_load`` / ``setpoints`` / ``ventilation``, simplified under the
80/20 rule: each end use (residential, services, ...) is described by 24-value
weekday/weekend daily profiles in a JSON database (see
``data/examples/schedules_urbem_like.json``), expanded here to annual arrays.

Schedule quantities per end use (SI units, per m2 of net floor area where
applicable):

- ``people``, ``appliances``, ``lighting``: sensible gains [W/m2], each with
  a radiant fraction (the rest is convective);
- ``people_latent``: latent (vapour) internal gains [W/m2];
- ``heating_setpoint`` / ``cooling_setpoint``: air temperature bands [°C];
- ``humidity_setpoint_low`` / ``humidity_setpoint_high``: relative humidity
  band [0-1] for (de)humidification control;
- ``ventilation_ach``: mechanical+natural ventilation air changes [1/h];
- ``dhw`` (optional): domestic hot water demand — ``volume_per_m2_day``
  [l/(m2 day)] distributed over a daily ``profile`` (UNI-TS 11300-2 default
  shape, as in the retained reference); EXTENDED: ``"method": "stochastic"`` switches to
  per-building DHWcalc event generation
  (:mod:`dt_prototype.common.preprocessing.dhw_stochastic`);
- ``ahu`` (optional): air handling unit parameters applied to the mechanical
  ventilation air (heat recovery efficiencies, supply set points, humidity
  control, EXTENDED ``outdoor_air_ratio`` for recirculation) — consumed by
  ``dt_prototype.dynamic.simulation.air_handling_unit``;
- ``natural_ventilation`` (optional, EXTENDED): window-opening free-cooling
  parameters (``ach_max``, ``zone_temperature_threshold``,
  ``min_outdoor_temperature``).

EXTENSION POINT (new end uses, NFR-06): add entries to the JSON database —
no code changes required.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

import numpy as np
import pandas as pd
from dt_prototype.common.input_validation import validate_calendar, validate_resolution

_GAIN_KEYS = ("people", "appliances", "lighting")

# UNI-TS 11300-2 default daily DHW draw-off shape (relative weights per hour),
# migrated from reference_building.domestic_hot_water
_DHW_DEFAULT_PROFILE = [
    0.500, 0.502, 0.504, 0.957, 0.984, 1.042, 1.102, 1.120, 1.126, 1.131,
    1.133, 1.132, 1.133, 1.136, 1.133, 1.135, 1.134, 1.134, 1.135, 1.133,
    1.122, 1.102, 0.972, 0.498,
]


def _optional_array(value) -> np.ndarray | None:
    """None-preserving array conversion, for the optional schedule arrays."""
    return None if value is None else np.asarray(value, dtype=float)


@dataclass
class EndUseSchedule:
    """Annual schedule arrays for one end use, ready for simulation.

    All arrays have length ``8760 * time_steps_per_hour``.

    Attributes
    ----------
    internal_gain_convective : numpy.ndarray
        Convective sensible internal gains [W/m2].
    internal_gain_radiative : numpy.ndarray
        Radiative sensible internal gains [W/m2].
    internal_gain_latent : numpy.ndarray
        Latent (vapour) internal gains [W/m2].
    heating_setpoint, cooling_setpoint : numpy.ndarray
        Zone air temperature setpoints [°C] (dual band).
    humidity_setpoint_low, humidity_setpoint_high : numpy.ndarray
        Relative humidity control band [0-1].
    ventilation_ach : numpy.ndarray
        Ventilation air change rate [1/h].
    electric_load : numpy.ndarray
        Electric consumption of appliances + lighting [W/m2] (for KPIs).
    dhw_volume_flow : numpy.ndarray
        Domestic hot water draw-off [m3/(s m2) of net floor area].
    ahu : dict or None
        Air handling unit parameters (see
        :class:`dt_prototype.dynamic.simulation.air_handling_unit.AirHandlingUnit`);
        None = no AHU, ventilation supplies outdoor air.
    """

    name: str
    internal_gain_convective: np.ndarray
    internal_gain_radiative: np.ndarray
    internal_gain_latent: np.ndarray
    heating_setpoint: np.ndarray
    cooling_setpoint: np.ndarray
    humidity_setpoint_low: np.ndarray
    humidity_setpoint_high: np.ndarray
    ventilation_ach: np.ndarray
    electric_load: np.ndarray
    dhw_volume_flow: np.ndarray = field(default_factory=lambda: np.zeros(0))
    ahu: dict | None = None
    # Optional the retained reference-native forms (see load_end_use_schedules). When set,
    # infiltration_ach overrides the envelope archetype's scalar, and
    # ventilation_flow_per_area [m3/(s m2)] overrides ventilation_ach.
    infiltration_ach: np.ndarray | None = None
    ventilation_flow_per_area: np.ndarray | None = None
    # EXTENDED: window-opening free cooling (ach_max,
    # zone_temperature_threshold, min_outdoor_temperature); None = disabled
    natural_ventilation: dict | None = None
    # EXTENDED: "profile" or "stochastic" (DHWcalc events, resolved per
    # building in assemble_building_input); daily volume kept for the latter
    dhw_method: str = "profile"
    dhw_volume_per_m2_day: float = 0.0

    def to_dict(self) -> dict:
        """Plain-dict (lists) representation for JSON serialisation (FR-08)."""
        return {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in asdict(self).items()}

    @classmethod
    def from_dict(cls, data: dict) -> "EndUseSchedule":
        """Rebuild from :meth:`to_dict` output."""
        return cls(
            name=data["name"],
            ahu=data.get("ahu"),
            natural_ventilation=data.get("natural_ventilation"),
            dhw_method=data.get("dhw_method", "profile"),
            dhw_volume_per_m2_day=data.get("dhw_volume_per_m2_day", 0.0),
            # optional the retained reference-native arrays: absent/None in the simpler
            # databases, but must survive the JSON round-trip when present
            infiltration_ach=_optional_array(data.get("infiltration_ach")),
            ventilation_flow_per_area=_optional_array(data.get("ventilation_flow_per_area")),
            **{
                k: np.asarray(data[k], dtype=float)
                for k in (
                    "internal_gain_convective",
                    "internal_gain_radiative",
                    "internal_gain_latent",
                    "heating_setpoint",
                    "cooling_setpoint",
                    "humidity_setpoint_low",
                    "humidity_setpoint_high",
                    "ventilation_ach",
                    "electric_load",
                    "dhw_volume_flow",
                )
            },
        )


def expand_daily_profiles(
    weekday: list[float],
    weekend: list[float],
    year: int = 2023,
    time_steps_per_hour: int = 1,
) -> np.ndarray:
    """Expand 24-value weekday/weekend daily profiles to one annual array.

    Parameters
    ----------
    weekday, weekend : list of float
        24 hourly values each.
    year : int
        Calendar year (drives the weekday/weekend pattern).
    time_steps_per_hour : int
        Sub-hourly repetition factor (values are held constant within the
        hour; FR-12).

    Returns
    -------
    numpy.ndarray
        Array of length ``8760 * time_steps_per_hour``.
    """
    validate_calendar(year)
    validate_resolution(time_steps_per_hour)
    if len(weekday) != 24 or len(weekend) != 24:
        raise ValueError("Daily profiles must have exactly 24 values")
    days = pd.date_range(start=f"{year}-01-01", periods=365, freq="D")
    wd, we = np.asarray(weekday, dtype=float), np.asarray(weekend, dtype=float)
    annual = np.concatenate([we if d.dayofweek >= 5 else wd for d in days])
    return np.repeat(annual, time_steps_per_hour)


def expand_day_type_profiles(
    weekday: list[float],
    saturday: list[float],
    sunday: list[float],
    year: int = 2023,
    time_steps_per_hour: int = 1,
) -> np.ndarray:
    """Expand 24-value weekday/saturday/sunday profiles to one annual array.

    The three-day-type form used by the retained reference's ``Schedules_total.xlsx`` (see
    ``data/examples/schedules.json``); the two-day-type
    :func:`expand_daily_profiles` remains available for the simpler
    weekday/weekend databases.

    Parameters
    ----------
    weekday, saturday, sunday : list of float
        24 hourly values each.
    year : int
        Calendar year (drives the day-of-week pattern).
    time_steps_per_hour : int
        Sub-hourly repetition factor (FR-12).

    Returns
    -------
    numpy.ndarray
        Array of length ``8760 * time_steps_per_hour``.
    """
    validate_calendar(year)
    validate_resolution(time_steps_per_hour)
    for profile in (weekday, saturday, sunday):
        if len(profile) != 24:
            raise ValueError("Daily profiles must have exactly 24 values")
    days = pd.date_range(start=f"{year}-01-01", periods=365, freq="D")
    wd = np.asarray(weekday, dtype=float)
    sa = np.asarray(saturday, dtype=float)
    su = np.asarray(sunday, dtype=float)
    annual = np.concatenate([su if d.dayofweek == 6 else sa if d.dayofweek == 5 else wd
                             for d in days])
    return np.repeat(annual, time_steps_per_hour)


def _profile(spec: dict, key: str, year: int, steps: int, default: float = 0.0) -> np.ndarray:
    """Expand one named profile from the JSON spec (constant fallback).

    Accepts a scalar, a ``weekday``/``weekend`` pair, or a
    ``weekday``/``saturday``/``sunday`` triple (the retained reference form).
    """
    entry = spec.get(key)
    if entry is None:
        return np.full(8760 * steps, default)
    if isinstance(entry, (int, float)):
        return np.full(8760 * steps, float(entry))
    return _expand_entry(entry, year, steps)


def _expand_entry(entry: dict, year: int, steps: int) -> np.ndarray:
    """Expand a profile dict in either the two- or three-day-type form."""
    if "saturday" in entry or "sunday" in entry:
        return expand_day_type_profiles(
            entry["weekday"],
            entry.get("saturday", entry["weekday"]),
            entry.get("sunday", entry.get("saturday", entry["weekday"])),
            year,
            steps,
        )
    return expand_daily_profiles(
        entry["weekday"], entry.get("weekend", entry["weekday"]), year, steps
    )


def load_end_use_schedules(
    path: str | Path, year: int = 2023, time_steps_per_hour: int = 1
) -> dict[str, EndUseSchedule]:
    """Load an end-use schedule JSON database and expand to annual arrays.

    See ``data/examples/schedules_urbem_like.json`` for the schema. Each gain
    entry (``people``, ``appliances``, ``lighting``) has ``weekday`` /
    ``weekend`` 24-value profiles [W/m2] and a ``radiant_fraction``; setpoints
    and ``ventilation_ach`` accept either profiles or scalar constants.

    Parameters
    ----------
    path : str or pathlib.Path
        JSON schedule database.
    year : int
        Reference year (weekday/weekend pattern).
    time_steps_per_hour : int
        Temporal resolution (FR-12).

    Returns
    -------
    dict
        End-use name → :class:`EndUseSchedule`.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    steps = time_steps_per_hour
    schedules: dict[str, EndUseSchedule] = {}
    for name, spec in data.get("end_uses", data).items():
        if name.startswith("_"):  # skip comment keys
            continue
        conv = np.zeros(8760 * steps)
        rad = np.zeros(8760 * steps)
        electric = np.zeros(8760 * steps)
        for key in _GAIN_KEYS:
            if key not in spec:
                continue
            gain = _profile(spec, key, year, steps)
            f_rad = float(spec[key].get("radiant_fraction", 0.5)) if isinstance(spec[key], dict) else 0.5
            conv += gain * (1.0 - f_rad)
            rad += gain * f_rad
            if key in ("appliances", "lighting"):
                electric += gain
        # Domestic hot water: daily volume distributed over the (normalised)
        # daily draw-off profile → [m3/(s m2)]
        dhw_spec = spec.get("dhw")
        if dhw_spec and "flow_l_per_m2_h" in dhw_spec:
            # the retained reference native form: hourly draw-off profile in [L/(m2 h)],
            # per day type -> [m3/(s m2)]
            dhw_flow = _expand_entry(dhw_spec["flow_l_per_m2_h"], year, steps) / 1000.0 / 3600.0
        elif dhw_spec:
            weights = np.asarray(dhw_spec.get("profile", _DHW_DEFAULT_PROFILE), dtype=float)
            hourly_fraction = weights / weights.sum()  # fraction of daily volume per hour
            daily_volume = float(dhw_spec["volume_per_m2_day"]) / 1000.0  # [m3/(m2 day)]
            profile = list(daily_volume * hourly_fraction / 3600.0)  # [m3/(s m2)]
            dhw_flow = expand_daily_profiles(profile, profile, year, steps)
        else:
            dhw_flow = np.zeros(8760 * steps)

        # the retained reference carries infiltration and ventilation as hourly schedules in
        # their native units; both are optional and override, respectively,
        # the envelope archetype's scalar infiltration_ach and the
        # air-change-based ventilation_ach (converted per building in
        # build_zone, where floor area and volume are known).
        infiltration = (
            _profile(spec, "infiltration_ach", year, steps)
            if "infiltration_ach" in spec else None
        )
        ventilation_flow = (
            _profile(spec, "ventilation_flow_per_area", year, steps)
            if "ventilation_flow_per_area" in spec else None
        )

        schedules[name] = EndUseSchedule(
            name=name,
            internal_gain_convective=conv,
            internal_gain_radiative=rad,
            internal_gain_latent=_profile(spec, "people_latent", year, steps, default=0.0),
            heating_setpoint=_profile(spec, "heating_setpoint", year, steps, default=20.0),
            cooling_setpoint=_profile(spec, "cooling_setpoint", year, steps, default=26.0),
            humidity_setpoint_low=_profile(spec, "humidity_setpoint_low", year, steps, default=0.35),
            humidity_setpoint_high=_profile(spec, "humidity_setpoint_high", year, steps, default=0.55),
            ventilation_ach=_profile(spec, "ventilation_ach", year, steps, default=0.5),
            electric_load=electric,
            dhw_volume_flow=dhw_flow,
            ahu=spec.get("ahu"),
            infiltration_ach=infiltration,
            ventilation_flow_per_area=ventilation_flow,
            natural_ventilation=spec.get("natural_ventilation"),
            dhw_method=(dhw_spec or {}).get("method", "profile"),
            dhw_volume_per_m2_day=float((dhw_spec or {}).get("volume_per_m2_day", 0.0)),
        )
    return schedules
