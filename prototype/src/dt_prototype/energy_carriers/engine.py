"""Solver-independent conversion and explicit building-meter balances.

Every energy input is positive kWh for the stated interval. Solar thermal is
available heat at the DHW generator bus; PV is available AC electricity.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from .config import EnergyConfig, PerformanceCurve, SERVICES, monthly_values

ENERGY_INPUTS = tuple(f"{s}_kWh" for s in SERVICES) + (
    "appliances_kWh", "fans_kWh", "base_auxiliary_kWh", "pv_generation_kWh", "solar_thermal_available_kWh",
)
META = ["time", "period_id", "duration_h", "outdoor_temp_C"]


def validate_inputs(frame, resolution):
    missing = set(META + list(ENERGY_INPUTS)) - set(frame)
    if missing or frame.empty:
        raise ValueError(f"Empty energy input or missing columns: {sorted(missing)}")
    for field in ("duration_h", "outdoor_temp_C", *ENERGY_INPUTS):
        if not pd.api.types.is_numeric_dtype(frame[field]) or pd.api.types.is_bool_dtype(frame[field]):
            raise ValueError(f"{field}: expected numeric quantities, not text or booleans")
    values = frame[["duration_h", "outdoor_temp_C", *ENERGY_INPUTS]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (frame[list(ENERGY_INPUTS)] < 0).any().any():
        raise ValueError("Energy inputs must be finite, nonnegative energies and finite temperatures")
    if (frame.duration_h <= 0).any():
        raise ValueError("Interval durations must be positive")
    times = pd.DatetimeIndex(pd.to_datetime(frame.time))
    if times.hasnans or times.has_duplicates or not times.is_monotonic_increasing or times.tz is not None:
        raise ValueError("Use unique, ordered local-standard-time interval starts without timezone")
    if not np.array_equal(times.to_period("M").astype(str), frame.period_id.astype(str)):
        raise ValueError("period_id does not match interval start")
    if resolution not in ("dynamic", "monthly"):
        raise ValueError("resolution must be dynamic or monthly")
    ends = times + pd.to_timedelta(frame.duration_h.to_numpy(), unit="h")
    if len(times) > 1 and not (ends[:-1] == times[1:]).all():
        raise ValueError("Energy intervals must be contiguous without gaps or overlaps")
    month_ends = (times.to_period("M") + 1).to_timestamp()
    if (ends > month_ends).any():
        raise ValueError("An interval cannot cross a calendar-month boundary")
    if resolution == "monthly":
        if frame.period_id.duplicated().any() or not (times == times.to_period("M").to_timestamp()).all():
            raise ValueError("Monthly rows must start on the first day, one per month")
        if not (ends == month_ends).all():
            raise ValueError("Monthly rows must cover complete calendar months")


def aggregate_inputs(frame):
    """Integrate interval energies and duration-weight temperatures for complete months."""
    validate_inputs(frame, "dynamic")
    rows = []
    for period, g in frame.groupby("period_id", sort=True):
        rows.append(dict(time=str(pd.Period(period).start_time), period_id=period,
                         duration_h=float(g.duration_h.sum()),
                         outdoor_temp_C=float(np.average(g.outdoor_temp_C, weights=g.duration_h)),
                         **g[list(ENERGY_INPUTS)].sum().to_dict()))
    result = pd.DataFrame(rows)
    validate_inputs(result, "monthly")
    return result


def sum_energy(frame, group="period_id"):
    """Aggregate additive outputs only; never sum temperatures, efficiencies or factors."""
    fields = [c for c in frame if c.endswith(("_kWh", "_kgCO2e", "_cost", "_credit"))]
    return frame.groupby(group, sort=True)[fields].sum().reset_index()


@dataclass
class EnergyResult:
    intervals: pd.DataFrame
    services: pd.DataFrame
    metadata: dict

    def monthly(self):
        return sum_energy(self.intervals)

    def annual(self):
        frame = self.intervals.assign(year=self.intervals.period_id.str[:4])
        return sum_energy(frame, "year")

    def check_balances(self):
        frame = self.intervals
        if not np.isfinite(frame.select_dtypes(include="number")).all().all():
            raise ValueError("Nonfinite calculated energy or impact; check magnitudes and efficiencies")
        if not np.isfinite(self.services.select_dtypes(include="number")).all().all():
            raise ValueError("Nonfinite calculated service conversion")
        fields = [c for c in frame if c.endswith("residual_kWh")]
        scale = frame[["gross_electricity_kWh", "pv_generation_kWh", "solar_thermal_available_kWh"]].max(axis=1)
        errors = frame[fields].abs().max(axis=1)
        if (errors > 1e-6 + 1e-9 * scale).any():
            raise AssertionError("Energy or meter balance failed")
        service = self.services
        if (service.conversion_residual_kWh.abs() > 1e-6 + 1e-9 * service.useful_demand_kWh).any():
            raise AssertionError("Service conversion balance failed")
        return {c: float(frame[c].abs().max()) for c in fields} | {
            "service_conversion_residual_kWh": float(service.conversion_residual_kWh.abs().max())
        }


def calculate(inputs: pd.DataFrame, config: EnergyConfig, building_id: str, *, resolution: str) -> EnergyResult:
    """Apply identical technology equations at dynamic or monthly resolution.

    Dynamic PV and solar-thermal use are contemporaneous, without storage.
    Monthly use follows explicit supplied factors. Export credits are separate
    from import impacts and can never offset another carrier's physical demand.
    """
    x = inputs.reset_index(drop=True).copy()
    validate_inputs(x, resolution)
    b = config.building(building_id)
    months = pd.to_datetime(x.time).dt.month.to_numpy() - 1
    out = x[META + list(ENERGY_INPUTS)].copy()
    services, carrier_energy = [], {c: np.zeros(len(x)) for c in config.data["carriers"]}
    auxiliary = np.zeros(len(x))
    solar_used = np.zeros(len(x))
    for service in SERVICES:
        tech_id = b["services"][service]
        tech = config.data["technologies"][tech_id]
        perf, clipped = PerformanceCurve.from_dict(tech["performance"]).evaluate(x.outdoor_temp_C)
        chain = np.prod([tech[k] for k in ("distribution_efficiency", "emission_efficiency", "regulation_efficiency")])
        useful = x[f"{service}_kWh"].to_numpy()
        generator_required = useful / chain
        solar = np.zeros(len(x))
        if service == "dhw":
            utilisation = (np.ones(len(x)) if resolution == "dynamic" else
                           monthly_values(b["solar_thermal"]["monthly_utilisation"], "ST factor")[months])
            solar = np.minimum(generator_required, x.solar_thermal_available_kWh.to_numpy()) * utilisation
            solar_used = solar
        generated = generator_required - solar
        delivered = generated / perf
        aux = generated * tech["auxiliary_kWh_per_kWh_generated"]
        auxiliary += aux
        carrier_energy[tech["carrier"]] += delivered
        out[f"{service}_delivered_kWh"] = delivered
        out[f"{service}_auxiliary_kWh"] = aux
        records = x[META].copy()
        records["service"], records["technology"], records["carrier"] = service, tech_id, tech["carrier"]
        records["useful_demand_kWh"] = useful
        records["performance"] = perf
        records["chain_efficiency"] = chain
        records["temperature_clipped"] = clipped
        records["generator_required_kWh"] = generator_required
        records["solar_thermal_used_kWh"] = solar
        records["generator_output_kWh"] = generated
        records["delivered_kWh"] = delivered
        records["auxiliary_kWh"] = aux
        records["downstream_losses_kWh"] = generator_required - useful
        records["conversion_residual_kWh"] = useful - (delivered * perf + solar) * chain
        services.append(records)
    out["system_auxiliary_kWh"] = auxiliary
    out["solar_thermal_used_kWh"] = solar_used
    out["solar_thermal_curtailed_kWh"] = x.solar_thermal_available_kWh - solar_used
    out["solar_thermal_residual_kWh"] = x.solar_thermal_available_kWh - solar_used - out.solar_thermal_curtailed_kWh
    carrier_energy["electricity"] += auxiliary + x.appliances_kWh + x.fans_kWh + x.base_auxiliary_kWh
    load = np.asarray(carrier_energy["electricity"])
    pv = x.pv_generation_kWh.to_numpy()
    overlap = np.minimum(load, pv)
    if resolution == "dynamic":
        self_used = overlap
        requested = overlap
    else:
        factor = monthly_values(b["pv"]["monthly_factor"], "PV factor")[months]
        requested = factor * (overlap if b["pv"]["factor_basis"] == "overlap" else pv)
        self_used = np.minimum(requested, overlap)
        out["pv_input_factor"] = factor
    out["pv_factor_capped"] = requested > overlap + 1e-9
    out["gross_electricity_kWh"] = load
    out["pv_self_consumed_kWh"] = self_used
    out["grid_import_kWh"] = load - self_used
    out["grid_export_kWh"] = pv - self_used
    out["electric_load_residual_kWh"] = load - out.grid_import_kWh - self_used
    out["pv_residual_kWh"] = pv - out.grid_export_kWh - self_used
    out["meter_residual_kWh"] = out.grid_import_kWh + pv - load - out.grid_export_kWh
    impacts = {name: np.zeros(len(x)) for name in (
        "import_primary_nonrenewable_kWh", "import_primary_renewable_kWh", "import_carbon_kgCO2e",
        "import_energy_cost", "export_primary_nonrenewable_kWh", "export_primary_renewable_kWh",
        "export_carbon_kgCO2e", "export_energy_credit",
    )}
    for carrier, gross in carrier_energy.items():
        imported = out.grid_import_kWh.to_numpy() if carrier == "electricity" else np.asarray(gross)
        exported = out.grid_export_kWh.to_numpy() if carrier == "electricity" else np.zeros(len(x))
        out[f"gross_{carrier}_kWh"] = gross
        out[f"imported_{carrier}_kWh"] = imported
        factors = config.data["carriers"][carrier]
        for output, field, energy in (
            ("import_primary_nonrenewable_kWh", "primary_nonrenewable", imported),
            ("import_primary_renewable_kWh", "primary_renewable", imported),
            ("import_carbon_kgCO2e", "carbon_kgCO2e_per_kWh", imported),
            ("import_energy_cost", "import_price_per_kWh", imported),
            ("export_primary_nonrenewable_kWh", "export_primary_nonrenewable", exported),
            ("export_primary_renewable_kWh", "export_primary_renewable", exported),
            ("export_carbon_kgCO2e", "export_carbon_kgCO2e_per_kWh", exported),
            ("export_energy_credit", "export_price_per_kWh", exported),
        ):
            value = energy * monthly_values(factors[field], field, low=None if "price" in field else 0)[months]
            out[f"{carrier}_{output}"] = value
            impacts[output] += value
    for name, value in impacts.items():
        out[name] = value
    out["import_primary_total_kWh"] = out.import_primary_nonrenewable_kWh + out.import_primary_renewable_kWh
    out["export_primary_total_kWh"] = out.export_primary_nonrenewable_kWh + out.export_primary_renewable_kWh
    out["net_primary_total_kWh"] = out.import_primary_total_kWh - out.export_primary_total_kWh
    out["net_carbon_kgCO2e"] = out.import_carbon_kgCO2e - out.export_carbon_kgCO2e
    out["net_energy_cost"] = out.import_energy_cost - out.export_energy_credit
    out["total_imported_carrier_kWh"] = sum(out[f"imported_{c}_kWh"] for c in carrier_energy)
    out["carrier_allocation_residual_kWh"] = sum(carrier_energy.values()) - (
        sum(out[f"{s}_delivered_kWh"] for s in SERVICES) + auxiliary + x.appliances_kWh + x.fans_kWh + x.base_auxiliary_kWh
    )
    result = EnergyResult(out, pd.concat(services, ignore_index=True), dict(
        building_id=str(building_id), resolution=resolution, config_sha256=config.sha256,
        scenario_id=config.data["scenario_id"], currency=config.data["currency"],
        pv_matching="contemporaneous_no_storage" if resolution == "dynamic" else f"monthly_factor_{b['pv']['factor_basis']}",
        solar_thermal_boundary="DHW_generator_bus", battery="none",
    ))
    result.metadata["balance_checks"] = result.check_balances()
    return result
