"""Independent analytical and invariance checks for shared energy accounting."""
from copy import deepcopy
import numpy as np
import pandas as pd
import pytest

from dt_prototype.energy_carriers import EnergyConfig, PerformanceCurve, calculate, aggregate_inputs
from dt_prototype.energy_carriers.config import SERVICES
from dt_prototype.energy_carriers.engine import ENERGY_INPUTS


def configuration():
    factors = dict(primary_nonrenewable=2, primary_renewable=.5, carbon_kgCO2e_per_kWh=.25,
        import_price_per_kWh=.3, export_primary_nonrenewable=0, export_primary_renewable=0,
        export_carbon_kgCO2e_per_kWh=0, export_price_per_kWh=.1, source="analytical fixture")
    tech = dict(carrier="electricity", performance=dict(coefficients=[2], temperature_min_C=-20,
        temperature_max_C=45, out_of_range="clip", source="analytical fixture"),
        distribution_efficiency=1, emission_efficiency=1, regulation_efficiency=1,
        auxiliary_kWh_per_kWh_generated=0, description="analytical fixture")
    return dict(schema_version="1.0", scenario_id="test", description="Analytical test", currency="EUR",
        carriers={"electricity": factors, "natural_gas": deepcopy(factors)}, technologies={"hp": tech},
        buildings={"a": dict(services={s: "hp" for s in SERVICES}, fan_W_per_m3_h=0, base_auxiliary_W=0,
            source="fixture", pv=dict(roof_coverage=.3, module_kWp_per_m2=.2, performance_ratio=.8,
                monthly_factor=[.5]*12, factor_basis="overlap", source="fixture"),
            solar_thermal=dict(roof_coverage=.1, eta0=.8, a1_W_m2K=3, a2_W_m2K2=.01,
                mean_fluid_temperature_C=50, monthly_utilisation=[1]*12, source="fixture"))})


def monthly(**energies):
    row = dict(time="2023-01-01", period_id="2023-01", duration_h=744, outdoor_temp_C=10,
               **{c: 0.0 for c in ENERGY_INPUTS})
    row.update(energies)
    return pd.DataFrame([row])


def hourly(n=744):
    index = pd.date_range("2023-01-01", periods=n, freq="h")
    return pd.DataFrame(dict(time=index.astype(str), period_id=index.to_period("M").astype(str),
        duration_h=1.0, outdoor_temp_C=10.0, **{c: np.zeros(n) for c in ENERGY_INPUTS}))


def test_hand_calculated_meter_and_impacts():
    # 100 thermal / COP2 + 10 appliances = 60 electric; PV40, factor .5 -> use20.
    r = calculate(monthly(zone_heating_kWh=100, appliances_kWh=10, pv_generation_kWh=40),
                  EnergyConfig.from_dict(configuration()), "a", resolution="monthly")
    row = r.intervals.iloc[0]
    assert row.gross_electricity_kWh == 60
    assert row.pv_self_consumed_kWh == 20
    assert row.grid_import_kWh == 40
    assert row.grid_export_kWh == 20
    assert row.import_primary_total_kWh == 100
    assert row.import_carbon_kgCO2e == 10
    assert row.import_energy_cost == 12
    assert row.export_energy_credit == 2
    assert row.net_energy_cost == 10
    assert max(r.check_balances().values()) < 1e-10


def test_solar_thermal_at_generator_bus_and_downstream_losses():
    cfg = configuration()
    cfg["technologies"]["hp"]["distribution_efficiency"] = .8
    r = calculate(monthly(dhw_kWh=80, solar_thermal_available_kWh=50),
                  EnergyConfig.from_dict(cfg), "a", resolution="monthly")
    dhw = r.services[r.services.service == "dhw"].iloc[0]
    assert dhw.generator_required_kWh == 100
    assert dhw.solar_thermal_used_kWh == 50
    assert dhw.delivered_kWh == 25
    assert dhw.downstream_losses_kWh == 20
    assert abs(dhw.conversion_residual_kWh) < 1e-10


@pytest.mark.parametrize("load,pv,expected", [(0, 20, (0,20)), (20,0,(20,0)), (20,20,(10,10))])
def test_zero_load_zero_pv_and_simultaneous_monthly_flows(load, pv, expected):
    r = calculate(monthly(appliances_kWh=load, pv_generation_kWh=pv), EnergyConfig.from_dict(configuration()), "a", resolution="monthly")
    assert (r.intervals.grid_import_kWh[0], r.intervals.grid_export_kWh[0]) == expected


