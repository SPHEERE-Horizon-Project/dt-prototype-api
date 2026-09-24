"""Build numeric, graphical and Markdown evidence from completed tool runs."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
BUILDINGS=['Test building 1','Test building 2','Test building 3','Test building 4','Test building 5']
IDS={1:'Test building 1',18:'Test building 2',19:'Test building 3',20:'Test building 4',21:'Test building 5'}
ENERGY=['zone_heating_kWh','ahu_heating_kWh','heating_kWh','zone_cooling_kWh','ahu_cooling_kWh','cooling_kWh']
LABELS={'5R1C_ideal_extended':'Dynamic 5R1C','7R2C_ideal_extended':'Dynamic 7R2C','semi_qss_extended':'Monthly QSS','model3_seasonal_ahu':'Simplified single zone collapsed','model3_seasonal_ahu_zone_sum':'Simplified zone sum','model3_legacy':'Model 3 legacy'}
PRIMARY=list(LABELS)[:-1]

def mdtable(frame):
    frame=frame.copy()
    for col in frame:
        if pd.api.types.is_numeric_dtype(frame[col]):
            frame[col]=frame[col].map(lambda x: 'n/a' if pd.isna(x) else f'{x:,.2f}')
    rows=[list(frame.columns)]+frame.astype(str).values.tolist()
    return '\n'.join(['| '+' | '.join(rows[0])+' |','| '+' | '.join(['---']*len(rows[0]))+' |']+['| '+' | '.join(r)+' |' for r in rows[1:]])

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--diagnostic',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();src=args.source.resolve();out=args.output.resolve()
    out.mkdir(exist_ok=False);(out/'figures').mkdir()
    os.environ['MPLCONFIGDIR']=str(out/'mplconfig')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    frames=[pd.read_csv(src/k/'monthly.csv') for k in ['dynamic','semi']]
    frames.append(pd.read_csv(args.diagnostic/'monthly.csv'))
    for mode in ['legacy','seasonal_ahu']:
        f=pd.read_csv(src/mode/'physics_model3_comparison_monthly.csv')
        f=f.rename(columns={'zone_sensible_heating_kWh':'zone_heating_kWh','zone_sensible_cooling_kWh':'zone_cooling_kWh','ahu_sensible_heating_kWh':'ahu_heating_kWh','ahu_sensible_cooling_kWh':'ahu_cooling_kWh','useful_heating_kWh':'heating_kWh','useful_cooling_kWh':'cooling_kWh'})
        f['zone_id']=f.zone_id.fillna('aggregate');f['building']=f.building_id.map(IDS);f['variant']='model3_'+mode
        frames.append(f[['building_id','building','variant','zone_id','period_id']+ENERGY])
        parts=f[(f.zone_id!='aggregate')|(f.building=='Test building 5')]
        sums=parts.groupby(['building_id','building','period_id'],as_index=False)[ENERGY].sum()
        sums['variant']='model3_'+mode+'_zone_sum';sums['zone_id']='aggregate';frames.append(sums)
    monthly=pd.concat(frames,ignore_index=True)
    monthly['building_id']=monthly.building_id.astype(str)
    keys=['building','variant','zone_id','period_id']
    assert not monthly.duplicated(keys).any()
    assert monthly.groupby(keys[:-1]).size().eq(12).all()
    assert np.isfinite(monthly[ENERGY]).all().all()
    assert (monthly[ENERGY]>=-1e-8).all().all()
    assert np.allclose(monthly.heating_kWh,monthly.zone_heating_kWh+monthly.ahu_heating_kWh,rtol=0,atol=1e-8)
    assert np.allclose(monthly.cooling_kWh,monthly.zone_cooling_kWh+monthly.ahu_cooling_kWh,rtol=0,atol=1e-8)
    monthly['run_id']=out.name
    monthly['scenario_id']='baseline';monthly['weather_id']='venezia_161050_igdg'
    monthly['boundary_id']=np.where(monthly.variant.str.startswith('model3_legacy'),'legacy_zone_no_separate_ahu','useful_sensible_zone_plus_ahu')
    buildings=json.loads((src/'dynamic/input_summary.json').read_text())
    zone_counts={b['geometry']['name']:len(b['zones']) for b in buildings}
    def representation(building, variant, zone):
        if zone!='aggregate':return 'individual_zone'
        if zone_counts[building]==1:return 'native_single_zone'
        if variant.startswith('model3_') and not variant.endswith('_zone_sum'):return 'single_zone_collapsed_from_two_zones'
        return 'sum_of_independent_zones'
    monthly['source_zone_count']=monthly.building.map(zone_counts)
    monthly['representation']=[representation(r.building,r.variant,r.zone_id) for r in monthly.itertuples()]
    monthly.to_csv(out/'monthly_comparison.csv',index=False)
    annual=monthly.groupby(['building_id','building','variant','zone_id','boundary_id'],as_index=False)[ENERGY].sum()
    # Correct area per zone, not repeated whole-building area from raw summaries.
    areas={}
    for b in buildings:
        name=b['geometry']['name'];areas[(name,'aggregate')]=sum(z['geometry']['net_floor_area'] for z in b['zones'])
        for z in b['zones']:areas[(name,z['geometry']['zone_label'])]=z['geometry']['net_floor_area']
    annual['area_m2']=[areas[(r.building,r.zone_id)] for r in annual.itertuples()]
    annual['source_zone_count']=annual.building.map(zone_counts)
    annual['representation']=[representation(r.building,r.variant,r.zone_id) for r in annual.itertuples()]
    for q in ['heating','cooling']:annual[q+'_kWh_m2']=annual[q+'_kWh']/annual.area_m2
    annual.to_csv(out/'annual_comparison.csv',index=False)
    totals=annual[annual.zone_id=='aggregate']
    ref=annual[annual.variant=='semi_qss_extended'].set_index(['building','zone_id'])
    diffs=[]
    for row in annual.itertuples():
        for q in ENERGY:
            rv=ref.loc[(row.building,row.zone_id),q];v=getattr(row,q)
            diffs.append(dict(building=row.building,zone_id=row.zone_id,variant=row.variant,quantity=q,reference_variant='semi_qss_extended',reference_value=rv,candidate_value=v,difference_kWh=v-rv,difference_pct=100*(v-rv)/rv if abs(rv)>1e-10 else np.nan,classification='NOT_COMPARABLE' if row.variant.startswith('model3_legacy') else 'APPROXIMATE',next_action='Review component monthly balance and operating assumptions; see report and mapped input manifest',source_inputs=f'{src.name}/'+('validated inputs in seasonal_ahu or legacy' if row.variant.startswith('model3') else 'dynamic/input_summary.json')))
    difference=pd.DataFrame(diffs);difference.to_csv(out/'annual_differences.csv',index=False)
    metrics=[]
    for (building,variant,zone),f in monthly.groupby(['building','variant','zone_id']):
        rr=monthly[(monthly.building==building)&(monthly.variant=='semi_qss_extended')&(monthly.zone_id==zone)].set_index('period_id')
        f=f.set_index('period_id').loc[rr.index]
        for q in ['heating_kWh','cooling_kWh']:
            delta=f[q]-rr[q];maxmonth=delta.abs().idxmax()
            metrics.append(dict(building=building,variant=variant,zone_id=zone,quantity=q,reference_variant='semi_qss_extended',monthly_RMSE_kWh=np.sqrt(np.mean(delta**2)),monthly_MAE_kWh=delta.abs().mean(),max_abs_monthly_difference_kWh=delta.abs().max(),max_difference_period=maxmonth,annual_difference_kWh=delta.sum()))
    pd.DataFrame(metrics).to_csv(out/'monthly_discrepancy_metrics.csv',index=False)
    # Independent workbook evaluation compared by stable case/period keys.
    book=json.loads((src/'workbook_recalculated.json').read_text())['sheets']['Out_Monthly']
    w=pd.DataFrame(book[1:],columns=book[0]);w['building_id']=w.building_id.astype(str)
    mm=monthly[monthly.variant=='model3_seasonal_ahu']
    joined=w.merge(mm,on=['building_id','zone_id','period_id'],validate='one_to_one')
    assert len(joined)==156
    checks={}
    for wc,pc in [('useful_heating_kWh','heating_kWh'),('useful_cooling_kWh','cooling_kWh')]:
        checks[wc+'_max_abs_difference']=float((joined[wc]-joined[pc]).abs().max())
        assert checks[wc+'_max_abs_difference']<1e-7
    joined.to_csv(out/'workbook_reconciliation.csv',index=False)
    qss=monthly[monthly.variant.isin(['semi_qss_extended','dynamic_qss_extended'])].pivot(index=['building','zone_id','period_id'],columns='variant',values=ENERGY)
    checks['dynamic_qss_vs_standalone_max_abs_kWh']=float(max((qss[q]['semi_qss_extended']-qss[q]['dynamic_qss_extended']).abs().max() for q in ENERGY))
    # Supplied historical comparison: check its rounded annual numbers, not prose claims.
    historical=[]
    for line in (ROOT/'annual_side_by_side_outputs.md').read_text().splitlines():
        if not re.match(r'\| \d+ \|',line):continue
        c=[v.strip() for v in line.strip('|').split('|')]
        name=c[1];zone='aggregate' if c[2]=='building_aggregate' else c[2].split(':')[1]
        for variant,indices in [('semi_qss_extended',(3,6)),('model3_legacy',(4,7))]:
            row=annual[(annual.building==name)&(annual.zone_id==zone)&(annual.variant==variant)].iloc[0]
            for q,ix in zip(['heating_kWh','cooling_kWh'],indices):
                value=float(c[ix].replace(',',''));historical.append(dict(building=name,zone_id=zone,variant=variant,quantity=q,historical_rounded_kWh=value,fresh_kWh=row[q],difference_kWh=row[q]-value))
    historical=pd.DataFrame(historical);historical.to_csv(out/'historical_table_reconciliation.csv',index=False)
    checks['historical_rounded_table_max_abs_kWh']=float(historical.difference_kWh.abs().max())
    # Diagnostic isolation: latent alone and sizing alone must not be conflated with emitter physics.
    for model in ['5R1C','7R2C']:
        for suffix,a,b in [('latent_ideal',model+'_ideal_extended',model+'_ideal_latent'),('latent_plants',model+'_plants_latent_design_day',model+'_plants_sensible'),('sizing_sensible',model+'_plants_latent_design_day',model+'_plants_latent_static')]:
            x=monthly[monthly.variant==a].set_index(['building','zone_id','period_id'])[ENERGY]
            y=monthly[monthly.variant==b].set_index(['building','zone_id','period_id'])[ENERGY]
            checks[model+'_'+suffix+'_max_abs_kWh']=float((x-y).abs().max().max())
    carriers=[]
    for folder in (src/'dynamic').iterdir():
        if not folder.is_dir() or '_plants_' not in folder.name:continue
        for name in BUILDINGS:
            f=pd.read_csv(folder/f'{name}.csv')
            carriers.append(dict(building=name,variant=folder.name,**{c+'_kWh':f[c].sum()/1000 for c in ['gas','electric_plant','electric_appliances','district_heat','other_fuel','dhw_demand','pv_production','solar_thermal_production'] if c in f}))
    carriers=pd.DataFrame(carriers);carriers.to_csv(out/'dynamic_carriers_and_other_enduses.csv',index=False)
    # Quantify shared AHU operation outside zone availability.
    ahu=monthly[(monthly.variant=='semi_qss_extended')&(monthly.zone_id=='aggregate')].copy()
    ahu['month']=ahu.period_id.str[-2:].astype(int)
    outside=ahu[ahu.month.isin([5,6,7,8,9])].groupby('building',as_index=False)[['ahu_heating_kWh']].sum()
    outside.to_csv(out/'ahu_heating_outside_zone_heating_season.csv',index=False)
    # Selected component/mass mapping differences.
    f=pd.read_csv(src/'seasonal_ahu/physics_full_monthly.csv');g=pd.read_csv(src/'seasonal_ahu/physics_model3_comparison_monthly.csv')
    inter=f.merge(g,on=['building_id','zone_id','period_id'],suffixes=('_reference','_simplified'),validate='one_to_one')
    inter.to_csv(out/'intermediate_reference_vs_simplified.csv',index=False)
    # Export publication-friendly plots, using distinct scales for each building.
    colors=['#2457A7','#6C4198','#202A35','#D27C28','#278564']
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(5,2,figsize=(13,16))
    for i,name in enumerate(BUILDINGS):
        for j,q in enumerate(['heating_kWh','cooling_kWh']):
            ax=axes[i,j]
            for v,c in zip(PRIMARY,colors):
                s=monthly[(monthly.building==name)&(monthly.zone_id=='aggregate')&(monthly.variant==v)].sort_values('period_id')
                ax.plot(range(1,13),s[q]/1000,label=LABELS[v],color=c,linewidth=1.7,linestyle='--' if 'zone_sum' in v else '-')
            ax.set_title(name+' — '+q.split('_')[0]);ax.set_ylabel('MWh/month');ax.set_xticks([1,3,5,7,9,11]);ax.grid(alpha=.18)
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',ncol=3,bbox_to_anchor=(.5,.99));fig.tight_layout(rect=[0,0,1,.95]);fig.savefig(out/'figures/monthly_profiles.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    for j,q in enumerate(['heating_kWh','cooling_kWh']):
        ax=axes[j]
        for k,(v,c) in enumerate(zip(PRIMARY,colors)):
            s=totals[totals.variant==v].set_index('building').loc[BUILDINGS,q]
            r=totals[totals.variant=='semi_qss_extended'].set_index('building').loc[BUILDINGS,q]
            ax.bar(np.arange(5)+(k-2)*.15,100*s/r,width=.15,color=c,label=LABELS[v])
        ax.axhline(100,color='#555',lw=.8);ax.set_xticks(range(5),BUILDINGS,rotation=20);ax.set_ylabel('% of monthly QSS');ax.set_title(q.split('_')[0].capitalize());ax.grid(axis='y',alpha=.15)
    fig.legend(handles,labels,loc='upper center',ncol=3);fig.tight_layout(rect=[0,0,1,.85]);fig.savefig(out/'figures/annual_relative.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(10,8))
    for j,q in enumerate(['heating_kWh','cooling_kWh']):
        dd=difference[(difference.zone_id=='aggregate')&(difference.quantity==q)&difference.variant.isin(PRIMARY)].pivot(index='building',columns='variant',values='difference_pct').loc[BUILDINGS,PRIMARY]
        ax=axes[j];im=ax.imshow(dd,cmap='RdBu_r',vmin=-30,vmax=30,aspect='auto')
        for i in range(5):
            for k in range(5):ax.text(k,i,f'{dd.iloc[i,k]:+.1f}%',ha='center',va='center',color='white' if abs(dd.iloc[i,k])>20 else '#111')
        plot_labels=[LABELS[v].replace('single zone collapsed','single zone\ncollapsed') for v in PRIMARY]
        ax.set_yticks(range(5),BUILDINGS);ax.set_xticks(range(5),plot_labels,rotation=12,fontsize=9);ax.set_title(q.split('_')[0].capitalize()+' difference from monthly QSS')
    fig.subplots_adjust(left=.18,right=.82,hspace=.45,bottom=.12)
    color_axis=fig.add_axes([.87,.23,.025,.54])
    fig.colorbar(im,cax=color_axis,label='Candidate minus QSS (%)');fig.savefig(out/'figures/annual_differences.png',dpi=180);plt.close(fig)
    # Report tables.
    def annual_table(q,variants=PRIMARY):
        t=totals[totals.variant.isin(variants)].pivot(index='building',columns='variant',values=q).loc[BUILDINGS,variants]/1000
        return mdtable(t.rename(columns=LABELS).reset_index().rename(columns={'building':'Building'}))
    def delta_table(q):
        t=difference[(difference.zone_id=='aggregate')&(difference.quantity==q)&difference.variant.isin(PRIMARY)].pivot(index='building',columns='variant',values='difference_pct').loc[BUILDINGS,PRIMARY]
        return mdtable(t.rename(columns=LABELS).reset_index())
    component=totals[totals.variant.isin(PRIMARY[:3])][['building','variant']+ENERGY].copy()
    component['variant']=component.variant.map(LABELS)
    component[ENERGY]=component[ENERGY]/1000
    component=component.rename(columns={c:c.replace('_kWh','_MWh') for c in ENERGY})
    zones=annual[(annual.zone_id!='aggregate')&annual.variant.isin(['semi_qss_extended','model3_seasonal_ahu','5R1C_ideal_extended','7R2C_ideal_extended'])].copy()
    zt=zones.pivot(index=['building','zone_id'],columns='variant',values=['heating_kWh','cooling_kWh'])/1000
    zt.columns=[q.split('_')[0]+' '+LABELS[v] for q,v in zt.columns]
    oper=totals[totals.variant.str.contains('plants_latent')][['building','variant','heating_kWh','cooling_kWh']].copy();oper[['heating_kWh','cooling_kWh']]/=1000;oper.columns=['Building','Option','Heating MWh','Cooling MWh']
    checks['rows_monthly']=len(monthly);checks['rows_annual']=len(annual);checks['buildings']=BUILDINGS
    (out/'verification_checks.json').write_text(json.dumps(checks,indent=2))
    portfolio=totals[totals.variant.isin(PRIMARY)].groupby('variant')[['heating_kWh','cooling_kWh']].sum().loc[PRIMARY]/1000;portfolio.index=portfolio.index.map(LABELS)
    legacy=annual_table('heating_kWh',['semi_qss_extended','model3_legacy'])+'\n\n'+annual_table('cooling_kWh',['semi_qss_extended','model3_legacy'])
    report=fr'''# DT-Prototype: five-building comparison

Run date: 2026-09-17. All values below come from fresh executions of the supplied
code and current bundled cases. Energy is **useful sensible demand**, positive
magnitudes, in **MWh/year** unless stated otherwise. Heating and cooling each
include zone demand plus separate sensible AHU demand, except the explicitly
labelled legacy Model 3 comparison. No calibration was performed and no measured
building data were used. These results support comparison and software
verification, not empirical validation or a ranking of physical accuracy.

## 1. Main findings

- Heating agreement is appreciably better than cooling agreement. Relative to
  monthly QSS, ideal dynamic 5R1C heating is -6.8% to +3.1%, and 7R2C heating is
  -0.6% to +5.6%. Dynamic cooling is systematically lower: 5R1C -7.2% to -19.4%,
  and 7R2C -9.7% to -23.4%. These differences are material for cooling decisions.
- The seasonal/AHU simplified model follows monthly QSS more closely when each
  zone is calculated before aggregation. Collapsing zones changes the outcome;
  it is an additional approximation, not an alternative way of summing results.
- Standalone monthly and dynamic-QSS compatibility routes use the same retained
  monthly solver. Agreement verifies routing, not independent physics or empirical validation.
- Basic and extended AHU options give identical sensible results on these
  particular examples. This dataset does not exercise every distinction between
  the two algorithms.
- The reissued workbook recalculates and matches fresh seasonal/AHU Python
  outputs across all 156 case-month rows to less than 1e-7 kWh. The older root
  Markdown table is also reproduced, but represents the **legacy** mode.

## 2. Execution and comparability

All engines now consume one shared GeoJSON, EPW, envelope and schedule dataset.
Test building 1, Test building 2, Test building 3 and Test building 4 have independent lower/upper zones; Test building 5 has
one zone. The weather has 8,760 hourly records on the package's synthetic 2023
calendar. Test building 5 uses 36 m total height and 12 floors. Historical figures using 3 m total height have a different geometry boundary.

The primary dynamic variants use `plants=False`, `latent=False`, hourly steps,
extended AHU, received seasons (heating days 288–120, cooling 152–273), and the
received initial 15 degC state. QSS retains its corresponding defaults. Dynamic
W are integrated as W × timestep hours / 1000. Cooling negatives become positive
magnitudes; zone and AHU heating/cooling are bucketed per zone before summation.
This prevents simultaneous loads in different zones cancelling each other.

The Model 3 seasonal/AHU calculation uses reference-derived monthly gains and UA,
annual-mean airflow, active setpoints, a nearest mass class and monthly AHU
conditions. It has independent balance equations but does not independently
rebuild raw geometry, schedules or solar gains. Two variants are retained:
`Simplified single zone collapsed` solves one equivalent building; `Simplified zone sum`
sums the independent lower/upper results (Test building 5 is unchanged).

The collapsed label applies to the four two-zone buildings. **Test building 5 is a native
single-zone case:** its value in that comparison column is an ordinary simplified
single-zone calculation, with no collapse. It needs no second zone, dummy inputs
or zero-area zone. The numeric tables explicitly distinguish `native_single_zone`,
`single_zone_collapsed_from_two_zones`, `individual_zone` and
`sum_of_independent_zones` in the `representation` column.

The simplified Model 3 engine itself solves one zone per input case. The
integration workflow supports two-zone buildings by running that engine for
each zone and summing the outputs. Its collapsed alternative combines both
zones' inputs before the single-zone solve. Simply omitting a second zone from
an originally two-zone building would not perform this collapse: the mapping
must preserve the whole building's areas, heat-transfer boundary and gains.

## 3. Annual heating

{annual_table('heating_kWh')}

Candidate minus monthly QSS, percent of monthly QSS:

{delta_table('heating_kWh')}

## 4. Annual cooling

{annual_table('cooling_kWh')}

Candidate minus monthly QSS, percent of monthly QSS:

{delta_table('cooling_kWh')}

![Annual model differences](figures/annual_differences.png)

The percentage denominator is QSS throughout these tables. A positive value
means the candidate predicts more. These are model differences, not metered
residuals, calibrated-model errors, or evidence that QSS is correct.

Portfolio totals (sum of five actual buildings, without double-counting zones):

{mdtable(portfolio.reset_index().rename(columns={'variant':'Model','heating_kWh':'Heating MWh','cooling_kWh':'Cooling MWh'}))}

Test building 5 dominates portfolio heating; the portfolio can conceal building-specific
disagreement. Review all five buildings and zone rows before selecting a method.

## 5. Zone versus AHU contribution

The following separates each total into its two useful-demand components.

{mdtable(component)}

Monthly profiles expose differences which an annual total can conceal. Numeric
monthly differences, RMSE, MAE, largest differing month and annual bias against
QSS are saved in `monthly_discrepancy_metrics.csv`. These statistics measure
cross-model discrepancy, not validation accuracy.

![Monthly demand profiles](figures/monthly_profiles.png)

## 6. Zone-level results

Individual-zone totals, MWh/year:

{mdtable(zt.reset_index())}

For the simplified model, summing zones is the appropriate comparison with the
received dynamic/QSS aggregation convention. The collapsed case remains useful
as an explicitly different screening scenario. Nonlinear utilisation factors,
different schedules, mass-class mapping and area-weighted setpoints mean the
collapsed result need not equal the independent-zone sum.

## 7. Dynamic modelling options and systems

The complete executions include both RC networks, basic/extended AHU, ideal
sensible loads, latent+plant runs, and design-day/static plant sizing. Additional
diagnostic runs toggle latent and plants separately. All hourly files and exact
configurations are retained.

Plant-enabled sensible totals (latent energy is excluded from these columns):

{mdtable(oper)}

The diagnostic runs show that enabling latent alone leaves sensible demand
unchanged for these inputs, whether plants are enabled or disabled. In contrast,
enabling plants changes the radiative/convective emission split used in the RC
solver. Consequently it can change useful sensible demand as well as carrier
consumption. For example, Test building 4 7R2C heating changes from 1,224.84 MWh
in ideal mode to 1,270.61 MWh with the configured system; Test building 3 moves in the opposite
direction, from 314.57 to 298.45 MWh. This is evidenced by isolated toggles and
`runner.py` passing system `sigma()` values into each zone solver.

Static versus design-day sizing does not change sensible demand in these
unlimited-load runs; sizing affects plant conversion/capacity parameters.
For Test building 5, design-day versus static sizing changes annual gas from 3,918.66 to
4,161.88 MWh in 5R1C (+6.2%) and from 4,009.75 to 4,211.86 MWh in 7R2C (+5.0%).
This deserves a separate systems review even though the sensible totals match.
`dynamic_carriers_and_other_enduses.csv` contains the actual gas, plant electricity,
appliances, DHW and renewable quantities. These are different boundaries and
must not be added indiscriminately or compared to useful heating/cooling.
The current runner does not expose a clean end-use-by-carrier allocation, so
whole-plant electricity is not labelled as cooling electricity here.

Natural ventilation, DHW storage and solar technologies are retained where
configured. No artificial capacity limits, altered schedules, sub-hourly
convergence sweep, warm-up cycle, weather perturbation, calibration or scenario
parameter sweep was introduced. Those are additional studies, not implicit
variants of this benchmark.

## 8. Legacy table and spreadsheet verification

The original `annual_side_by_side_outputs.md` is reproduced across 13 cases and
both energy terms (maximum difference from its rounded numbers:
{checks['historical_rounded_table_max_abs_kWh']:.5f} kWh). Its aggregate tables are:

Heating MWh, then cooling MWh:

{legacy}

Legacy Model 3 has no separate AHU term, does not apply the newer seasonal/AHU
boundary, and retains its historical cooling ratio equation. Therefore these
rows are `NOT_COMPARABLE` for strict total-boundary verification; they remain
visible for continuity with the user's example. Large legacy deviations are
not evidence against the seasonal/AHU workbook.

The actual workbook is the newer seasonal/AHU implementation. A read-only
in-memory recalculation with artifact-tool was compared to newly executed Python
using building/zone/period keys. Maximum monthly heating difference is
{checks['useful_heating_kWh_max_abs_difference']:.3g} kWh; cooling is
{checks['useful_cooling_kWh_max_abs_difference']:.3g} kWh. This verifies the
translation for supplied inputs. It is not a recalculation in Microsoft Excel,
an independent weather model, or empirical validation. The reissued workbook changes labels only; its formulas and numeric inputs are preserved.

## 9. Problems and development gaps

| Priority | Finding and evidence | Consequence and next action |
|---|---|---|
| High | Cooling differs materially across detail levels, especially Test building 5 and Test building 4. See annual, monthly and component tables. | Preserve hourly/zone/AHU diagnostics; compare return-air assumptions, time-varying gains and controls, utilisation factors and mass. Do not tune tolerances or claim accuracy from inter-model closeness. |
| Resolved | Aggregate rows previously obscured zone representation. | Explicit representation and variant columns distinguish native single zone, collapsed and zone sum. |
| High | `plants=True` changes emitter splits and hence useful demand, not only energy conversion. | Decouple emitter physics from carrier conversion in a future adapter. Expose emitter assumptions in configuration and result manifests. Preserve existing behaviour with tests before refactoring. |
| High | AHU heat remains nonzero outside the zone heating season. Both dynamic and QSS compute AHU conditioning whenever scheduled airflow is present; season selects supply mode rather than turning the AHU off. | Confirm intended operating semantics with the building operator. Introduce explicit AHU availability if needed; do not silently zero current totals. |
| High | No measured data for these five buildings, no untouched validation period, and missing original external benchmark artifacts. | Recover meter boundaries, quality flags and observations; distinguish regression protection, independent reference validation and empirical validation. |
| High | Legacy `model3.py:636` calibrates on every metered row; the newer integration 5P fitter explicitly separates calibration/validation flags. | Keep legacy calibration only as a compatibility baseline. Route future real-meter calibration through the integration fitter and its leakage tests. No measured fit was used for the five-building results here. |
| Medium | Dynamic output exposes signed net AHU sensible load but omits the separate heating/cooling coil loads used internally for plants. | Export per-zone coil heat/cool and latent terms to avoid loss of reheat/dehumidification information on other AHU settings. Current sensible comparison is restricted to the supplied non-humidity-controlled cases. |
| Medium | A long-path integration run fails while writing the 5P SVG; the same suite passes with shorter paths. | Shorten/hash output filenames, preserve full identifiers in manifests, and add a Windows long-path regression case. This is an I/O portability defect, not a demonstrated physics failure. |
| Resolved | Duplicate monthly packages and input copies were consolidated. | Shared inputs and one monthly solver; dynamic and Model 3 balances remain independent. See the refactor verification report. |
| Medium | EPW reader assumes 8,760 records and a synthetic non-leap calendar; validation evidence is limited for leap years, missing/sentinel values and all solar paths. | Make calendar/hour convention explicit and add independent raw-record, missing-data and solar reference checks. |
| Medium | QSS ground is a 0.7-U outdoor-temperature approximation; mass, airflow and gains are further simplified in Model 3. | Record method IDs and mappings; test alternatives as declared scenarios rather than changing baseline assumptions. |
| Medium | Dynamic initial state is 15 degC with no explicit warm-up here. In two-zone runs configured capacity limits are passed to each zone solver. | Test initial-state sensitivity and clarify whether capacity limits mean per-zone or shared building plant. Do not interpret unlimited-load runs as evidence of capacity adequacy. |
| Medium | Exact upstream commits, full standard edition/clause mapping, Model 3 licence and standalone licence text are incomplete. README versions and historical links are stale. | Recover provenance and licence chain; fix documentation before distribution/compliance claims. |
| Open | The common CLI isolates per-building failures and writes status manifests; 10/100/1,000-building performance and resumability remain unverified. | Benchmark and add resumability before portfolio production. |

AHU heating during May–September (zone heating unavailable), kWh:

{mdtable(outside)}

This is an observed shared operating assumption. It is not independently
established as a bug. Similarly, the detailed causes of every dynamic/QSS cooling
gap have not been isolated by controlled physics ablations; the report names
the relevant differences without claiming a complete causal attribution.
Current architecture, retained gaps and migration evidence are documented under `docs/`.

## 10. Verification status

| Check | Result |
|---|---|
| Dynamic retained suite | 139 passed; unavailable external-fixture test archived |
| Standalone QSS original suite | 1 passed (all five annual cases) |
| Integration retained suite | 23 passed; duplicate monthly regression removed |
| Pre-refactor long-path diagnostic | 23 passed, 1 file-path failure in 5P reporting; use short output paths |
| Final consolidated suite | 169 passed |
| Independent launchers | Six configurations passed against the numerical benchmark |
| Legacy standalone smoke | PASS |
| Model 3 immutable reference CSVs | Byte-for-byte reproduction passes in integration suite |
| Core input consistency | One shared input dataset and manifest |
| Refactor numerical regression | See refactor verification report; original evidence is archived |
| Dynamic QSS versus standalone QSS monthly maximum | {checks['dynamic_qss_vs_standalone_max_abs_kWh']:.3g} kWh |
| Workbook versus fresh seasonal/AHU Python | 156 rows, heating/cooling below 1e-7 kWh |
| Comparison data | Unique keys, 12 months per case, finite nonnegative loads, zone+AHU identities |

Earlier preliminary executions and their failures are retained in the archive.
The current consolidated suite passed all 169 tests. All six independent
launcher configurations reproduce the benchmark within 3e-11 kWh. The full
before/after numerical comparison covers 19,642,320 values and is recorded in
`docs/refactor_verification.md`. Short output paths remain appropriate for
the retained 5P reporting implementation.

## 11. Next step toward one Digital Twin

1. Maintain the frozen input/result regression evidence. Recover missing
   licences, upstream versions and original benchmark artifacts.
2. Extend the shared input contract in `docs/data_contracts.md` while preserving
   the now-independent dynamic, monthly and simplified launchers. Improve
   schema coverage and explicit emitter/AHU/energy-boundary configuration.
3. Resolve AHU operating seasons and production zone topology using actual
   building operating information. First investigate cooling and component
   differences on Test building 5 and Test building 4; keep Test building 1/Test building 2/Test building 3 zone cases.
4. Build a transparent system/carrier layer with end-use allocations, then
   connect quality-controlled meters. Fit only declared calibration periods;
   assess untouched validation observations and use 5P as a diagnostic bridge.
5. Add input validation, per-building failures, resumability and portfolio
   benchmarks before a polished unified notebook/UI workflow.

The present comparison does not justify choosing an engine solely because it
matches another. The selection should follow intended decision, required time
resolution, available inputs and independent validation evidence.

## 12. Files and reproduction

Primary execution: `{src.name}`. Additional toggle diagnostics:
`{args.diagnostic.name}`. This report directory contains annual/monthly numeric
tables, component differences, historical and workbook reconciliation, source
hashes and saved figures. The raw execution contains every hourly dynamic
series, configuration, mapped Model 3 input, weather artifact and test log.

From the project root, use the prepared `.venv-comparison` interpreter:

```powershell
.\.venv-comparison\Scripts\python.exe scripts/compare_tools.py --run-id NEW_UNIQUE_RUN_ID
.\.venv-comparison\Scripts\python.exe scripts/compare_tools.py --worker dynamic --diagnostic --output outputs/NEW_DIAGNOSTIC_ID
# The runner uses a short, unique basetemp beneath outputs for Windows.
# Recalculate workbook read-only using the bundled Node runtime:
node scripts/check_workbook.mjs outputs/NEW_UNIQUE_RUN_ID
.\.venv-comparison\Scripts\python.exe scripts/build_comparison_report.py --source outputs/NEW_UNIQUE_RUN_ID --diagnostic outputs/NEW_DIAGNOSTIC_ID --output outputs/NEW_REPORT_ID
```

Always use a new run/report ID. The exact commands, versions, source and result
hashes accompany the artifacts. The prepared environment inherits the bundled
Python's NumPy/pandas; the manifest records this rather than claiming a fully
isolated or universally pinned installation.
'''
    (out/'comparison_report.md').write_text(report,encoding='utf-8')
    # Simple portable HTML rendering of the generated Markdown (tables/images/code).
    def render(text):
        lines=text.splitlines();parts=[];i=0;code=False
        while i<len(lines):
            line=lines[i]
            if line.startswith('```'):
                parts.append('</pre>' if code else '<pre>');code=not code;i+=1;continue
            if code:parts.append(html.escape(line)+'\n');i+=1;continue
            if line.startswith('|'):
                parts.append('<div class="table"><table>');first=True
                while i<len(lines) and lines[i].startswith('|'):
                    row=lines[i]
                    if not re.match(r'^\|[\s|:\-]+\|$',row):
                        tag='th' if first else 'td';parts.append('<tr>'+''.join(f'<{tag}>'+html.escape(c.strip())+f'</{tag}>' for c in row.strip('|').split('|'))+'</tr>');first=False
                    i+=1
                parts.append('</table></div>');continue
            if line.startswith('#'):
                n=len(line)-len(line.lstrip('#'));parts.append(f'<h{n}>'+html.escape(line[n:].strip())+f'</h{n}>')
            elif line.startswith('!['):
                m=re.match(r'!\[(.*?)\]\((.*?)\)',line);parts.append(f'<img alt="{html.escape(m[1])}" src="{html.escape(m[2])}">')
            elif line.strip():parts.append('<p>'+html.escape(line)+'</p>')
            i+=1
        return '\n'.join(parts)
    (out/'comparison_report.html').write_text('<!doctype html><html><meta charset="utf-8"><title>Five-building model comparison</title><style>body{font:16px/1.55 system-ui,sans-serif;color:#202a35;max-width:1300px;margin:40px auto;padding:0 30px}h1{font-size:32px}h2{margin-top:48px;border-bottom:1px solid #ddd;padding-bottom:8px}p{margin:.35em 0}table{border-collapse:collapse;font-size:13px;width:100%;margin:20px 0}th{text-align:left;background:#e9edf2}td,th{padding:9px;border-bottom:1px solid #ddd}td:not(:first-child){text-align:right}.table{overflow:auto}img{width:100%;height:auto}pre{background:#f2f4f6;padding:18px;overflow:auto}@media print{body{max-width:none;padding:0}h2{break-after:avoid}tr,img{break-inside:avoid}}</style><body>'+render(report)+'</body></html>',encoding='utf-8')
    evidence={}
    for base in [src,args.diagnostic.resolve()]:
        for f in base.rglob('*'):
            if f.is_file() and 'test_tmp' not in str(f) and 'mplconfig' not in str(f):evidence[str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
    manifest=dict(report_id=out.name,created_utc=datetime.now(timezone.utc).isoformat(),source_run=str(src),diagnostic_run=str(args.diagnostic),scope='comparison; no metered validation',checks=checks,evidence_hashes=evidence,report_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),received_source_changes=json.loads((src/'manifest.json').read_text())['source_changes'])
    manifest['artifact_hashes']={str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for f in out.rglob('*') if f.is_file() and 'mplconfig' not in f.parts}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(checks,indent=2));print(out)

if __name__=='__main__':main()
