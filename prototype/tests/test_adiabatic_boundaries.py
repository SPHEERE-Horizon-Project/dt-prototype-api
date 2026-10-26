"""Boundary overrides preserve physical inventory and reach every thermal path."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import csv

import numpy as np
import pandas as pd
import pytest

from tests.dynamic_rc.conftest import make_box_building, make_constant_weather, make_two_zone_box_building
from dt_prototype.common.preprocessing.geometry import BuildingGeometry, SurfaceSpec
from dt_prototype.common.preprocessing.tabular_geometry import load_district_tables, write_district_tables
from dt_prototype.dynamic_rc.simulation.config import SimulationConfig as DynamicConfig
from dt_prototype.dynamic_rc.simulation.model_base import get_model_class
from dt_prototype.dynamic_rc.simulation.runner import run_building as run_dynamic
from dt_prototype.dynamic_rc.simulation.zone import build_zone as dynamic_zone
from dt_prototype.dynamic_rc.simulation.pv_system import PVSystem
from dt_prototype.monthly_ss.simulation.config import SimulationConfig
from dt_prototype.monthly_ss.simulation.models.model_5r1c import Model5R1C
from dt_prototype.monthly_ss.simulation.zone import build_zone as monthly_zone
from dt_prototype.monthly_ss.run import run_building as run_monthly
from dt_prototype.monthly_ss_simplified.mapping.prepared_inputs import prepare_mapping_inputs
from dt_prototype.monthly_ss_simplified.mapping.reference_to_model3 import write_reference_case_as_model3_inputs
from dt_prototype.monthly_ss_simplified.model3.model3 import run_forward
from dt_prototype.monthly_ss_simplified.engines.semi_stationary import SemiStationaryEngine, SemiStationaryRequest
from dt_prototype.monthly_ss_simplified.verification_cases import make_reference_verification_case
from dt_prototype.monthly_ss_vbdd.preprocessing import prepare_building
from dt_prototype.monthly_ss_vbdd.model import simulate, VBOptions
from dt_prototype.monthly_ss_vbdd.weather import temperature_linear_solar
from dt_prototype.energy_carriers.config import EnergyConfig
from dt_prototype.energy_carriers.preprocessing import prepare_common


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('condition', ['auto', '', None, 'adiabatic'])
def test_optional_csv_condition_and_round_trip(tmp_path, condition):
    geometry = make_box_building(n_steps=48).geometry
    folder = tmp_path / 'source'
    write_district_tables(geometry, folder)
    file = folder / 'surfaces.csv'
    with file.open(newline='') as stream:
        reader = csv.DictReader(stream)
        rows, fields = list(reader), reader.fieldnames
    if condition is None:
        fields = [name for name in fields if name != 'boundary_condition']
        for row in rows:
            row.pop('boundary_condition')
    else:
        rows[0]['boundary_condition'] = condition
    with file.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    loaded = load_district_tables(folder)[0]
    surface = loaded.zones[0].surfaces[0]
    assert surface.boundary_condition == (condition or 'auto')
    assert surface.surface_type == 'ExtWall'
    write_district_tables(loaded, tmp_path / 'roundtrip')
    assert load_district_tables(tmp_path / 'roundtrip')[0].to_dict() == loaded.to_dict()


def test_legacy_and_explicit_geometry_json():
    geometry = make_box_building(n_steps=48).geometry
    old = geometry.to_dict()
    for surface in old['zones'][0]['surfaces']:
        surface.pop('boundary_condition')
    assert BuildingGeometry.from_dict(old).to_dict() == geometry.to_dict()
    geometry.zones[0].surfaces[0].boundary_condition = 'adiabatic'
    assert BuildingGeometry.from_dict(geometry.to_dict()).to_dict() == geometry.to_dict()


@pytest.mark.parametrize('value', ['adiabtik', 'outdoor', True, None])
def test_unknown_boundary_is_rejected(value):
    with pytest.raises(ValueError, match='boundary_condition'):
        SurfaceSpec('ExtWall', 10, boundary_condition=value)


def test_bad_csv_boundary_reports_source_and_line(tmp_path):
    write_district_tables(make_box_building(n_steps=48).geometry, tmp_path / 'source')
    file = tmp_path / 'source/surfaces.csv'
    file.write_text(file.read_text().replace(',auto', ',adiabtik', 1))
    with pytest.raises(ValueError, match=r'surfaces.csv:2: boundary_condition'):
        load_district_tables(file.parent)


@pytest.mark.parametrize('surface_type', ['ExtWall', 'Roof', 'GroundFloor'])
def test_partial_boundary_retains_construction_glazing_capacity_and_inventory(surface_type):
    building = make_box_building(n_steps=48)
    weather = make_constant_weather(n_steps=48)
    config = SimulationConfig()
    original = Model5R1C(building, weather, config)
    target = next(s for s in building.geometry.surfaces if s.surface_type == surface_type)
    area = target.area
    fraction = 0.4
    target.area = area * (1 - fraction)
    building.geometry.zones[0].surfaces.append(replace(target, area=area*fraction, boundary_condition='adiabatic'))
    changed = Model5R1C(building, weather, config)
    c = building.envelope.constructions[surface_type]
    wwr = building.envelope.wwr if surface_type == 'ExtWall' else 0
    removed_h = area*fraction*((1-wwr)*c.u_value + wwr*building.envelope.window.u_value)
    assert changed.UA_tot == pytest.approx(original.UA_tot - removed_h)
    assert changed.Cm == pytest.approx(original.Cm)
    assert changed.Atot == original.Atot
    for builder in (dynamic_zone, monthly_zone):
        zone = builder(building, weather)
        adiabatic = zone.surfaces[-1]
        assert not adiabatic.is_external
        assert adiabatic.construction is c
        assert adiabatic.surface_type == surface_type
        assert adiabatic.glazed_area == pytest.approx(area*fraction*wwr)
        assert sum(s.gross_area for s in zone.surfaces) == original.Atot
    for name in ('5R1C', '7R2C'):
        model = get_model_class(name)(building, weather, DynamicConfig(model=name))
        assert model.UA_tot == pytest.approx(original.UA_tot - removed_h)


@pytest.mark.parametrize('model_name', ['5R1C', '7R2C', 'Monthly_SS'])
def test_adiabatic_boundaries_remove_solar_and_sky_forcing(model_name):
    building = make_box_building(n_steps=48)
    weather = make_constant_weather(n_steps=48)
    weather.average_dt_air_sky = 8.0
    for col in weather.df:
        if col.startswith('poa_glob_'):
            weather.df[col] = 500.0
        if col.startswith('poa_dir_'):
            weather.df[col] = 300.0
    # Ground remains exposed; no solar/sky correction applies to it.
    for s in building.geometry.surfaces:
        if s.surface_type in ('ExtWall', 'Roof'):
            s.boundary_condition = 'adiabatic'
    if model_name == 'Monthly_SS':
        model = Model5R1C(building, weather, SimulationConfig())
        np.testing.assert_array_equal(model.phi_sol, np.zeros(48))
    else:
        model = get_model_class(model_name)(building, weather, DynamicConfig(model=model_name))
        if model_name == '5R1C':
            np.testing.assert_array_equal(model.phi_sol, np.zeros(48))
        else:
            np.testing.assert_allclose(model.theta_eq_tot, weather.df.temp_air)
            np.testing.assert_array_equal(model.Q_il_kon, np.zeros(48))
            np.testing.assert_array_equal(model.Q_il_str_aw, np.zeros(48))
            np.testing.assert_array_equal(model.Q_il_str_iw, np.zeros(48))


@pytest.mark.parametrize('model_name', ['5R1C', '7R2C'])
def test_fully_adiabatic_dynamic_zone_has_actionable_error(model_name):
    building = make_box_building(n_steps=48)
    for s in building.geometry.surfaces:
        s.boundary_condition = 'adiabatic'
    with pytest.raises(ValueError, match='fully enclosed'):
        get_model_class(model_name)(building, make_constant_weather(n_steps=48), DynamicConfig(model=model_name))


@pytest.mark.parametrize('model_name', ['5R1C', '7R2C'])
def test_explicit_adiabatic_internal_surface_preserves_existing_dynamic_solution(model_name):
    building = make_box_building(n_steps=48)
    weather = make_constant_weather(n_steps=48)
    config = DynamicConfig(model=model_name, plants=False, latent=False)
    expected = run_dynamic(building, weather, config)
    for surface in building.geometry.surfaces:
        if surface.surface_type.startswith('Int'):
            surface.boundary_condition = 'adiabatic'
    pd.testing.assert_frame_equal(run_dynamic(building, weather, config), expected, check_exact=True)


@pytest.fixture(scope='module')
def controlled_cases():
    case = make_reference_verification_case('transmission_only')
    for az in (90, 180, 270):
        for mode in ('glob', 'dir'):
            case.weather.df[f'poa_{mode}_az{az}_t90'] = 0.0
    baseline = case.building
    changed = deepcopy(baseline)
    changed.geometry.zones[0].surfaces = [SurfaceSpec('ExtWall', 50),
        SurfaceSpec('ExtWall', 50, boundary_condition='adiabatic'), SurfaceSpec('IntWall', 100)]
    config = SimulationConfig(heating_season=(1,365), cooling_season=(1,365))
    return baseline, changed, case.weather, config


def test_three_monthly_paths_match_controlled_transmission_balance(controlled_cases, tmp_path):
    baseline, changed, weather, config = controlled_cases
    for name, building, expected_h in [('baseline', baseline, 50.0), ('adiabatic', changed, 25.0)]:
        monthly = run_monthly(building, weather, config)
        expected = expected_h * 20 * 31 * 24 / 1000
        assert monthly.iloc[0].heating_demand_kWh == pytest.approx(expected)
        mapping = prepare_mapping_inputs(building, weather, config)
        assert all(row.H_transmission_W_K == expected_h for row in mapping.records)
        mapped = write_reference_case_as_model3_inputs(tmp_path/name, reference_results=mapping,
            reference_building=building, reference_weather=weather, run_id='adiabatic_test',
            scenario_id='test', weather_id='constant', zone_id=None, config=config,
            comparison_mode='seasonal_ahu')
        simplified, _ = run_forward(mapped.data_dir)
        assert simplified[0]['useful_heating_kWh'] == pytest.approx(expected)
        vb = prepare_building(building, weather, config)
        for options in (VBOptions(), VBOptions('fixed')):
            assert simulate(vb, options).iloc[0].zone_heating_kWh == pytest.approx(expected)
        # Linear-solar fitting needs varying temperatures. Inputs are the same
        # prepared boundary coefficients; its weather-only fit must retain them.
        varied = [replace(row, outdoor_temp_C=float(i)) for i,row in enumerate(vb)]
        linear, _ = temperature_linear_solar(varied)
        assert all(row.H_heating_W_K == expected_h for row in linear)


def test_ground_override_reaches_both_simplified_adapters():
    building = make_box_building()
    weather = make_constant_weather()
    for s in building.geometry.surfaces:
        if s.surface_type == 'GroundFloor':
            s.boundary_condition = 'adiabatic'
    config = SimulationConfig()
    mapping = prepare_mapping_inputs(building, weather, config)
    assert all(row.H_ground_W_K == 0 for row in mapping.records)
    assert all(row.H_transmission_W_K >= 0 for row in mapping.records)
    result = SemiStationaryEngine().simulate(SemiStationaryRequest('test','box','test','constant',building,weather,config))
    assert all(row.H_ground_W_K == 0 for row in result.records)


@pytest.mark.parametrize('model_name', ['5R1C', '7R2C'])
def test_two_zone_subset_changes_only_the_selected_zone(model_name):
    building = make_two_zone_box_building(n_steps=48)
    weather = make_constant_weather(n_steps=48)
    config = DynamicConfig(model=model_name, plants=False, latent=False)
    baseline = run_dynamic(building, weather, config)
    building.zones[0].geometry.surfaces[0].boundary_condition = 'adiabatic'
    changed = run_dynamic(building, weather, config)
    assert np.isfinite(changed.select_dtypes(include='number').to_numpy()).all()
    lower = [col for col in baseline if col.startswith('zone_lower_')]
    pd.testing.assert_frame_equal(changed[lower], baseline[lower], check_exact=True)
    assert not changed.zone_upper_sensible_load.equals(baseline.zone_upper_sensible_load)


def test_thermal_roof_override_preserves_physical_renewable_resource():
    building = make_box_building()
    building.geometry.building_id = '1'  # existing demonstration energy config
    weather = make_constant_weather()
    weather.df['poa_glob_az0_t0'] = 500.0
    weather.df['poa_dir_az0_t0'] = 300.0
    config = EnergyConfig.load(ROOT/'configs/energy_example.json')
    original = prepare_common(building, weather, config)
    pv_original = PVSystem(dynamic_zone(building, weather)).production(weather.df.temp_air.to_numpy())
    for s in building.geometry.surfaces:
        if s.surface_type == 'Roof':
            s.boundary_condition = 'adiabatic'
    changed = prepare_common(building, weather, config)
    pd.testing.assert_frame_equal(changed.intervals, original.intervals, check_exact=True)
    assert changed.metadata == original.metadata
    pv_changed = PVSystem(dynamic_zone(building, weather)).production(weather.df.temp_air.to_numpy())
    np.testing.assert_array_equal(pv_changed, pv_original)
    assert pv_changed.sum() > 0