def test_generation_factor_is_capped_and_reported():
    cfg = configuration()
    cfg["buildings"]["a"]["pv"].update(factor_basis="generation", monthly_factor=1)
    r = calculate(monthly(appliances_kWh=10, pv_generation_kWh=100), EnergyConfig.from_dict(cfg), "a", resolution="monthly")
    assert r.intervals.pv_factor_capped[0]
    assert r.intervals.pv_self_consumed_kWh[0] == 10
    assert r.intervals.grid_export_kWh[0] == 90


def test_pv_does_not_offset_gas():
    cfg = configuration()
    cfg["technologies"]["gas"] = deepcopy(cfg["technologies"]["hp"])
    cfg["technologies"]["gas"].update(carrier="natural_gas")
    cfg["technologies"]["gas"]["performance"]["coefficients"] = [.8]
    cfg["buildings"]["a"]["services"]["zone_heating"] = "gas"
    row = calculate(monthly(zone_heating_kWh=80, pv_generation_kWh=100),
                    EnergyConfig.from_dict(cfg), "a", resolution="monthly").intervals.iloc[0]
    assert row.imported_natural_gas_kWh == 100
    assert row.grid_export_kWh == 100
    assert row.grid_import_kWh == 0


def test_dynamic_day_night_matching_not_monthly_netting():
    f = hourly(2)
    f["appliances_kWh"] = [0,10]
    f["pv_generation_kWh"] = [10,0]
    r = calculate(f, EnergyConfig.from_dict(configuration()), "a", resolution="dynamic")
    assert r.intervals.grid_import_kWh.sum() == 10
    assert r.intervals.grid_export_kWh.sum() == 10
    assert r.intervals.pv_self_consumed_kWh.sum() == 0


def test_constant_conversion_commutes_with_aggregation():
    f = hourly()
    f["zone_heating_kWh"] = np.linspace(0, 5, len(f))
    f["zone_cooling_kWh"] = np.linspace(3, 0, len(f))
    f["dhw_kWh"] = 1
    cfg = EnergyConfig.from_dict(configuration())
    a = calculate(f, cfg, "a", resolution="dynamic").monthly()
    b = calculate(aggregate_inputs(f), cfg, "a", resolution="monthly").monthly()
    pd.testing.assert_frame_equal(a, b, check_exact=False, check_dtype=False, atol=1e-9, rtol=1e-12)


def test_linear_cop_monthly_mean_is_not_mean_inverse_cop():
    f = hourly()
    f["zone_heating_kWh"] = 1
    f["outdoor_temp_C"] = np.tile([0,20], 372)
    cfg = configuration()
    cfg["technologies"]["hp"]["performance"]["coefficients"] = [3,.1]
    cfg = EnergyConfig.from_dict(cfg)
    fine = calculate(f, cfg, "a", resolution="dynamic").intervals.zone_heating_delivered_kWh.sum()
    coarse = calculate(aggregate_inputs(f), cfg, "a", resolution="monthly").intervals.zone_heating_delivered_kWh.sum()
    assert fine == pytest.approx(372/3 + 372/5)
    assert coarse == pytest.approx(744/4)
    assert abs(coarse-fine) > 10


def test_polynomial_and_domain_clipping():
    curve = PerformanceCurve.from_dict(dict(coefficients=[3,.05,.002], temperature_min_C=0,
        temperature_max_C=20, out_of_range="clip", source="fixture"))
    values, clipped = curve.evaluate([-10,10,30])
    assert values == pytest.approx([3,3.7,4.8])
    assert clipped.tolist() == [True,False,True]


def test_reject_polynomial_negative_between_positive_endpoints():
    with pytest.raises(ValueError, match="strictly positive"):
        PerformanceCurve.from_dict(dict(coefficients=[-1,0,1], temperature_min_C=-2,
            temperature_max_C=2, out_of_range="error", source="fixture"))


def test_domain_error_instead_of_uncontrolled_extrapolation():
    cfg = configuration()
    cfg["technologies"]["hp"]["performance"]["out_of_range"] = "error"
    with pytest.raises(ValueError, match="outside technology"):
        calculate(monthly(outdoor_temp_C=-30), EnergyConfig.from_dict(cfg), "a", resolution="monthly")


