from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from dt_prototype.monthly_ss_vbdd import MonthlyInput, VBOptions, calculate_month, simulate
from dt_prototype.monthly_ss_vbdd.model import utilisation_factor
from dt_prototype.monthly_ss_vbdd.weather import linear_fit, monthly_weather, temperature_linear_solar
from dt_prototype.monthly_ss_vbdd.preprocessing import prepare_building
from dt_prototype.common.project import ProjectInputs
from dt_prototype.monthly_ss.simulation.config import SimulationConfig
from dt_prototype.monthly_ss.run import run_building
from dt_prototype.monthly_ss_simplified.five_parameter import fit_five_parameter
from dt_prototype.monthly_ss_vbdd.signature import physics_coefficients


def example(**changes):
    row=MonthlyInput('1__single','1','Analytic','single','native_single_zone','2023-01',31,
                     0,20,24,1000,1000,0,0,2000,0,1e7,1000,True,True)
    return replace(row,**changes)


def test_constant_physics_matches_five_parameter_signature():
    temperatures=[-2,0,5,10,15,18,20,22,24,26,30,35]
    rows=[example(period_id=f'2023-{m:02}',days=pd.Period(f'2023-{m:02}').days_in_month,outdoor_temp_C=t) for m,t in enumerate(temperatures,1)]
    frame=simulate(rows,VBOptions('fixed'))
    fit=fit_five_parameter(temperatures,(frame.heating_kWh+frame.cooling_kWh)/frame.days)
    np.testing.assert_allclose(fit.predict_daily_energy(temperatures)/24,frame.average_power_kW,atol=1e-10)
    assert fit.heating_change_point_C == 18
    assert fit.cooling_change_point_C == 22
    assert fit.beta_heating_kWh_day_K/24 == pytest.approx(1)
    assert calculate_month(rows[0],VBOptions('fixed'))['heating_degree_days_K_day']==620


def test_calendar_normalisation_and_ahu_boundary():
    jan=calculate_month(example(ahu_heating_kWh=744),VBOptions('fixed'))
    feb=calculate_month(example(period_id='2024-02',days=29,ahu_heating_kWh=696),VBOptions('fixed'))
    assert jan['average_power_kW']==feb['average_power_kW']==19
    assert jan['heating_kWh']-jan['zone_heating_kWh']==744
    with pytest.raises(ValueError,match='calendar'):example(days=28)


def test_zero_activity_and_duplicate_or_invalid_input():
    result=calculate_month(example(heating_enabled=False,cooling_enabled=False,H_heating_W_K=0,H_cooling_W_K=0))
    assert result['zone_heating_kWh']==result['zone_cooling_kWh']==0
    assert result['balance_heating_C'] is None
    with pytest.raises(ValueError,match='duplicate'):simulate([example(),example()])
    with pytest.raises(ValueError):example(outdoor_temp_C=float('nan'))
    with pytest.raises(ValueError):example(H_time_constant_W_K=0)
    with pytest.raises(ValueError):VBOptions(eta_cooling=0)


def test_utilisation_limits_and_extreme_values():
    for a in [1,5,500]:
        assert utilisation_factor(1,a)==a/(a+1)
        for gamma in [1e-9,0.1,1,10,1e15]:
            for cooling in [False,True]:
                assert 0 < utilisation_factor(gamma,a,cooling=cooling) <= 1


def test_gain_response_and_temperature_response():
    cold=calculate_month(example(),VBOptions('fixed'))
    warm=calculate_month(example(outdoor_temp_C=5),VBOptions('fixed'))
    gain=calculate_month(example(internal_gain_W=3000),VBOptions('fixed'))
    assert cold['heating_kWh']>warm['heating_kWh']
    assert cold['heating_kWh']>gain['heating_kWh']
    assert calculate_month(example(outdoor_temp_C=30),VBOptions('fixed'))['cooling_kWh']>0


def test_weather_fit_does_not_use_demand():
    fit=linear_fit([0,10,20],[100,300,500])
    assert fit['intercept_W']==pytest.approx(100)
    assert fit['slope_W_K']==pytest.approx(20)
    with pytest.raises(ValueError):linear_fit([10,10,10],[1,2,3])


def test_physics_signature_sign_and_equivalence():
    row=example(outdoor_temp_C=5,solar_gain_W=100+20*5)
    options=VBOptions('fixed',eta_heating=0.8,eta_cooling=0.9)
    coef=physics_coefficients(row,100,20,options)
    result=calculate_month(row,options)
    assert coef['heating_slope_kW_K']==pytest.approx(-1.016)
    assert coef['cooling_slope_kW_K']==pytest.approx(0.92)
    assert result['zone_heating_kWh']/result['hours']==pytest.approx(max(0,coef['heating_intercept_kW']+coef['heating_slope_kW_K']*5))
    with pytest.raises(ValueError):physics_coefficients(row,100,20,VBOptions())


@pytest.fixture(scope='module')
def district():
    root=Path(__file__).resolve().parents[2]
    project=ProjectInputs.load(root/'configs/example.json')
    config=SimulationConfig(**{k:tuple(v) if k.endswith('_season') else v for k,v in project.configuration['operating'].items()})
    return project.preprocess(),config


def test_portfolio_balance_identity_collapse_conservation_and_solar(district):
    district,config=district
    for building in district.buildings:
        rows=prepare_building(building,district.weather,config)
        fresh=simulate(rows)
        qss=run_building(building,district.weather,config)
        for zone in building.zones:
            g=fresh[fresh.zone_id==zone.geometry.zone_label].sort_values('period_id')
            prefix=f'zone_{zone.geometry.zone_label}_' if len(building.zones)>1 else ''
            for target,source in [('zone_heating_kWh','heating_demand_kWh'),('zone_cooling_kWh','cooling_demand_kWh'),('ahu_heating_kWh','ahu_heating_demand_kWh'),('ahu_cooling_kWh','ahu_cooling_demand_kWh')]:
                np.testing.assert_allclose(g[target],qss[prefix+source],rtol=1e-9,atol=1e-6)
        if len(building.zones)>1:
            for period,g in fresh.groupby('period_id'):
                collapse=g[g.representation.str.startswith('single_zone_collapsed')].iloc[0]
                independent=g[g.representation=='individual_zone']
                for name in ['loss_heating_W','loss_cooling_W','gains_W','capacity_J_K','ahu_heating_kWh','ahu_cooling_kWh']:
                    assert collapse[name]==pytest.approx(independent[name].sum(),abs=1e-8)
    weather=monthly_weather(district.weather)
    np.testing.assert_allclose(weather.solar_S_kWh_m2,weather.solar_S_W_m2*weather.hours/1000)
    assert weather.hours.sum()==8760
