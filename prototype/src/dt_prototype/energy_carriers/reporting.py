"""Numeric, graphical and Markdown validation evidence for shared energy runs."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from dt_prototype.common.output_paths import output_component

ORDER = ["Dynamic_RC 5R1C", "Dynamic_RC 7R2C", "Monthly_SS", "Monthly_SS_simplified zone sum", "Monthly_SS_simplified collapsed",
         "Monthly_SS_VBDD monthly zone sum", "Monthly_SS_VBDD monthly collapsed", "Monthly_SS_VBDD linear zone sum", "Monthly_SS_VBDD linear collapsed",
         "Monthly_SS_VBDD fixed zone sum", "Monthly_SS_VBDD fixed collapsed"]


def table(frame):
    f = frame.copy()
    for c in f:
        if pd.api.types.is_numeric_dtype(f[c]):
            f[c] = f[c].map(lambda x: "n/a" if pd.isna(x) else f"{x:,.3f}")
    return "\n".join(["| " + " | ".join(f.columns) + " |", "| " + " | ".join(["---"]*len(f.columns)) + " |"] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in f.itertuples(index=False, name=None)])


def _ordered(frame):
    return frame.assign(_order=frame.model.map({v: i for i, v in enumerate(ORDER)})).sort_values("_order").drop(columns="_order")


def _optional_csv(path):
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _historical(path, annual):
    if not path.is_file():
        return pd.DataFrame()
    text = path.read_text(encoding="utf-8")
    rows = []
    for section, use in ((3,"heating"), (4,"cooling")):
        marker = f"## {section}. Annual "
        if marker not in text:
            continue
        block = text.split(marker, 1)[1].split("Candidate minus", 1)[0]
        for line in block.splitlines():
            if not line.startswith("| Test building "):
                continue
            parts = [v.strip().replace(",", "") for v in line.strip("|").split("|")]
            for model, value in zip(["Dynamic_RC 5R1C", "Dynamic_RC 7R2C", "Monthly_SS", "Monthly_SS_simplified collapsed", "Monthly_SS_simplified zone sum"], parts[1:]):
                selected = annual[(annual.building_name == parts[0]) & (annual.model == model)]
                if selected.empty and model == "Monthly_SS_simplified collapsed":
                    selected = annual[(annual.building_name == parts[0]) & (annual.model == "Monthly_SS_simplified zone sum") &
                                      (annual.representation == "native_single_zone")]
                if len(selected) != 1:
                    continue
                fresh = float(selected.iloc[0][f"zone_{use}_kWh"] + selected.iloc[0][f"ahu_{use}_kWh"]) / 1000
                historical = float(value)
                rows.append(dict(building_name=parts[0], model=model, quantity=use, historical_MWh=historical,
                    fresh_MWh=fresh, difference_MWh=fresh-historical, within_display_rounding=abs(fresh-historical) <= .00501))
    return pd.DataFrame(rows)


def build_report(output, historical_path):
    out = Path(output)
    monthly = pd.read_csv(out / "energy_monthly.csv", dtype={"building_id": str})
    annual = pd.read_csv(out / "energy_annual.csv", dtype={"building_id": str})
    zone = pd.read_csv(out / "zone_service_monthly.csv", dtype={"building_id": str})
    services = pd.read_csv(out / "service_monthly.csv", dtype={"building_id": str})
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    config = json.loads((out / "energy_config_resolved.json").read_text(encoding="utf-8"))
    groups = ["building_id", "model", "representation"]
    if monthly.duplicated(groups + ["period_id"]).any() or not monthly.groupby(groups).size().eq(12).all():
        raise AssertionError("Duplicate/missing building-model months")
    physical = [c for c in monthly if c.endswith("_kWh") and not any(t in c for t in ("residual", "primary"))]
    if not np.isfinite(monthly[physical]).all().all() or (monthly[physical] < -1e-8).any().any():
        raise AssertionError("Invalid physical energy outputs")
    # Compare zone allocations to the service totals at the shared building systems.
    zk = groups + ["period_id", "service"]
    fields = ["useful_demand_kWh", "delivered_kWh", "auxiliary_kWh", "solar_thermal_used_kWh", "generator_output_kWh"]
    zz = zone.groupby(zk)[fields].sum()
    ss = services.set_index(zk)[fields].sort_index()
    zz = zz.reindex(ss.index)
    if zz.isna().any().any():
        raise AssertionError("Missing zone allocation")
    zd = (zz-ss).abs()
    if (zd > 1e-6 + 1e-9*ss.abs()).any().any():
        raise AssertionError("Zone-to-building service allocation does not close")
    checks = {"cases": len(annual), "building_model_months": len(monthly), "buildings": annual.building_id.nunique(),
              "zone_allocation_max_abs_kWh": float(zd.max().max()),
              "maximum_interval_balance_residual_kWh": max(v for c in manifest["cases"] for v in c["balance_checks"].values())}
    # Common ancillary energy and renewable production are identical across solvers.
    common_fields = ["dhw_kWh", "appliances_kWh", "fans_kWh", "base_auxiliary_kWh", "pv_generation_kWh", "solar_thermal_available_kWh"]
    spreads = monthly.groupby(["building_id", "period_id"])[common_fields].agg(lambda x: x.max()-x.min())
    checks["common_inputs_max_spread_kWh"] = float(spreads.max().max())
    if checks["common_inputs_max_spread_kWh"] > 1e-6:
        raise AssertionError("Common loads or renewable production changed between solvers")
    differences = []
    quantities = ["grid_import_kWh", "grid_export_kWh", "total_imported_carrier_kWh", "import_primary_total_kWh",
                  "net_carbon_kgCO2e", "net_energy_cost", "zone_heating_delivered_kWh", "ahu_heating_delivered_kWh",
                  "zone_cooling_delivered_kWh", "ahu_cooling_delivered_kWh"]
    for (bid, model), f in monthly.groupby(["building_id", "model"]):
        reference = monthly[(monthly.building_id == bid) & (monthly.model == "Monthly_SS")]
        if reference.empty:
            continue
        f, reference = f.set_index("period_id").sort_index(), reference.set_index("period_id").sort_index()
        for q in quantities:
            delta = f[q] - reference[q]
            ref = float(reference[q].sum())
            differences.append(dict(building_id=bid, building_name=f.building_name.iloc[0], model=model,
                reference_model="Monthly_SS", quantity=q, reference_annual=ref, candidate_annual=float(f[q].sum()),
                annual_difference=float(delta.sum()), annual_difference_pct=100*float(delta.sum())/ref if abs(ref)>1e-9 else np.nan,
                monthly_RMSE=float(np.sqrt(np.mean(delta**2))), max_abs_monthly_difference=float(delta.abs().max()),
                largest_difference_month=delta.abs().idxmax(), classification="MODEL_COMPARISON_NOT_EQUIVALENCE"))
    pd.DataFrame(differences).to_csv(out / "differences_vs_qss.csv", index=False)
    matching = monthly[["building_id", "building_name", "model", "period_id", "resolution",
                        "gross_electricity_kWh", "pv_generation_kWh", "pv_self_consumed_kWh",
                        "grid_import_kWh", "grid_export_kWh"]].copy()
    for field, denominator in (
        ("achieved_overlap_factor", np.minimum(matching.gross_electricity_kWh, matching.pv_generation_kWh)),
        ("PV_self_consumed_fraction", matching.pv_generation_kWh),
        ("electricity_self_sufficiency", matching.gross_electricity_kWh),
    ):
        matching[field] = np.divide(matching.pv_self_consumed_kWh, denominator,
            out=np.full(len(matching), np.nan), where=np.asarray(denominator)>0)
    matching.to_csv(out / "pv_matching_diagnostics.csv", index=False)
    historical = _historical(Path(historical_path), annual)
    historical.to_csv(out / "historical_thermal_reconciliation.csv", index=False)
    checks["historical_values_compared"] = len(historical)
    if len(historical):
        checks["historical_within_rounding"] = int(historical.within_display_rounding.sum())
        checks["historical_max_abs_difference_MWh"] = float(historical.difference_MWh.abs().max())
        checks["historical_source_sha256"] = hashlib.sha256(Path(historical_path).read_bytes()).hexdigest()
        # Different user projects may intentionally change inputs, so report rather than hide discrepancies.
    aggregation = _optional_csv(out / "dynamic_monthly_aggregation.csv")
    if len(aggregation):
        constant = aggregation[aggregation.scenario_id == config["scenario_id"]]
        # Baseline may be user-defined nonlinear curves: commutativity is only asserted for constant curves.
        is_constant = all(len(t["performance"]["coefficients"]) == 1 for t in config["technologies"].values())
        checks["baseline_all_curves_constant"] = is_constant
        checks["baseline_aggregation_max_abs_kWh"] = float(constant.difference_kWh.abs().max())
        if is_constant and (constant.difference_kWh.abs() > 1e-6 + 1e-9*constant.dynamic_kWh.abs()).any():
            raise AssertionError("Constant conversion failed aggregation invariance")
    # QSS and monthly-balance Monthly_SS_VBDD are algebraically equivalent on the native zone sums.
    qss = monthly[monthly.model == "Monthly_SS"].set_index(["building_id", "period_id"])
    vb = monthly[monthly.model == "Monthly_SS_VBDD monthly zone sum"].set_index(["building_id", "period_id"])
    if len(qss) and len(vb):
        compare = [c for c in physical if "residual" not in c]
        vd = (vb[compare] - qss[compare]).abs()
        checks["vb_monthly_vs_qss_max_abs_kWh"] = float(vd.max().max())
        if (vd > 1e-6 + 1e-9*qss[compare].abs()).any().any():
            raise AssertionError("Native Monthly_SS_VBDD monthly and Monthly_SS shared energy did not agree")
    _figures(out, monthly, annual)
    zone_pages = _zone_appendices(out)
    docs = ["# Shared systems, carriers and renewable energy: comparison report", "",
        "Fresh calculations for the supplied building cases. All four thermal solver families use the same downstream system equations, ancillary schedules, renewable production and carrier-factor configuration. Results are engineering model comparisons and software verification, not validation against metered consumption or the future ISO spreadsheet.", "",
        "## Calculation boundary and assumptions", "",
        "- Thermal loads: sensible zone plus separate net sensible AHU heating/cooling, positive kWh; ideal emitter settings preserve the earlier thermal benchmark. Latent conditioning and extra gross AHU reheat/cooling are outside this comparison.",
        "- Additional loads: actual shared DHW, appliance/lighting and AHU fan schedules. Monthly_SS_simplified mapped thermal gains are never treated as appliance consumption.",
        "- Systems: the resolved JSON records all generation curves, distribution/emission/regulation efficiencies and explicit auxiliary coefficients. AHU coils use generation/distribution only. DHW solar heat is allocated at the generator bus before fuel/electricity conversion.",
        "- Dynamic: conversion and no-storage PV/ST matching at each weather/thermal time step. Monthly: conversion at monthly mean outdoor temperature and the explicitly supplied PV/ST factors. Dynamic and monthly grid exchange therefore have intentionally different matching assumptions.",
        "- The example uses supplied constant system efficiencies. PR, collector parameters, monthly matching factors, primary/carbon factors and prices are labelled illustrative inputs. They are not inferred national values or validated ISO factors. Costs exclude standing charges, taxes and demand tariffs.",
        "- Renewable/meter balances operate once per building. Zone service outputs allocate the common plant energy by each zone's useful demand. They are not separate PV meters. Collapsed cases remain separate alternative building representations.", "",
        "See [resolved configuration](energy_config_resolved.json), [monthly outputs](energy_monthly.csv), [annual outputs](energy_annual.csv), [annual service outputs](service_annual.csv), [annual zone service allocations](zone_service_annual.csv), and [manifest](manifest.json).", "",
        "## Verification", "", table(pd.DataFrame([{"Check": k, "Value": v} for k,v in checks.items()])), "",
        "The balance tolerance is 1e-6 kWh + 1e-9 times the relevant energy magnitude. Cross-model differences have no arbitrary pass threshold. The historical reconciliation checks only useful heating/cooling against comparison_report.md's rounded figures; the old report does not validate the new delivered-energy results.", "",
        "## Systems and renewable sizing", ""]
    sizing = []
    for b in manifest["buildings"]:
        cfg = config["buildings"][b["building_id"]]
        h = config["technologies"][cfg["services"]["zone_heating"]]
        c = config["technologies"][cfg["services"]["zone_cooling"]]
        sizing.append({"Building": b["building_name"], "Heating": h["description"], "Cooling": c["description"],
                       "PV kWp": b["pv_capacity_kWp"], "ST m²": b["solar_thermal_area_m2"]})
    docs += [table(pd.DataFrame(sizing)), "", "## Building-by-building annual results", "",
             "Energy columns below are MWh/year. Imported carrier energy is final energy at the building boundary. Primary energy and carbon use import factors; export credits are reported separately in the CSVs. No fuel is offset by exported PV.", ""]
    for bid, g in annual.groupby("building_id", sort=False):
        g = _ordered(g)
        name = g.building_name.iloc[0]
        cols = {"model":"Model", "grid_import_kWh":"Electricity imported", "imported_natural_gas_kWh":"Gas imported",
                "pv_self_consumed_kWh":"PV self-use", "grid_export_kWh":"PV exported", "solar_thermal_used_kWh":"ST used"}
        cols = {k:v for k,v in cols.items() if k in g}
        values = g[list(cols)].rename(columns=cols)
        for c in values.columns[1:]: values[c] /= 1000
        docs += [f"### {name}", "", table(values), ""]
        impacts = g[["model", "import_primary_total_kWh", "import_carbon_kgCO2e", "net_energy_cost"]].copy()
        impacts.iloc[:,1:] = impacts.iloc[:,1:]/1000
        impacts.columns = ["Model", "Imported primary MWh", "Import carbon tCO2e", f"Net energy cost, thousand {config['currency']}"]
        docs += [table(impacts), "", f"![Monthly carrier and renewable results](figures/{output_component(bid)}_monthly.png)", ""]
        docs += [f"[Individual-zone and collapsed-case service tables]({zone_pages[str(bid)]}) show useful and delivered heating/cooling separately, DHW conversion, solar heat allocation and common zone electrical loads.", ""]
    docs += ["## Differences and temporal approximation", "",
        "[differences_vs_qss.csv](differences_vs_qss.csv) contains annual signed/percentage differences, monthly RMSE and the largest differing month for every model/building and selected carrier/impact quantities. A collapsed case is compared with the QSS independent-zone sum and is a distinct approximation.", "",
        "[dynamic_monthly_aggregation.csv](dynamic_monthly_aggregation.csv) holds an isolated check: identical Dynamic_RC thermal loads are converted at native time steps and again after monthly aggregation, with PV/ST removed. Constant efficiency must commute with aggregation. The additional sensitivity uses supplied historical Model 3 linear heat-pump/chiller curves; these curves are not calibrated to these buildings. With variable performance, sum(Q/COP(T)) generally differs from sum(Q)/COP(mean(T)).", "",
        "[linear_sensitivity_annual.csv](linear_sensitivity_annual.csv) and [its resolved configuration](linear_sensitivity_config.json) show the resulting whole-building carrier/impact sensitivity. Polynomial curves are supported and covered by analytical tests; no equipment-specific polynomial coefficients are invented for the baseline.", "",
        "[pv_factor_sensitivity.csv](pv_factor_sensitivity.csv) reports overlap factors 0, 0.65 and 1 for the PV buildings. They span zero self-use to the maximum monthly overlap. Dynamic matching can be assessed alongside these cases, but the illustrative monthly factor is not fitted to the dynamic result.", "",
        "[pv_matching_diagnostics.csv](pv_matching_diagnostics.csv) reports each month's achieved overlap factor, fraction of PV production self-consumed and electrical self-sufficiency. For dynamic results these factors are derived from actual interval matching and provide an independent diagnostic for later ISO-factor comparison; they are not reused as monthly input factors.", "",
        "## Individual zones and collapsed buildings", "",
        "[thermal_zone_monthly.csv](thermal_zone_monthly.csv) retains original zone heating/cooling and separate AHU demands. [zone_service_monthly.csv](zone_service_monthly.csv) adds technology/carrier conversion, DHW and the proportional solar-thermal allocation. Its sums are checked against building service totals. A collapsed result has one synthetic zone; it cannot reconstruct separate upper/lower-zone demands.", "",
        "Annual forms are also provided in [thermal_zone_annual.csv](thermal_zone_annual.csv), [zone_service_annual.csv](zone_service_annual.csv) and [service_annual.csv](service_annual.csv). [zone_ancillary_annual.csv](zone_ancillary_annual.csv) and its monthly counterpart expose actual appliance and fan energy for each physical zone, common to every solver. Building base auxiliaries remain a building-level quantity.", "",
        "## Reproducibility and limits", "",
        "Run `python -m dt_prototype.energy_carriers.cli --config configs/example.json --energy-config configs/energy_example.json --engine all --output outputs/<new-directory>` with `src` on PYTHONPATH, or use the installed `dt-energy-carriers` command. Each case directory retains its input energies, evaluated performance, clipping flags and result balances; dynamic interval tables are gzip-compressed CSVs. The manifest records all input/code hashes and software versions.", "",
        "The new layer is a deterministic performance-curve model without capacity limits, plant staging, heat recovery between heating/cooling, or thermal/electrical storage. Generator-bus solar heat in monthly calculations uses an explicit utilisation factor, not a simulated tank. Renewable production uses the existing roof irradiance mapping. Future ISO-derived monthly matching can replace the input factors without changing the thermal solvers or meter equations.", ""]
    (out / "comparison_report.md").write_text("\n".join(docs), encoding="utf-8")
    (out / "validation_checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    return checks


def _zone_appendices(out):
    zone = pd.read_csv(out / "zone_service_annual.csv", dtype={"building_id": str})
    ancillary = pd.read_csv(out / "zone_ancillary_annual.csv", dtype={"building_id": str})
    folder = out / "zone_reports"
    folder.mkdir(exist_ok=True)
    pages = {}
    for bid, g in zone.groupby("building_id", sort=False):
        rows = []
        for (model, label), z in g.groupby(["model", "zone_id"], sort=False):
            heat = z[z.service.isin(["zone_heating", "ahu_heating"])]
            cool = z[z.service.isin(["zone_cooling", "ahu_cooling"])]
            dhw = z[z.service == "dhw"]
            rows.append(dict(model=model, Zone=label,
                **{"Heating useful MWh": heat.useful_demand_kWh.sum()/1000,
                   "Heating carrier MWh": heat.delivered_kWh.sum()/1000,
                   "Cooling useful MWh": cool.useful_demand_kWh.sum()/1000,
                   "Cooling carrier MWh": cool.delivered_kWh.sum()/1000,
                   "DHW carrier MWh": dhw.delivered_kWh.sum()/1000,
                   "ST bus heat MWh": dhw.solar_thermal_used_kWh.sum()/1000}))
        a = ancillary[ancillary.building_id == bid][["zone_id", "appliances_kWh", "fans_kWh", "dhw_kWh"]].copy()
        a.iloc[:, 1:] = a.iloc[:, 1:]/1000
        a.columns = ["Physical zone", "Appliances MWh", "Fans MWh", "Useful DHW MWh"]
        carriers = g[["service", "carrier"]].drop_duplicates().sort_values(["service", "carrier"])
        path = folder / f"{output_component(bid)}.md"
        path.write_text("\n".join([
            f"# {g.building_name.iloc[0]}: zone and service results", "",
            "[Return to comparison report](../comparison_report.md)", "",
            "Heating and cooling each include the corresponding zone and AHU service. Carrier energy is allocated at the shared generator and precedes PV meter allocation. It is not a zone-specific grid import. Solar thermal is generator-bus heat allocated to DHW in proportion to useful zone demand. Collapsed rows describe an alternative single-zone building, not an additional load to add to the original zones.", "",
            "## Service carrier mapping", "", table(carriers), "",
            "## Annual useful demand and delivered service energy", "",
            table(_ordered(pd.DataFrame(rows)).rename(columns={"model": "Model"})), "",
            "## Common annual ancillary inputs", "",
            "These actual physical-zone schedules are identical for every solver and sum to the building inputs. Do not add useful DHW again to delivered DHW energy. Building-level base and system auxiliaries are separately exposed in the energy/service CSV files.", "",
            table(a), "",
            "Full monthly allocations: [zone services](../zone_service_monthly.csv), [zone ancillary inputs](../zone_ancillary_monthly.csv).", ""
        ]), encoding="utf-8")
        pages[str(bid)] = path.relative_to(out).as_posix()
    return pages


def _figures(out, monthly, annual):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    folder = out / "figures"
    folder.mkdir(exist_ok=True)
    chosen = ["Dynamic_RC 5R1C", "Dynamic_RC 7R2C", "Monthly_SS", "Monthly_SS_simplified zone sum", "Monthly_SS_simplified collapsed",
              "Monthly_SS_VBDD monthly collapsed", "Monthly_SS_VBDD linear collapsed", "Monthly_SS_VBDD fixed collapsed"]
    for bid, group in monthly.groupby("building_id", sort=False):
        fig, axes = plt.subplots(2,2, figsize=(13,8), layout="constrained")
        for model in chosen:
            g = group[group.model == model].sort_values("period_id")
            if g.empty: continue
            for ax, quantity, title in zip(axes.flat,
                ["grid_import_kWh", "imported_natural_gas_kWh", "pv_self_consumed_kWh", "grid_export_kWh"],
                ["Imported electricity", "Imported gas", "PV self-consumption", "Exported electricity"]):
                if quantity in g:
                    ax.plot(range(1,13), g[quantity]/1000, marker=".", label=model)
                ax.set(title=title, xlabel="Month", ylabel="MWh", xticks=[1,3,6,9,12])
                ax.grid(alpha=.2)
        axes[0,0].legend(fontsize=7)
        fig.suptitle(group.building_name.iloc[0] + " | shared systems; distinct matching resolutions")
        fig.savefig(folder / f"{output_component(bid)}_monthly.png", dpi=150)
        plt.close(fig)
