"""Execute every independent launcher and compare its energies to the benchmark."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
ENERGY=['zone_heating_kWh','zone_cooling_kWh','ahu_heating_kWh','ahu_cooling_kWh','heating_kWh','cooling_kWh']

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    baseline=pd.read_csv(args.report/'monthly_comparison.csv')
    cases=[('run_dynamic.py','dynamic_5R1C',['--model','5R1C'],'5R1C_ideal_extended'),('run_dynamic.py','dynamic_7R2C',['--model','7R2C'],'7R2C_ideal_extended'),('run_monthly.py','monthly',[],'semi_qss_extended'),('run_simplified.py','simplified_sum',['--zone-mode','sum'],'model3_seasonal_ahu_zone_sum'),('run_simplified.py','simplified_collapsed',['--zone-mode','collapsed'],'model3_seasonal_ahu'),('run_simplified.py','simplified_both',['--zone-mode','both'],'model3_seasonal_ahu_zone_sum')]
    checks=[]
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONUTF8']='1'
    for launcher,label,options,variant in cases:
        subprocess.run([sys.executable,str(ROOT/'runners'/launcher),'--config',str(ROOT/'configs/example.json'),'--output',str(out/label),*options],cwd=ROOT,env=env,check=True)
        actual=pd.read_csv(out/label/'monthly.csv')
        expected=baseline[(baseline.variant==variant)&(baseline.zone_id=='aggregate')]
        merged=actual.merge(expected,on=['building_id','period_id'],validate='one_to_one',suffixes=('_new','_old'))
        assert len(merged)==60
        delta=max(float((merged[c+'_new']-merged[c+'_old']).abs().max()) for c in ENERGY)
        for c in ENERGY:assert np.allclose(merged[c+'_new'],merged[c+'_old'],rtol=1e-12,atol=1e-7)
        checks.append({'entry_point':f'runners/{launcher}','variant':label,'rows':60,'max_abs_kWh':delta,'status':'PASS'})
    (out/'verification.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print(json.dumps(checks,indent=2))
if __name__=='__main__':main()
