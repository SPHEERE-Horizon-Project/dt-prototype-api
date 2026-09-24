"""Prepare simplified inputs without executing any forward heat-balance solver.

Static UA, capacity, gains and scheduled airflow retain the existing reference
mapping. This contract has no heating/cooling predictions or utilisation factors.
"""
from dataclasses import dataclass
import calendar
import numpy as np
import pandas as pd
from dt_prototype.common.constants import AIR_SPECIFIC_HEAT
from dt_prototype.monthly.simulation.models.model_5r1c import Model5R1C
from dt_prototype.monthly.simulation.air_handling_unit import AirHandlingUnit

@dataclass(frozen=True)
class MappingInputRecord:
    building_id: str
    zone_id: str | None
    period_id: str
    days: int
    hours_valid: float
    outdoor_temp_C: float
    H_transmission_W_K: float
    H_ground_W_K: float
    H_ventilation_W_K: float
    H_infiltration_W_K: float
    thermal_capacity_J_K: float
    total_gain_kWh: float

@dataclass(frozen=True)
class MappingInputs:
    records: tuple[MappingInputRecord,...]
    engine_id: str='dt_prototype_inputs'
    engine_version: str='1.0'

def prepare_mapping_inputs(building,weather,config):
    """Produce the same mapping quantities as the received reference adapter."""
    index=weather.df.index;year=int(index[0].year);zones=[]
    for i,z in enumerate(building.zones):
        model=Model5R1C(building,weather,config,zone_index=i);zone=model.zone
        ground=sum(s.opaque_area*s.construction.u_value for s in zone.surfaces if s.surface_type=='GroundFloor')
        inf=zone.infiltration_mass_flow*AIR_SPECIFIC_HEAT
        vent=zone.ventilation_mass_flow*AIR_SPECIFIC_HEAT
        if zone.ahu is not None:
            ahu=AirHandlingUnit.from_dict(zone.ahu,mode=config.ahu_mode)
            ratio=1.0 if config.ahu_mode=='basic' else ahu.outdoor_air_ratio
            vent=vent*ratio*(1.0-ahu.eta_sensible)
        def mean(a):return pd.Series(a,index=index).groupby(index.month).mean().to_numpy()
        # Keep the original summation order to preserve mapped monthly gains.
        gains=zone.gains_convective+zone.gains_radiative+model.phi_sol
        gains=pd.Series(gains,index=index).groupby(index.month).sum().to_numpy()*weather.timestep_seconds/3.6e6
        zones.append((z.geometry.zone_label,model.UA_tot-ground,ground,mean(vent),mean(inf),model.Cm,gains))
    records=[]
    selections=[(None,zones)]+([(z[0],[z]) for z in zones] if len(zones)>1 else [])
    for label,selected in selections:
        for m in range(1,13):
            mask=index.month==m
            records.append(MappingInputRecord(str(building.geometry.building_id),label,f'{year:04d}-{m:02d}',
                calendar.monthrange(year,m)[1],float(mask.sum()/weather.time_steps_per_hour),float(weather.df.loc[mask,'temp_air'].mean()),
                sum(z[1] for z in selected),sum(z[2] for z in selected),sum(z[3][m-1] for z in selected),
                sum(z[4][m-1] for z in selected),sum(z[5] for z in selected),sum(z[6][m-1] for z in selected)))
    return MappingInputs(tuple(records))
