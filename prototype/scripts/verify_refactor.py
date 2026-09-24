"""Compare all retained numeric outputs with immutable pre-refactor evidence."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--before',type=Path,required=True)
    p.add_argument('--after',type=Path,required=True)
    p.add_argument('--before-diagnostic',type=Path,required=True)
    p.add_argument('--after-diagnostic',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    old_buildings=json.loads((args.before/'dynamic/input_summary.json').read_text(encoding='utf-8'))
    new_buildings=json.loads((args.after/'dynamic/input_summary.json').read_text(encoding='utf-8'))
    names={old['geometry']['name']:new['geometry']['name'] for old,new in zip(old_buildings,new_buildings)}
    assert [b['geometry']['building_id'] for b in old_buildings]==[b['geometry']['building_id'] for b in new_buildings]
    rows=[]
    def compare(old,new,kind):
        a=pd.read_csv(old);b=pd.read_csv(new)
        assert a.shape==b.shape,(old,a.shape,b.shape)
        assert list(a.columns)==list(b.columns),(old,'columns')
        cols=a.select_dtypes(include='number').columns
        assert list(cols)==list(b.select_dtypes(include='number').columns)
        x=a[cols].to_numpy();y=b[cols].to_numpy()
        valid=np.isfinite(x)&np.isfinite(y)
        maximum=float(np.max(np.abs(x[valid]-y[valid]))) if valid.any() else 0.
        passed=bool(np.allclose(x,y,rtol=1e-12,atol=1e-7,equal_nan=True))
        # Every nonnumeric field must agree after the requested display rename.
        for c in a.columns.difference(cols):
            original=a[c].astype(str)
            for original_name,new_name in names.items():original=original.str.replace(original_name,new_name,regex=False)
            assert original.equals(b[c].astype(str)),(old,c)
        rows.append(dict(group=kind,file=str(new.relative_to(args.after)) if new.is_relative_to(args.after) else new.name,rows=len(a),numeric_cells=x.size,max_abs_difference=maximum,passed=passed,before_sha256=hashlib.sha256(old.read_bytes()).hexdigest(),after_sha256=hashlib.sha256(new.read_bytes()).hexdigest()))
        assert passed,(old,maximum)
    for kind in ['dynamic','semi']:
        for old in sorted((args.before/kind).glob('*/*.csv')):
            compare(old,args.after/kind/old.parent.name/(names.get(old.stem,old.stem)+'.csv'),kind)
        compare(args.before/kind/'monthly.csv',args.after/kind/'monthly.csv',kind+'_summary')
    for old in sorted(args.before_diagnostic.glob('*/*.csv')):
        compare(old,args.after_diagnostic/old.parent.name/(names.get(old.stem,old.stem)+'.csv'),'dynamic_diagnostic')
    for mode in ['legacy','seasonal_ahu']:
        for file in ['physics_full_monthly.csv','physics_model3_comparison_monthly.csv']:
            # Run IDs are intentionally distinct metadata, compared separately.
            a=pd.read_csv(args.before/mode/file);b=pd.read_csv(args.after/mode/file)
            cols=a.select_dtypes(include='number').columns
            keys=['building_id','zone_id','period_id']
            a=a.sort_values(keys).reset_index(drop=True);b=b.sort_values(keys).reset_index(drop=True)
            assert a[keys].equals(b[keys])
            delta=(a[cols]-b[cols]).abs().max().max()
            assert np.allclose(a[cols],b[cols],rtol=1e-12,atol=1e-7,equal_nan=True)
            rows.append(dict(group=mode,file=file,rows=len(a),numeric_cells=len(a)*len(cols),max_abs_difference=delta,passed=True))
    result=pd.DataFrame(rows);result.to_csv(args.output/'numeric_regression.csv',index=False)
    summary={'status':'PASS','comparisons':len(rows),'numeric_cells':int(result.numeric_cells.sum()),'max_abs_difference':float(result.max_abs_difference.max()),'atol':1e-7,'rtol':1e-12,'before':str(args.before),'after':str(args.after),'scope':'All dynamic hourly numeric columns, monthly QSS numeric columns, detailed Model 3 monthly numeric columns, all toggle diagnostics; display labels mapped by unchanged stable IDs.'}
    (args.output/'verification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
