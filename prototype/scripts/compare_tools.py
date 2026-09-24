"""Reproduce the received five-building tools without modifying engine code.

Run with the project-local Python environment. Every invocation creates a new
output directory. Workers isolate independent engine executions.
"""
from __future__ import annotations
import argparse
import dataclasses
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, default=str), encoding='utf-8')

def snapshot():
    files = []
    for folder in ['src', 'tests', 'data', 'configs', 'spreadsheets']:
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files.append(ROOT/'pyproject.toml')
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}

def worker(kind, out, diagnostic=False):
    import numpy as np
    import pandas as pd

    if kind == 'dynamic':
        from dt_prototype.common.preprocessing.building_input import preprocess_district
        from dt_prototype.dynamic.simulation.config import SimulationConfig
        from dt_prototype.dynamic.simulation.runner import run_building
        from dt_prototype.monthly.simulation.quasi_steady_state import run_quasi_steady_state
    else:
        from dt_prototype.common.preprocessing.building_input import preprocess_district
        from dt_prototype.monthly.simulation.config import SimulationConfig
        from dt_prototype.monthly.run import run_building as run_quasi_steady_state
    from dt_prototype.common.project import ProjectInputs
    shared = ProjectInputs.load(ROOT/'configs/example.json')
    district = shared.preprocess()
    out.mkdir()
    district.weather.to_csv(out/'weather_hourly.csv')
    write_json(out/'input_summary.json', [dataclasses.asdict(b) for b in district.buildings])
    configs = []
    if kind == 'dynamic':
        for model in ['5R1C','7R2C']:
            for ahu in ['extended','basic']:
                configs.append((f'{model}_ideal_{ahu}', SimulationConfig(model=model,latent=False,plants=False,ahu_mode=ahu), False))
            for sizing in ['design_day','static']:
                configs.append((f'{model}_plants_latent_{sizing}', SimulationConfig(model=model,latent=True,plants=True,sizing=sizing), False))
    for ahu in ['extended','basic']:
        configs.append((f'{kind}_qss_{ahu}', SimulationConfig(ahu_mode=ahu), True))
    if diagnostic:
        configs=[]
        for model in ['5R1C','7R2C']:
            configs.append((f'{model}_ideal_latent',SimulationConfig(model=model,latent=True,plants=False),False))
            configs.append((f'{model}_plants_sensible',SimulationConfig(model=model,latent=False,plants=True),False))
    rows, timings, failures = [], [], []
    for label, cfg, qss in configs:
        target = out/label
        target.mkdir()
        write_json(target/'config.json',dataclasses.asdict(cfg))
        for b in district.buildings:
            start = time.perf_counter()
            try:
                frame = run_quasi_steady_state(b,district.weather,cfg) if qss else run_building(b,district.weather,cfg,system_templates=district.system_templates)
                frame.to_csv(target/f'{b.name}.csv')
                write_json(target/f'{b.name}_attrs.json', frame.attrs)
                labels = ['aggregate'] + ([z.geometry.zone_label for z in b.zones] if len(b.zones)>1 else [])
                for zone in labels:
                    prefix = '' if zone == 'aggregate' else f'zone_{zone}_'
                    if qss:
                        monthly = pd.DataFrame({
                            'zone_heating_kWh':frame[prefix+'heating_demand_kWh'].to_numpy(),
                            'zone_cooling_kWh':frame[prefix+'cooling_demand_kWh'].to_numpy(),
                            'ahu_heating_kWh':frame[prefix+'ahu_heating_demand_kWh'].to_numpy(),
                            'ahu_cooling_kWh':frame[prefix+'ahu_cooling_demand_kWh'].to_numpy(),
                        },index=range(1,13))
                    else:
                        dt_h = district.weather.timestep_seconds/3600
                        # Clip AHU signs per zone before aggregation; otherwise simultaneous
                        # heating and cooling in separate zones can cancel.
                        coil_cols = [f'zone_{z.geometry.zone_label}_ahu_sensible_load' for z in b.zones] if zone=='aggregate' and len(b.zones)>1 else [prefix+'ahu_sensible_load']
                        hourly = pd.DataFrame({
                            'zone_heating_kWh':frame[prefix+'heating_load']*dt_h/1000,
                            'zone_cooling_kWh':-frame[prefix+'cooling_load']*dt_h/1000,
                            'ahu_heating_kWh':frame[coil_cols].clip(lower=0).sum(axis=1)*dt_h/1000,
                            'ahu_cooling_kWh':-frame[coil_cols].clip(upper=0).sum(axis=1)*dt_h/1000,
                        })
                        monthly=hourly.groupby(hourly.index.month).sum()
                    monthly['heating_kWh']=monthly.zone_heating_kWh+monthly.ahu_heating_kWh
                    monthly['cooling_kWh']=monthly.zone_cooling_kWh+monthly.ahu_cooling_kWh
                    for month, r in monthly.iterrows():
                        rows.append(dict(building_id=b.geometry.building_id,building=b.name,variant=label,zone_id=zone,period_id=f'2023-{month:02d}',area_m2=b.geometry.net_floor_area,**r.to_dict()))
                timings.append(dict(variant=label,building=b.name,seconds=time.perf_counter()-start,warnings=frame.attrs.get('warnings',[])))
                print(label,b.name,'OK',round(time.perf_counter()-start,2),flush=True)
            except Exception as e:
                import traceback
                failures.append(dict(variant=label,building=b.name,error=repr(e),traceback=traceback.format_exc()))
                print(label,b.name,'FAILED',repr(e),flush=True)
    pd.DataFrame(rows).to_csv(out/'monthly.csv',index=False)
    write_json(out/'timings.json',timings)
    write_json(out/'failures.json',failures)
    if failures:
        raise SystemExit(1)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',choices=['dynamic','semi'])
    parser.add_argument('--output',type=Path)
    parser.add_argument('--run-id')
    parser.add_argument('--diagnostic',action='store_true')
    args=parser.parse_args()
    if args.worker:
        worker(args.worker,args.output,args.diagnostic)
        return
    run_id=args.run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_comparison')
    out=ROOT/'outputs'/run_id
    out.mkdir(parents=True,exist_ok=False)
    (out/'logs').mkdir()
    manifest=dict(run_id=run_id,started_utc=datetime.now(timezone.utc).isoformat(),status='running',python=sys.version,executable=sys.executable,git_commit=None,source_hashes=snapshot(),dependencies={d.metadata['Name']:d.version for d in importlib.metadata.distributions()},commands=[])
    write_json(out/'manifest.json',manifest)
    jobs=[]
    def launch(name,cmd,cwd=ROOT,pythonpath=None):
        env=os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE']='1'
        env['MPLBACKEND']='Agg'
        env['MPLCONFIGDIR']=str(out/'mplconfig')
        if pythonpath: env['PYTHONPATH']=str(pythonpath)
        log=open(out/'logs'/f'{name}.log','w',encoding='utf-8')
        p=subprocess.Popen([str(x) for x in cmd],cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT)
        jobs.append((name,p,log))
        manifest['commands'].append(dict(name=name,command=[str(x) for x in cmd],cwd=str(cwd)))
    # Existing suites run independently. Engines execute only after tests finish.
    for i,project in enumerate(['dynamic','monthly','integration']):
        # Keep 5P report paths below the Windows path limit. A unique run ID
        # gives a fresh temp folder without touching completed run artifacts.
        test_tmp=ROOT/'outputs'/('t'+hashlib.sha256(run_id.encode()).hexdigest()[:6]+str(i))
        launch(f'test_{i}',[sys.executable,'-m','pytest','-q','-p','no:cacheprovider','--basetemp',test_tmp,'tests/'+project],ROOT)
    launch('test_model3_pipeline',[sys.executable,'-m','dt_prototype.integration.model3.test_model3'],ROOT)
    def finish():
        for name,p,log in jobs:
            code=p.wait();log.close()
            next(c for c in manifest['commands'] if c['name']==name)['returncode']=code
            print(name,'exit',code,flush=True)
        jobs.clear()
        write_json(out/'manifest.json',manifest)
    finish()
    if any(command.get('returncode') for command in manifest['commands']):
        manifest['status'] = 'failed_tests'
        write_json(out/'manifest.json', manifest)
        raise SystemExit(1)
    for kind in ['dynamic','semi']:
        launch(kind,[sys.executable,__file__,'--worker',kind,'--output',out/kind])
    for mode in ['legacy','seasonal_ahu']:
        launch(mode,[sys.executable,'-m','dt_prototype.integration','verify-supplied-reference','--outputs-root',out,'--run-id',mode,'--comparison-mode',mode],ROOT,ROOT/'src')
    finish()
    manifest['source_changes']=[p for p,h in snapshot().items() if manifest['source_hashes'].get(p)!=h]
    manifest['completed_utc']=datetime.now(timezone.utc).isoformat()
    manifest['status']='completed_with_command_failures' if any(c.get('returncode') for c in manifest['commands']) else 'execution_complete'
    write_json(out/'manifest.json',manifest)
    print(out,flush=True)
    if any(command.get('returncode') for command in manifest['commands']):
        raise SystemExit(1)

if __name__=='__main__':main()
