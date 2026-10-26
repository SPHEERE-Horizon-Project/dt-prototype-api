"""Integration checks against real shared building inputs and existing commands."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest

from dt_prototype.common.project import ProjectInputs
from dt_prototype.energy_carriers.config import EnergyConfig
from dt_prototype.energy_carriers.preprocessing import prepare_common
from dt_prototype.energy_carriers.adapters import solve_cases, energy_inputs, zone_allocations, THERMAL
from dt_prototype.energy_carriers.engine import calculate

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def inputs():
    project = ProjectInputs.load(ROOT / "configs/example.json")
    return project, project.preprocess(), EnergyConfig.load(ROOT / "configs/energy_example.json")


def test_all_buildings_common_schedule_energy_and_unique_roof_sizing(inputs):
    project, district, config = inputs
    for building in district.buildings:
        common = prepare_common(building, district.weather, config)
        expected_appliances = sum(z.schedule.electric_load.sum()*z.geometry.net_floor_area for z in building.zones) * district.weather.timestep_seconds/3.6e6
        assert common.intervals.appliances_kWh.sum() == pytest.approx(expected_appliances)
        assert common.monthly().appliances_kWh.sum() == pytest.approx(expected_appliances)
        assert len(common.monthly()) == 12
        roofs = sum(s.area for z in building.zones for s in z.geometry.surfaces if s.surface_type == "Roof")
        assert common.metadata["roof_area_m2"] == pytest.approx(roofs)
        b = config.building(building.geometry.building_id)
        assert common.metadata["pv_capacity_kWp"] == pytest.approx(roofs*b["pv"]["roof_coverage"]*b["pv"]["module_kWp_per_m2"])
        for field in ("dhw_kWh", "appliances_kWh", "fans_kWh"):
            np.testing.assert_allclose(common.intervals[field], sum(z[field] for z in common.zones.values()))
        assert all(z.pv_generation_kWh.sum() == 0 for z in common.zones.values())


def test_qss_vbdd_all_buildings_match_after_conversion_and_zone_allocation(inputs,tmp_path):
    project, district, config = inputs
    for building in district.buildings:
        common = prepare_common(building, district.weather, config)
        qss = solve_cases(building,district.weather,project.configuration["operating"],"Monthly_SS",tmp_path)[0]
        vb = solve_cases(building,district.weather,project.configuration["operating"],"Monthly_SS_VBDD",tmp_path,zone_mode="sum")[0]
        a = calculate(energy_inputs(qss,common),config,str(building.geometry.building_id),resolution="monthly")
        b = calculate(energy_inputs(vb,common),config,str(building.geometry.building_id),resolution="monthly")
        fields = [c for c in a.intervals if c.endswith("_kWh")]
        np.testing.assert_allclose(a.intervals[fields],b.intervals[fields],atol=1e-6,rtol=1e-9)
        alloc = zone_allocations(qss,common,a)
        for field in ("delivered_kWh","auxiliary_kWh","solar_thermal_used_kWh"):
            np.testing.assert_allclose(alloc.groupby(["period_id","service"])[field].sum(),
                a.services.groupby(["period_id","service"])[field].sum(),atol=1e-6,rtol=1e-9)


def test_simplified_has_no_dependency_on_another_forward_solver(inputs,tmp_path,monkeypatch):
    import dt_prototype.monthly_ss.simulation.quasi_steady_state as qss
    import dt_prototype.dynamic_rc.simulation.runner as dynamic
    def forbidden(*args,**kwargs):
        raise AssertionError("Another forward solver was called")
    monkeypatch.setattr(qss,"run_quasi_steady_state",forbidden)
    monkeypatch.setattr(dynamic,"run_building",forbidden)
    project,district,config = inputs
    cases = solve_cases(district.buildings[0],district.weather,project.configuration["operating"],"Monthly_SS_simplified",tmp_path)
    assert {c.representation for c in cases} == {"sum_of_independent_zones","single_zone_collapsed"}
    assert all(len(c.total()) == 12 for c in cases)
    assert len(cases[0].zones) == 2 and len(cases[1].zones) == 1


def test_dynamic_conversion_uses_thermal_powers_and_keeps_common_schedule(inputs,tmp_path):
    project,district,config = inputs
    building = district.buildings[1]
    common = prepare_common(building,district.weather,config)
    case = solve_cases(building,district.weather,project.configuration["operating"],"Dynamic_RC",tmp_path,
                       dynamic_options=project.configuration["dynamic"])[0]
    frame = energy_inputs(case,common)
    raw = pd.read_csv(tmp_path/"thermal_dynamic.csv")
    assert frame.zone_heating_kWh.sum() == pytest.approx(raw.heating_load.sum()/1000)
    assert frame.zone_cooling_kWh.sum() == pytest.approx(-raw.cooling_load.sum()/1000)
    np.testing.assert_allclose(frame.dhw_kWh,raw.dhw_demand/1000,atol=1e-9)
    np.testing.assert_allclose(frame.appliances_kWh,raw.electric_appliances/1000,atol=1e-9)
    result = calculate(frame,config,str(building.geometry.building_id),resolution="dynamic")
    assert max(result.check_balances().values()) < 1e-6


@pytest.mark.parametrize("option", ["plants","latent","pv_battery"])
def test_dynamic_boundary_rejects_incompatible_options(inputs,tmp_path,option):
    project,district,config = inputs
    with pytest.raises(ValueError,match="requires"):
        solve_cases(district.buildings[0],district.weather,project.configuration["operating"],"Dynamic_RC",tmp_path,
                    dynamic_options={**project.configuration["dynamic"],option:True})


def test_existing_monthly_command_with_energy_config_produces_complete_results(tmp_path):
    from dt_prototype.cli import main
    out = tmp_path/"monthly_energy"
    main(["Monthly_SS","--config",str(ROOT/"configs/example.json"),"--energy-config",str(ROOT/"configs/energy_example.json"),"--output",str(out)])
    manifest = json.loads((out/"manifest.json").read_text())
    frame = pd.read_csv(out/"energy_monthly.csv")
    assert manifest["status"] == "complete"
    assert len(frame) == 60 and frame.building_id.nunique() == 5
    assert "grid_import_kWh" in frame and "net_energy_cost" in frame
    assert (out/"comparison_report.md").is_file()
    service_annual = pd.read_csv(out/"service_annual.csv")
    service_monthly = pd.read_csv(out/"service_monthly.csv")
    assert service_annual.delivered_kWh.sum() == pytest.approx(service_monthly.delivered_kWh.sum())
    assert len(list((out/"zone_reports").glob("*.md"))) == 5
    assert len(pd.read_csv(out/"zone_ancillary_annual.csv")) == 9


def test_vbdd_command_routes_options_to_shared_layer(tmp_path,monkeypatch):
    from dt_prototype.monthly_ss_vbdd.cli import main
    import dt_prototype.energy_carriers.workflow as workflow
    received = {}
    def run(*args,**kwargs):
        received.update(kwargs)
    monkeypatch.setattr(workflow,"run_project",run)
    main(["--config",str(ROOT/"configs/example.json"),"--energy-config",str(ROOT/"configs/energy_example.json"),
          "--output",str(tmp_path/"vb"),"--solar","temperature_linear","--utilisation","fixed","--eta-heating",".8"])
    assert received["engine"] == "Monthly_SS_VBDD"
    assert received["vb_solar"] == "temperature_linear"
    assert received["vb_options"].eta_heating == .8
