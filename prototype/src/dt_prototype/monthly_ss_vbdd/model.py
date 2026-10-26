"""Explicit power balance and variable-base degree days. No spreadsheet runtime.

All average powers use the complete calendar month, including inactive hours.
Availability is already represented in H and offsets and MUST NOT be applied
again to gains. The AHU boundary is separate and positive in both modes.
"""
from dataclasses import asdict, dataclass
import math
import pandas as pd


@dataclass(frozen=True)
class MonthlyInput:
    case_id: str
    building_id: str
    building_name: str
    zone_id: str
    representation: str
    period_id: str
    days: int
    outdoor_temp_C: float
    heating_setpoint_C: float
    cooling_setpoint_C: float
    H_heating_W_K: float
    H_cooling_W_K: float
    heating_offset_W: float
    cooling_offset_W: float
    internal_gain_W: float
    solar_gain_W: float
    capacity_J_K: float
    H_time_constant_W_K: float
    heating_enabled: bool
    cooling_enabled: bool
    ahu_heating_kWh: float = 0.0
    ahu_cooling_kWh: float = 0.0

    def __post_init__(self):
        for name, value in asdict(self).items():
            if isinstance(value, (float, int)) and not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        period = pd.Period(self.period_id, freq="M")
        if type(self.days) is not int or self.days != period.days_in_month:
            raise ValueError("days must equal the actual calendar month's length")
        for name in ("H_heating_W_K", "H_cooling_W_K", "capacity_J_K",
                     "ahu_heating_kWh", "ahu_cooling_kWh", "internal_gain_W"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be nonnegative")
        if self.H_time_constant_W_K <= 0:
            raise ValueError("H_time_constant_W_K must be positive")
        for name in ("heating_enabled", "cooling_enabled"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean")
        if not self.case_id or not self.building_id:
            raise ValueError("case and building identifiers are required")
        if self.heating_enabled and self.H_heating_W_K <= 0:
            raise ValueError("enabled heating requires a positive heat-transfer coefficient")
        if self.cooling_enabled and self.H_cooling_W_K <= 0:
            raise ValueError("enabled cooling requires a positive heat-transfer coefficient")


@dataclass(frozen=True)
class VBOptions:
    utilisation: str = "monthly_balance"
    eta_heating: float = 1.0
    eta_cooling: float = 1.0
    attenuation_heating: float = 0.0
    attenuation_cooling: float = 0.0

    def __post_init__(self):
        if self.utilisation not in {"monthly_balance", "fixed"}:
            raise ValueError("utilisation must be monthly_balance or fixed")
        for name in ("eta_heating", "eta_cooling", "attenuation_heating", "attenuation_cooling"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be between zero and one")
        if self.eta_cooling == 0 or max(self.attenuation_heating, self.attenuation_cooling) == 1:
            raise ValueError("positive effective slopes are required for finite balance points")


def utilisation_factor(gamma: float, a: float, *, cooling: bool = False) -> float:
    """Stable ISO-form limit at gamma=1; reciprocal prevents power overflow."""
    x = 1.0 / gamma if cooling else gamma
    if abs(x - 1.0) <= 1e-8:
        return a / (a + 1.0)
    if x > 1:
        return (1 - x ** (-a)) / (x - x ** (-a))
    return (1 - x ** a) / (1 - x ** (a + 1))


def calculate_month(row: MonthlyInput, options: VBOptions = VBOptions()) -> dict:
    hours = row.days * 24.0
    kh = row.H_heating_W_K * (1 - options.attenuation_heating)
    kc = row.H_cooling_W_K * (1 - options.attenuation_cooling)
    oh = row.heating_offset_W * (1 - options.attenuation_heating)
    oc = row.cooling_offset_W * (1 - options.attenuation_cooling)
    gains = row.internal_gain_W + row.solar_gain_W
    lh = kh * (row.heating_setpoint_C - row.outdoor_temp_C) + oh
    lc = kc * (row.cooling_setpoint_C - row.outdoor_temp_C) + oc
    a = 1 + row.capacity_J_K / (3600 * row.H_time_constant_W_K * 15)
    # Match the retained QSS lower bound of 1e-5 J, converted to average W.
    floor_W = 1e-5 / (hours * 3600)
    gh = min(1e5, max(1e-9, gains / max(floor_W, lh)))
    gc = min(1e15, max(1e-9, gains / max(floor_W, lc)))
    eh = utilisation_factor(gh, a) if options.utilisation == "monthly_balance" else options.eta_heating
    ec = utilisation_factor(gc, a, cooling=True) if options.utilisation == "monthly_balance" else options.eta_cooling
    # This bounded loss convention is explicit; offsets preserve algebra at L<0.
    if options.utilisation == "monthly_balance":
        oh += max(floor_W, lh) - lh
        oc += max(floor_W, lc) - lc
    bh = row.heating_setpoint_C + (oh - eh * gains) / kh if kh > 0 else None
    bc = row.cooling_setpoint_C + (oc - gains / ec) / kc if kc > 0 else None
    ddh = max(0.0, bh - row.outdoor_temp_C) * row.days if row.heating_enabled else 0.0
    ddc = max(0.0, row.outdoor_temp_C - bc) * row.days if row.cooling_enabled else 0.0
    qh = kh * ddh * 24 / 1000
    qc = ec * kc * ddc * 24 / 1000
    return dict(**asdict(row), utilisation=options.utilisation, hours=hours,
                gains_W=gains, loss_heating_W=lh, loss_cooling_W=lc, a=a,
                gamma_heating=gh, gamma_cooling=gc, eta_heating=eh, eta_cooling=ec,
                effective_H_heating_W_K=kh, effective_H_cooling_W_K=kc,
                balance_heating_C=bh, balance_cooling_C=bc,
                heating_degree_days_K_day=ddh, cooling_degree_days_K_day=ddc,
                zone_heating_kWh=qh, zone_cooling_kWh=qc,
                heating_kWh=qh + row.ahu_heating_kWh,
                cooling_kWh=qc + row.ahu_cooling_kWh,
                average_power_kW=(qh + qc + row.ahu_heating_kWh + row.ahu_cooling_kWh)/hours)


def simulate(rows, options: VBOptions = VBOptions()) -> pd.DataFrame:
    rows = list(rows)
    keys = [(r.case_id, r.period_id) for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate case/month input")
    if not rows:
        raise ValueError("no monthly inputs")
    return pd.DataFrame(calculate_month(r, options) for r in rows)
