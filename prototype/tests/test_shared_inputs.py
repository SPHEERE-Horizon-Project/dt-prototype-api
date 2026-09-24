"""Contracts for consolidated inputs and truly independent engine execution."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from dt_prototype.common.project import ProjectInputs
from dt_prototype.cli import main
from dt_prototype.integration.engines.semi_stationary import SemiStationaryEngine, SemiStationaryRequest
from dt_prototype.integration.mapping.prepared_inputs import prepare_mapping_inputs
from dt_prototype.monthly.simulation.config import SimulationConfig

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def shared_project():return ProjectInputs.load(ROOT/'configs/example.json')

@pytest.fixture(scope='module')
def shared_district(shared_project):return shared_project.preprocess()

def test_prepared_mapping_inputs_match_existing_reference_components(shared_district):
    fields=['H_transmission_W_K','H_ground_W_K','H_ventilation_W_K','H_infiltration_W_K','thermal_capacity_J_K','total_gain_kWh','outdoor_temp_C','days','hours_valid']
    for building in shared_district.buildings:
        reference=SemiStationaryEngine().simulate(SemiStationaryRequest('test',str(building.geometry.building_id),'baseline','weather',building,shared_district.weather)).records
        prepared=prepare_mapping_inputs(building,shared_district.weather,SimulationConfig()).records
        reference={(r.zone_id,r.period_id):r for r in reference}
        assert len(reference)==len(prepared)
        for row in prepared:
            expected=reference[(row.zone_id,row.period_id)]
            np.testing.assert_allclose([getattr(row,k) for k in fields],[getattr(expected,k) for k in fields],rtol=1e-12,atol=1e-7)

def test_simplified_runs_without_other_forward_solvers(tmp_path,monkeypatch):
    import dt_prototype.monthly.simulation.quasi_steady_state as monthly
    import dt_prototype.dynamic.simulation.runner as dynamic
    def forbidden(*args,**kwargs):raise AssertionError('Another forward solver was executed')
    monkeypatch.setattr(monthly,'run_quasi_steady_state',forbidden)
    monkeypatch.setattr(dynamic,'run_building',forbidden)
    main(['simplified','--config',str(ROOT/'configs/example.json'),'--output',str(tmp_path/'simplified')])
    result=pd.read_csv(tmp_path/'simplified/monthly.csv')
    assert len(result)==60
    assert result.building_name.nunique()==5
    assert json.loads((tmp_path/'simplified/manifest.json').read_text())['status']=='complete'

def test_monthly_runs_without_dynamic_solver(tmp_path,monkeypatch):
    import dt_prototype.dynamic.simulation.runner as dynamic
    def forbidden(*args,**kwargs):raise AssertionError('Dynamic solver was executed')
    monkeypatch.setattr(dynamic,'run_building',forbidden)
    main(['monthly','--config',str(ROOT/'configs/example.json'),'--output',str(tmp_path/'monthly')])
    assert len(pd.read_csv(tmp_path/'monthly/monthly.csv'))==60

def test_single_zone_input_has_no_second_zone(shared_district):
    building=next(b for b in shared_district.buildings if b.name=='Test building 5')
    assert len(building.zones)==1
    rows=prepare_mapping_inputs(building,shared_district.weather,SimulationConfig()).records
    assert len(rows)==12 and all(r.zone_id is None for r in rows)

def test_shared_config_requires_explicit_scientific_settings(tmp_path):
    config=json.loads((ROOT/'configs/example.json').read_text())
    del config['operating']['heating_season']
    p=tmp_path/'config.json';p.write_text(json.dumps(config))
    with pytest.raises(ValueError,match='heating_season'):ProjectInputs.load(p)

def test_cli_refuses_to_overwrite_completed_directory(tmp_path):
    with pytest.raises(FileExistsError):main(['monthly','--config',str(ROOT/'configs/example.json'),'--output',str(tmp_path)])
