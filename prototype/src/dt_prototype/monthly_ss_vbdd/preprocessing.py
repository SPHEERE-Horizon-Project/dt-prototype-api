"""Adapter from shared DT inputs. Builds static parameters, never demand outputs.

    L_h = H_h (T_h - T_month) + offset_h [monthly average W].

The offset retains ventilation/supply-temperature covariance from hourly input
schedules. Collapsing sums extensive quantities before computing utilisation.
"""
from dataclasses import replace
import numpy as np
from dt_prototype.common.constants import AIR_SPECIFIC_HEAT
from dt_prototype.monthly_ss.simulation.config import season_mask
from dt_prototype.monthly_ss.simulation.models.model_5r1c import Model5R1C
from dt_prototype.monthly_ss.simulation.quasi_steady_state import _ahu_sensible_balance
from .model import MonthlyInput
from .weather import monthly_weather


def prepare_building(building, weather, config, *, include_collapsed=True):
    monthly = monthly_weather(weather)
    index = weather.df.index
    te = weather.df.temp_air.to_numpy()
    hseason = season_mask(index, config.heating_season)
    cseason = season_mask(index, config.cooling_season)
    per_zone, areas = [], []
    for zi, input_zone in enumerate(building.zones):
        model = Model5R1C(building, weather, config, zone_index=zi)
        z = model.zone
        ha = (z.heating_setpoint > 17) & hseason
        ca = (z.cooling_setpoint < 27) & cseason
        th = float(z.heating_setpoint[ha].mean()) if ha.any() else 20.0
        tc = float(z.cooling_setpoint[ca].mean()) if ca.any() else 26.0
        supply, coil, hve = _ahu_sensible_balance(z, te, hseason, cseason, th, tc, config)
        hi = z.infiltration_mass_flow * AIR_SPECIFIC_HEAT
        hv = z.ventilation_mass_flow * AIR_SPECIFIC_HEAT
        h_direct = hi + (hv if z.ahu is None else 0)
        rows = []
        for m in monthly.itertuples(index=False):
            mask = index.to_period('M').astype(str) == m.period_id
            kh = model.UA_tot * ha[mask].mean() + (h_direct * ha)[mask].mean()
            kc = model.UA_tot * ca[mask].mean() + (h_direct * ca)[mask].mean()
            lh = model.UA_tot * ha[mask].mean() * (th-m.outdoor_temp_C) + ((hi*(th-te)+hv*(th-supply))*ha)[mask].mean()
            lc = model.UA_tot * ca[mask].mean() * (tc-m.outdoor_temp_C) + ((hi*(tc-te)+hv*(tc-supply))*ca)[mask].mean()
            bid = str(building.geometry.building_id)
            label = str(input_zone.geometry.zone_label)
            rows.append(MonthlyInput(
                case_id=f'{bid}__{label}', building_id=bid, building_name=building.name,
                zone_id=label, representation='individual_zone' if len(building.zones)>1 else 'native_single_zone',
                period_id=m.period_id, days=int(m.days), outdoor_temp_C=m.outdoor_temp_C,
                heating_setpoint_C=th, cooling_setpoint_C=tc,
                H_heating_W_K=float(kh), H_cooling_W_K=float(kc),
                heating_offset_W=float(lh-kh*(th-m.outdoor_temp_C)),
                cooling_offset_W=float(lc-kc*(tc-m.outdoor_temp_C)),
                internal_gain_W=float((z.gains_convective+z.gains_radiative)[mask].mean()),
                solar_gain_W=float(model.phi_sol[mask].mean()), capacity_J_K=float(model.Cm),
                H_time_constant_W_K=float(model.UA_tot+(hi+hve).max()),
                heating_enabled=bool(ha[mask].any()), cooling_enabled=bool(ca[mask].any()),
                ahu_heating_kWh=float(np.maximum(coil[mask],0).sum()*weather.timestep_seconds/3.6e6),
                ahu_cooling_kWh=float(-np.minimum(coil[mask],0).sum()*weather.timestep_seconds/3.6e6)))
        per_zone.append(rows)
        areas.append(float(input_zone.geometry.net_floor_area))
    result = [r for rows in per_zone for r in rows]
    if include_collapsed and len(per_zone)>1:
        for rows in zip(*per_zone):
            th = float(np.average([r.heating_setpoint_C for r in rows], weights=areas))
            tc = float(np.average([r.cooling_setpoint_C for r in rows], weights=areas))
            summed = {name:sum(getattr(r,name) for r in rows) for name in (
                'H_heating_W_K','H_cooling_W_K','internal_gain_W','solar_gain_W',
                'capacity_J_K','H_time_constant_W_K','ahu_heating_kWh','ahu_cooling_kWh')}
            result.append(replace(rows[0], case_id=f'{rows[0].building_id}__collapsed', zone_id='',
                representation='single_zone_collapsed_from_two_zones' if len(rows)==2 else 'single_zone_collapsed',
                heating_setpoint_C=th, cooling_setpoint_C=tc,
                heating_offset_W=sum(r.heating_offset_W+r.H_heating_W_K*(r.heating_setpoint_C-th) for r in rows),
                cooling_offset_W=sum(r.cooling_offset_W+r.H_cooling_W_K*(r.cooling_setpoint_C-tc) for r in rows),
                heating_enabled=any(r.heating_enabled for r in rows),
                cooling_enabled=any(r.cooling_enabled for r in rows), **summed))
    return result
