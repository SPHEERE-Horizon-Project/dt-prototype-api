"""Independent engine commands using a single explicit input configuration."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import pandas as pd
from dt_prototype import __version__
from dt_prototype.common.project import ProjectInputs
from dt_prototype.common.output_paths import output_component

def main(argv=None):
    parser=argparse.ArgumentParser(prog='DT-Prototype')
    parser.add_argument('engine',choices=['dynamic','monthly','simplified'])
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--model',choices=['5R1C','7R2C'])
    parser.add_argument('--zone-mode',choices=['sum','collapsed','both'])
    args=parser.parse_args(argv)
    if args.model and args.engine != 'dynamic':
        parser.error('--model applies only to the dynamic engine')
    if args.zone_mode and args.engine != 'simplified':
        parser.error('--zone-mode applies only to the simplified engine')
    project=ProjectInputs.load(args.config);out=args.output.resolve()
    if out.exists():raise FileExistsError(f'Refusing to overwrite {out}')
    district=project.preprocess()
    operation=dict(project.configuration['operating'])
    for field in ['heating_season','cooling_season']:operation[field]=tuple(operation[field])
    input_hashes = project.hashes()
    weather_id='weather_'+input_hashes['weather_epw'][:16]
    manifest=dict(name='DT-Prototype',version=__version__,engine=args.engine,status='running',timestamp_utc=datetime.now(timezone.utc).isoformat(),input_hashes=input_hashes,configuration=project.configuration,python=sys.version,dependencies={n:importlib.metadata.version(n) for n in ['numpy','pandas','matplotlib']},failed_buildings=[], building_outputs={})
    records=[]
    if args.engine=='dynamic':
        from dt_prototype.dynamic.simulation.config import SimulationConfig
        from dt_prototype.dynamic.simulation.runner import run_building
        options=dict(project.configuration['dynamic'])
        if args.model:options['model']=args.model
        config=SimulationConfig(**operation,**options)
    else:
        from dt_prototype.monthly.simulation.config import SimulationConfig
        config=SimulationConfig(**operation)
        if args.engine=='monthly':
            from dt_prototype.monthly.run import run_building
    manifest['resolved_engine_config']=asdict(config)
    out.mkdir(parents=True)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    for building in district.buildings:
        try:
            stem = output_component(building.geometry.building_id)
            manifest['building_outputs'][str(building.geometry.building_id)] = {
                'building_name': building.name,
                'details_file': f"{stem}_{'hourly' if args.engine == 'dynamic' else 'details'}.csv",
            }
            if args.engine=='dynamic':
                result=run_building(building,district.weather,config,system_templates=district.system_templates)
                result.to_csv(out/f'{stem}_hourly.csv',index_label='time')
                dt=district.weather.timestep_seconds/3600
                coils=[f'zone_{z.geometry.zone_label}_ahu_sensible_load' for z in building.zones] if len(building.zones)>1 else ['ahu_sensible_load']
                energies=pd.DataFrame({
                    'zone_heating_kWh':result.heating_load*dt/1000,
                    'zone_cooling_kWh':-result.cooling_load*dt/1000,
                    'ahu_heating_kWh':result[coils].clip(lower=0).sum(axis=1)*dt/1000,
                    'ahu_cooling_kWh':-result[coils].clip(upper=0).sum(axis=1)*dt/1000})
                monthly=energies.groupby(energies.index.to_period('M').astype(str)).sum()
            elif args.engine=='monthly':
                result=run_building(building,district.weather,config)
                result.to_csv(out/f'{stem}_details.csv',index_label='month')
                monthly=pd.DataFrame({
                    'zone_heating_kWh':result.heating_demand_kWh.to_numpy(),
                    'zone_cooling_kWh':result.cooling_demand_kWh.to_numpy(),
                    'ahu_heating_kWh':result.ahu_heating_demand_kWh.to_numpy(),
                    'ahu_cooling_kWh':result.ahu_cooling_demand_kWh.to_numpy()},
                    index=[f"{project.configuration['inputs']['calendar_year']}-{m:02d}" for m in range(1,13)])
            else:
                from dt_prototype.integration.mapping.prepared_inputs import prepare_mapping_inputs
                from dt_prototype.integration.mapping import write_reference_case_as_model3_inputs
                from dt_prototype.integration.engines.model3 import Model3Engine
                inputs=prepare_mapping_inputs(building,district.weather,config)
                mode=project.configuration['simplified']['comparison_mode']
                zone_mode=args.zone_mode or project.configuration['simplified']['zone_mode']
                manifest['zone_mode']=zone_mode;manifest['comparison_mode']=mode
                zones=[None] if len(building.zones)==1 or zone_mode=='collapsed' else [z.geometry.zone_label for z in building.zones]
                if zone_mode=='both' and len(building.zones)>1:zones=[None]+zones
                frames=[]
                for zone in zones:
                    request=write_reference_case_as_model3_inputs(out/'mapped_inputs'/stem/(output_component(zone) if zone is not None else 'aggregate'),
                        reference_results=inputs,reference_building=building,reference_weather=district.weather,
                        run_id=out.name,scenario_id='baseline',weather_id=weather_id,zone_id=zone,comparison_mode=mode,config=config)
                    frame=Model3Engine().simulate(request.request).to_frame();frames.append(frame)
                detail=pd.concat(frames,ignore_index=True)
                detail.to_csv(out/f'{stem}_details.csv',index=False)
                if zone_mode=='both' and len(building.zones)>1:detail=detail[detail.zone_id.notna()]
                names={'zone_sensible_heating_kWh':'zone_heating_kWh','zone_sensible_cooling_kWh':'zone_cooling_kWh','ahu_sensible_heating_kWh':'ahu_heating_kWh','ahu_sensible_cooling_kWh':'ahu_cooling_kWh'}
                monthly=detail.rename(columns=names).groupby('period_id')[list(names.values())].sum()
            monthly['heating_kWh']=monthly.zone_heating_kWh+monthly.ahu_heating_kWh
            monthly['cooling_kWh']=monthly.zone_cooling_kWh+monthly.ahu_cooling_kWh
            monthly['building_id']=str(building.geometry.building_id);monthly['building_name']=building.name
            monthly['zone_count']=len(building.zones)
            monthly['representation']='native_single_zone' if len(building.zones)==1 else ('single_zone_collapsed_from_two_zones' if args.engine=='simplified' and zone_mode=='collapsed' else 'sum_of_independent_zones')
            monthly.index.name='period_id';records.append(monthly.reset_index())
        except Exception as exc:
            manifest['failed_buildings'].append({'building_id':str(building.geometry.building_id),'error':str(exc)})
    if records:
        frame=pd.concat(records,ignore_index=True)
        frame['run_id']=out.name;frame['engine_id']=args.engine;frame['scenario_id']='baseline';frame['weather_id']=weather_id
        frame.to_csv(out/'monthly.csv',index=False)
        frame.groupby(['building_id','building_name'])[[c for c in frame if c.endswith('_kWh')]].sum().to_csv(out/'annual.csv')
    manifest['status']='failed' if manifest['failed_buildings'] else 'complete'
    manifest['code_hashes']={str(p.relative_to(Path(__file__).parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.rglob('*.py')}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(f'{args.engine}: {len(records)} buildings completed; {out}')
    if manifest['failed_buildings']:raise SystemExit(1)

if __name__=='__main__':main()
