"""Verify a complete single-zone input with no second-zone fields or rows."""
from pathlib import Path
import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'outputs/20260917_dt_prototype_verification_001'

def worker(kind, out):
    import numpy as np
    import pandas as pd
    package = 'dt_prototype.dynamic' if kind == 'dynamic' else 'dt_prototype.monthly'
    
    prep = importlib.import_module('dt_prototype.common.preprocessing.building_input').preprocess_district
    config = importlib.import_module(package+'.simulation.config').SimulationConfig
    qss = importlib.import_module('dt_prototype.monthly.simulation.quasi_steady_state').run_quasi_steady_state
    data = ROOT / 'data/examples'
    district = prep(out/'Test building 5_single_zone.geojson', data/'ITA_Venezia-Tessera.161050_IGDG.epw', data/'archetypes.json', data/'schedules.json')
    assert len(district.buildings) == 1
    building = district.buildings[0]
    assert len(building.zones) == 1
    assert building.zones[0].geometry.zone_label == 'single'
    checks = []
    cases = [('qss', qss, config())]
    if kind == 'dynamic':
        run = importlib.import_module(package+'.simulation.runner').run_building
        cases += [(model,run,config(model=model,plants=False,latent=False)) for model in ['5R1C','7R2C']]
    for label,run,cfg in cases:
        result = run(building,district.weather,cfg)
        result.to_csv(out/f'{kind}_{label}.csv')
        assert not any(c.startswith('zone_upper_') or c.startswith('zone_lower_') for c in result)
        if label=='qss':
            variant='dynamic_qss_extended' if kind=='dynamic' else 'semi_qss_extended'
            previous=BASELINE/kind/variant/'Test building 5.csv'
        else:
            previous=BASELINE/'dynamic'/f'{label}_ideal_extended'/'Test building 5.csv'
        old=pd.read_csv(previous,index_col=0)
        cols=result.select_dtypes(include='number').columns
        delta=float(np.max(np.abs(result[cols].to_numpy()-old[cols].to_numpy())))
        assert np.allclose(result[cols].to_numpy(),old[cols].to_numpy(),rtol=1e-12,atol=1e-7)
        checks.append(dict(engine=kind,model=label,building='Test building 5',input_zones=1,second_zone_fields_present=False,rows=len(result),max_abs_numeric_difference_vs_previous=delta,status='PASS'))
    (out/f'{kind}_checks.json').write_text(json.dumps(checks,indent=2))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--worker',choices=['dynamic','semi'])
    args=parser.parse_args();out=args.output.resolve()
    if args.worker:worker(args.worker,out);return
    out.mkdir(parents=True,exist_ok=False)
    source=ROOT/'data/examples/example_district.geojson'
    geo=json.loads(source.read_text())
    geo['features']=[f for f in geo['features'] if f['properties']['Name']=='Test building 5']
    for prop in ['Lower End Use','Upper End Use']:geo['features'][0]['properties'].pop(prop,None)
    assert geo['features'][0]['properties']['End Use']=='services'
    (out/'Test building 5_single_zone.geojson').write_text(json.dumps(geo,indent=2))
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
    for kind in ['dynamic','semi']:
        subprocess.run([sys.executable,__file__,'--worker',kind,'--output',str(out)],env=env,check=True)
    from dt_prototype.integration.model3 import model3
    import pandas as pd
    import numpy as np
    mapped=BASELINE/'seasonal_ahu/validated_inputs/model3_mapped/21/aggregate'
    assert len(pd.read_csv(mapped/'buildings.csv'))==1
    rows,_=model3.run_forward(mapped)
    assert len(rows)==12
    actual=pd.DataFrame(rows).sort_values('period_id')
    actual.to_csv(out/'simplified_single_zone.csv',index=False)
    prior=pd.read_csv(BASELINE/'seasonal_ahu/physics_model3_comparison_monthly.csv')
    prior=prior[prior.building_id==21].sort_values('period_id')
    columns=['useful_heating_kWh','useful_cooling_kWh']
    assert np.allclose(actual[columns].to_numpy(),prior[columns].to_numpy(),rtol=0,atol=1e-8)
    mapping_checks=[]
    for bid in [1,18,19,20,21]:
        p=BASELINE/f'seasonal_ahu/validated_inputs/model3_mapped/{bid}/aggregate/mapping_manifest.json'
        m=json.loads(p.read_text());collapsed='two_zone_to_single_zone' in m['approximate_mappings']
        assert collapsed == (bid!=21)
        mapping_checks.append(dict(building_id=bid,two_zone_to_single_zone=collapsed))
    checks=sum([json.loads((out/f'{kind}_checks.json').read_text()) for kind in ['dynamic','semi']],[])
    checks.append(dict(engine='Model 3 seasonal/AHU',building='Test building 5',input_building_rows=1,rows=12,status='PASS'))
    summary=dict(checks=checks,mapping_checks=mapping_checks,source_geojson_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),modified_input_description='Copied only Test building 5; removed both Upper End Use and Lower End Use; preserved End Use=services and all physical inputs',source_file_modified=False)
    (out/'verification.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
