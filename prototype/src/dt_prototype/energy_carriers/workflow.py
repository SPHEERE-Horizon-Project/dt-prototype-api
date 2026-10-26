"""Reproducible four-solver system/carrier workflow and inspectable exports."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd

from dt_prototype.common.project import ProjectInputs
from dt_prototype.common.output_paths import output_component
from dt_prototype.monthly_ss_vbdd import VBOptions
from . import __version__
from .config import EnergyConfig, SERVICES
from .engine import calculate, aggregate_inputs, sum_energy
from .adapters import solve_cases, energy_inputs, zone_allocations, THERMAL
from .preprocessing import prepare_common
from .templates import linear_sensitivity


def _stamp(frame, metadata):
    return frame.assign(**metadata)


def _service_monthly(result):
    fields = [c for c in result.services if c.endswith("_kWh")]
    group = result.services.groupby(["period_id", "service", "technology", "carrier"], as_index=False)
    frame = group[fields].sum()
    frame["effective_performance"] = np.divide(frame.generator_output_kWh, frame.delivered_kWh,
        out=np.full(len(frame), np.nan), where=frame.delivered_kWh.to_numpy() > 0)
    return frame


def run_project(project_path, energy_path, output, *, engine="all", model=None, zone_mode="both",
                vb_solar="direct", vb_options=None, progress=print):
    out = Path(output).resolve()
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite {out}")
    project = ProjectInputs.load(project_path)
    energy = EnergyConfig.load(energy_path)
    district = project.preprocess()
    for building in district.buildings:
        energy.building(building.geometry.building_id)
    dynamic = dict(project.configuration["dynamic"])
    if model:
        dynamic["model"] = model
    if engine in ("all", "Dynamic_RC") and (dynamic.get("plants", False) or dynamic.get("latent", True) or dynamic.get("pv_battery", False)):
        raise ValueError("Shared sensible boundary requires dynamic plants=false, latent=false, pv_battery=false in the project configuration")
    if engine in ("all", "Monthly_SS_simplified") and project.configuration["simplified"]["comparison_mode"] != "seasonal_ahu":
        raise ValueError("Shared comparison requires simplified.comparison_mode=seasonal_ahu")
    out.mkdir(parents=True)
    (out / "energy_config_resolved.json").write_text(json.dumps(energy.data, indent=2), encoding="utf-8")
    manifest = dict(status="running", version=__version__, timestamp_utc=datetime.now(timezone.utc).isoformat(),
        python=platform.python_version(), dependencies={n: importlib.metadata.version(n) for n in ("numpy", "pandas", "matplotlib")},
        input_hashes=project.hashes(), energy_file_sha256=hashlib.sha256(Path(energy_path).read_bytes()).hexdigest(),
        energy_config_sha256=energy.sha256, configuration=project.configuration,
        thermal_boundary="useful_sensible_zone_plus_separate_net_sensible_AHU_ideal_emitters",
        excluded_services=["latent conditioning", "gross AHU cooling/reheat beyond net sensible coil", "storage dynamics", "unspecified auxiliaries"],
        command=dict(engine=engine, model=model, zone_mode=zone_mode, vb_solar=vb_solar,
                     vb_options=asdict(vb_options or VBOptions())),
        cases=[], buildings=[],
        code_hashes={str(p.relative_to(Path(__file__).parents[1])): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in Path(__file__).parents[1].rglob("*.py")})
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    monthly, annual, service, zone_service, thermal_rows, sensitivities, aggregations, pv_sensitivities = [], [], [], [], [], [], [], []
    zone_ancillary = []
    linear = linear_sensitivity(energy)
    (out / "linear_sensitivity_config.json").write_text(json.dumps(linear.data, indent=2), encoding="utf-8")
    try:
        for building in district.buildings:
            bid = str(building.geometry.building_id)
            common = prepare_common(building, district.weather, energy)
            manifest["buildings"].append(common.metadata | {"building_name": building.name})
            building_dir = out / "cases" / output_component(bid)
            building_dir.mkdir(parents=True)
            common.monthly().to_csv(building_dir / "common_monthly_inputs.csv", index=False)
            for label, inputs in common.zones.items():
                ancillary = aggregate_inputs(inputs)[["period_id", "dhw_kWh", "appliances_kWh", "fans_kWh"]]
                zone_ancillary.append(ancillary.assign(building_id=bid, building_name=building.name, zone_id=label))
            specs = []
            if engine == "all":
                specs.extend([("Dynamic_RC", {**dynamic, "model": rc}, "direct", VBOptions()) for rc in ("5R1C", "7R2C")])
                specs.extend([(e, dynamic, "direct", VBOptions()) for e in ("Monthly_SS", "Monthly_SS_simplified", "Monthly_SS_VBDD")])
                specs += [("Monthly_SS_VBDD", dynamic, "temperature_linear", VBOptions()), ("Monthly_SS_VBDD", dynamic, "direct", VBOptions("fixed"))]
            else:
                specs = [(engine, dynamic, vb_solar, vb_options or VBOptions())]
            for family, options, solar, vbopt in specs:
                tag = f"{family}_{options['model'] if family == 'Dynamic_RC' else solar + '_' + vbopt.utilisation}"
                progress(f"{building.name}: {tag}", flush=True)
                cases = solve_cases(building, district.weather, project.configuration["operating"], family,
                    building_dir / output_component(tag), dynamic_options=options, zone_mode=zone_mode,
                    vb_solar=solar, vb_options=vbopt)
                for case in cases:
                    metadata = dict(building_id=bid, building_name=building.name, model=case.name,
                                    representation=case.representation, resolution=case.resolution)
                    directory = building_dir / output_component(case.name)
                    directory.mkdir(exist_ok=True)
                    inputs = energy_inputs(case, common)
                    result = calculate(inputs, energy, bid, resolution=case.resolution)
                    result.metadata.update(metadata)
                    result.metadata["temperature_clipped_service_intervals"] = int(result.services.temperature_clipped.sum())
                    result.metadata["pv_factor_capped_intervals"] = int(result.intervals.pv_factor_capped.sum())
                    manifest["cases"].append(result.metadata)
                    if case.resolution == "dynamic":
                        inputs.to_csv(directory / "energy_inputs.csv.gz", index=False)
                        result.intervals.to_csv(directory / "energy_intervals.csv.gz", index=False)
                        result.services.to_csv(directory / "service_intervals.csv.gz", index=False)
                    else:
                        inputs.to_csv(directory / "energy_inputs.csv", index=False)
                        result.intervals.to_csv(directory / "energy_intervals.csv", index=False)
                        result.services.to_csv(directory / "service_intervals.csv", index=False)
                    result.monthly().to_csv(directory / "energy_monthly.csv", index=False)
                    (directory / "metadata.json").write_text(json.dumps(result.metadata, indent=2), encoding="utf-8")
                    monthly.append(_stamp(result.monthly(), metadata))
                    annual.append(_stamp(result.annual(), metadata))
                    service.append(_stamp(_service_monthly(result), metadata))
                    zone_service.append(_stamp(zone_allocations(case, common, result), metadata))
                    for label, f in case.zones.items():
                        thermal_rows.append(_stamp(f.groupby("period_id", as_index=False)[THERMAL].sum(), metadata | {"zone_id": label}))
                    # Curves sensitivity uses the same thermal inputs; changes in thermal demand cannot confound it.
                    varied = calculate(inputs, linear, bid, resolution=case.resolution)
                    sensitivities.append(_stamp(varied.annual(), metadata | {"scenario_id": linear.data["scenario_id"]}))
                    if case.resolution == "dynamic":
                        no_solar = inputs.copy()
                        no_solar[["pv_generation_kWh", "solar_thermal_available_kWh"]] = 0.0
                        for scenario in (energy, linear):
                            fine = calculate(no_solar, scenario, bid, resolution="dynamic")
                            coarse = calculate(aggregate_inputs(no_solar), scenario, bid, resolution="monthly")
                            a = fine.monthly().set_index("period_id")
                            c = coarse.monthly().set_index("period_id")
                            for quantity in [f"{s}_delivered_kWh" for s in SERVICES]:
                                for period in a.index:
                                    aggregations.append(metadata | dict(scenario_id=scenario.data["scenario_id"],
                                        period_id=period, quantity=quantity, dynamic_kWh=float(a.loc[period, quantity]),
                                        monthly_kWh=float(c.loc[period, quantity]), difference_kWh=float(c.loc[period, quantity]-a.loc[period, quantity])))
                    elif energy.building(bid)["pv"]["roof_coverage"] > 0:
                        for f in (0.0, .65, 1.0):
                            # Sensitivity is explicitly on the overlap basis, independent of the baseline convention.
                            gross, pv = result.intervals.gross_electricity_kWh, result.intervals.pv_generation_kWh
                            used = np.minimum(gross, pv) * f
                            pv_sensitivities.append(metadata | dict(overlap_factor=f, pv_self_consumed_kWh=float(used.sum()),
                                grid_import_kWh=float((gross-used).sum()), grid_export_kWh=float((pv-used).sum())))
        frames = {"energy_monthly": monthly, "energy_annual": annual, "service_monthly": service,
                  "zone_service_monthly": zone_service, "thermal_zone_monthly": thermal_rows,
                  "linear_sensitivity_annual": sensitivities}
        for name, records in frames.items():
            pd.concat(records, ignore_index=True).to_csv(out / f"{name}.csv", index=False)
        # Annual service efficiencies are output/input ratios, never sums or means of monthly COPs.
        for name, records, extra in (
            ("service", service, ["service", "technology", "carrier"]),
            ("zone_service", zone_service, ["zone_id", "service", "technology", "carrier"]),
            ("thermal_zone", thermal_rows, ["zone_id"]),
        ):
            frame = pd.concat(records, ignore_index=True)
            frame["year"] = frame.period_id.str[:4]
            group = ["building_id", "building_name", "model", "representation", "resolution", "year", *extra]
            summed = frame.groupby(group, as_index=False)[[c for c in frame if c.endswith("_kWh")]].sum()
            if name == "service":
                summed["effective_performance"] = np.divide(summed.generator_output_kWh, summed.delivered_kWh,
                    out=np.full(len(summed), np.nan), where=summed.delivered_kWh.to_numpy() > 0)
            summed.to_csv(out / f"{name}_annual.csv", index=False)
        ancillary = pd.concat(zone_ancillary, ignore_index=True)
        ancillary.to_csv(out / "zone_ancillary_monthly.csv", index=False)
        ancillary.assign(year=ancillary.period_id.str[:4]).groupby(
            ["building_id", "building_name", "zone_id", "year"], as_index=False
        )[["dhw_kWh", "appliances_kWh", "fans_kWh"]].sum().to_csv(out / "zone_ancillary_annual.csv", index=False)
        pd.DataFrame(aggregations).to_csv(out / "dynamic_monthly_aggregation.csv", index=False)
        pd.DataFrame(pv_sensitivities).to_csv(out / "pv_factor_sensitivity.csv", index=False)
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        from .reporting import build_report
        manifest["validation"] = build_report(out, project.config_path.parent.parent / "comparison_report.md")
        manifest["status"] = "complete"
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out
