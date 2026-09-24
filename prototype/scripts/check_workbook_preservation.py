"""Read-only comparison of the reissued XLSX with its archived source."""
from pathlib import Path
import json
import openpyxl
ROOT=Path(__file__).resolve().parents[1]
a=openpyxl.load_workbook(ROOT/'archive/previous_tools/SPREADSHEETS INTEGRATION/spreadsheets/Integrated_Seasonal_AHU_Building_Energy_Tool.xlsx')
b=openpyxl.load_workbook(ROOT/'spreadsheets/DT_Prototype_Simplified.xlsx')
assert a.sheetnames==b.sheetnames
bad=[];changes=[];formulas=0;numbers=0;objects=[]
for s in a:
    t=b[s.title]
    assert len(s._charts)==len(t._charts),(s.title,'charts')
    assert str(s.freeze_panes)==str(t.freeze_panes),(s.title,'freeze panes')
    objects.append({'sheet':s.title,'charts':len(t._charts),'freeze_panes':str(t.freeze_panes)})
    for row in s:
        for c in row:
            d=t[c.coordinate]
            if c.data_type=='f':
                formulas+=1
                if c.value!=d.value:bad.append((s.title,c.coordinate,c.value,d.value))
            elif isinstance(c.value,(int,float)):
                numbers+=1
                if c.value!=d.value:bad.append((s.title,c.coordinate,c.value,d.value))
            elif c.value!=d.value:changes.append((s.title,c.coordinate))
summary={'formula_cells_unchanged':formulas,'numeric_inputs_unchanged':numbers,'unexpected_changes':bad,'text_edits':changes,'preserved_objects':objects}
(ROOT/'outputs/20260917_dt_prototype_workbook/preservation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print({k:v for k,v in summary.items() if k not in ['text_edits','preserved_objects']})
assert not bad