@pytest.mark.parametrize("change", [
    lambda c: c["carriers"].pop("electricity"),
    lambda c: c["technologies"]["hp"].update(distribution_efficiency=0),
    lambda c: c["buildings"]["a"]["pv"].update(monthly_factor=[.5]*11),
    lambda c: c["buildings"]["a"]["pv"].update(monthly_factor=1.1),
    lambda c: c["buildings"]["a"]["pv"].update(factor_basis="unknown"),
    lambda c: c["buildings"]["a"]["services"].update(zone_heating="unknown"),
    lambda c: c["carriers"]["electricity"].update(primary_nonrenewable=float("nan")),
    lambda c: c.update(typo=True),
])
def test_invalid_configuration_fails(change):
    cfg = configuration()
    change(cfg)
    with pytest.raises(ValueError):
        EnergyConfig.from_dict(cfg)


@pytest.mark.parametrize("field,value", [("appliances_kWh",-1), ("dhw_kWh",float("nan")),
    ("duration_h",0), ("duration_h",743), ("period_id","2023-02")])
def test_invalid_energy_inputs_fail(field, value):
    f = monthly()
    f[field] = value
    with pytest.raises(ValueError):
        calculate(f, EnergyConfig.from_dict(configuration()), "a", resolution="monthly")


def test_month_specific_factors_and_signed_tariffs():
    cfg = configuration()
    cfg["carriers"]["electricity"]["import_price_per_kWh"] = [-.1,.2] + [.3]*10
    a = monthly(appliances_kWh=10)
    b = monthly(time="2023-02-01", period_id="2023-02", duration_h=672, appliances_kWh=10)
    r = calculate(pd.concat([a,b]), EnergyConfig.from_dict(cfg), "a", resolution="monthly")
    assert r.intervals.import_energy_cost.tolist() == [-1,2]


def test_leap_month_duration_is_calendar_aware():
    r = calculate(monthly(time="2024-02-01", period_id="2024-02", duration_h=696),
                  EnergyConfig.from_dict(configuration()), "a", resolution="monthly")
    assert len(r.intervals) == 1


def test_interval_gap_and_month_crossing_rejected():
    f = hourly(2)
    f.loc[1, "time"] = "2023-01-01 03:00:00"
    with pytest.raises(ValueError, match="contiguous"):
        calculate(f, EnergyConfig.from_dict(configuration()), "a", resolution="dynamic")
    f = monthly(time="2023-01-31 23:00:00", duration_h=2)
    with pytest.raises(ValueError, match="month boundary|month-boundary|calendar-month"):
        calculate(f, EnergyConfig.from_dict(configuration()), "a", resolution="dynamic")


def test_auxiliary_not_omitted_from_meter():
    cfg = configuration()
    cfg["technologies"]["hp"]["auxiliary_kWh_per_kWh_generated"] = .1
    row = calculate(monthly(zone_heating_kWh=100, fans_kWh=2, base_auxiliary_kWh=3),
                    EnergyConfig.from_dict(cfg), "a", resolution="monthly").intervals.iloc[0]
    assert row.system_auxiliary_kWh == 10
    assert row.grid_import_kWh == 65


def test_fit_quadratic_samples_with_residual_evidence():
    from dt_prototype.energy_carriers.curves import fit_performance_curve
    temperatures = np.array([-5,0,5,10,15,20])
    samples = 3 + .05*temperatures + .002*temperatures**2
    curve, metrics = fit_performance_curve(temperatures, samples, degree=2, source="synthetic analytic curve")
    assert curve["coefficients"] == pytest.approx([3,.05,.002])
    assert metrics["max_abs_error"] < 1e-12
    assert metrics["R_squared"] == pytest.approx(1)


def test_hourly_and_half_hourly_constant_power_agree():
    a = hourly(2)
    a["zone_heating_kWh"] = [4,4]
    a["pv_generation_kWh"] = [1,3]
    b = hourly(4)
    index = pd.date_range("2023-01-01", periods=4, freq="30min")
    b["time"], b["duration_h"] = index.astype(str), .5
    b["zone_heating_kWh"] = 2
    b["pv_generation_kWh"] = [.5,.5,1.5,1.5]
    cfg = EnergyConfig.from_dict(configuration())
    ar = calculate(a, cfg, "a", resolution="dynamic").annual()
    br = calculate(b, cfg, "a", resolution="dynamic").annual()
    pd.testing.assert_frame_equal(ar,br,check_dtype=False,atol=1e-10,rtol=1e-10)
