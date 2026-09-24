// Read-only recalculation of the received workbook. Never export/modify it.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';
const root=process.cwd();
if (!process.argv[2]) throw new Error('Usage: node scripts/check_workbook.mjs OUTPUT_DIRECTORY');
const out=path.resolve(process.argv[2]);
await fs.mkdir(out, {recursive:true});
const source=path.join(root,'spreadsheets/DT_Prototype_Simplified.xlsx');
const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(source));
workbook.recalculate();
const sheets={};
for(const [name,range] of [['Out_Annual','A1:J14'],['Out_Monthly','A1:O157'],['Check_Reproduction','A1:J166']]) {
  sheets[name]=workbook.worksheets.getItem(name).getRange(range).values;
}
const formulaErrors=[];
for (const name of ['README','Nomenclature','Settings_General','Settings_Mass','In_Cases',
  'In_Monthly','Calc_Case','Calc_Monthly','Tested_Results','Check_Reproduction',
  'Out_Monthly','Out_Annual','Comparison']) {
  const values=workbook.worksheets.getItem(name).getUsedRange().values;
  for (let r=0;r<values.length;r++) for (let c=0;c<values[r].length;c++) {
    const value=values[r][c];
    if (typeof value==='string' && /^#(REF!|DIV\/0!|VALUE!|NAME\?|N\/A|NUM!|NULL!|SPILL!|CALC!)/.test(value)) {
      formulaErrors.push({sheet:name,row:r+1,column:c+1,value});
    }
  }
}
const checks=sheets.Check_Reproduction.filter(row=>/^\d{4}-\d{2}$/.test(String(row[1])));
const failures=checks.filter(row=>row[9]!=='PASS');
const summary={monthlyChecks:checks.length,passed:checks.length-failures.length,
  maxAbsoluteDifference_kWh:Math.max(...checks.flatMap(row=>row.slice(2,9).map(Math.abs))),
  formulaErrors,failures};
await fs.writeFile(path.join(out,'workbook_recalculated.json'),JSON.stringify({source,
  source_sha256:crypto.createHash('sha256').update(await fs.readFile(source)).digest('hex'),
  engine:'@oai/artifact-tool',summary,sheets},null,2),{flag:'wx'});
console.log(JSON.stringify(summary,null,2));
if (checks.length!==156 || failures.length || formulaErrors.length) process.exitCode=1;
