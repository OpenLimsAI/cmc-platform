"""只读核对真实第一表与预览；输出计数，不输出业务单元格值、不访问数据库。"""
from pathlib import Path
from collections import Counter
from io import BytesIO
from time import monotonic
import argparse
import json, resource
from openpyxl import load_workbook
from app.services.imports.preview import preview_workbook
from app.services.imports.templates import FIRST_TABLE_TEMPLATE
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('source_dir', type=Path)
args=parser.parse_args()
files=sorted(args.source_dir.glob('*.xlsx'))
if not files:
 parser.error('指定目录没有 .xlsx 文件')
reports=[]
for path in files:
 content=path.read_bytes(); t=monotonic()
 result=preview_workbook(content,filename=path.name,template=FIRST_TABLE_TEMPLATE)
 actual={c.coordinate:c for r in result.rows for c in r.cells}
 book=load_workbook(BytesIO(content),read_only=True,data_only=False,keep_links=False)
 sheet=book['原始数据表'];sheet.reset_dimensions()
 cells=0; data_rows=[]; mismatches=0; dimensions=0
 for row in sheet.iter_rows():
  present=[c for c in row if c.value is not None and not (isinstance(c.value,str) and not c.value.strip())]
  if not present or present[0].row<7:continue
  data_rows.append(present[0].row)
  for cell in present:
   cells+=1;dimensions+=int(cell.column<=10)
   parsed=actual.get(cell.coordinate)
   if parsed is None or (parsed.value,parsed.data_type,parsed.number_format)!=(cell.value,cell.data_type,cell.number_format):mismatches+=1
 book.close()
 assert data_rows==[r.row_number for r in result.rows],path.name
 assert not mismatches,path.name
 report=dict(file=path.name,rows=len(result.rows),nonblank_cells=cells,dimension_cells=dimensions,mismatches=mismatches,structure_valid=result.structure_valid,issues=dict(Counter(i.code for i in result.issues)),seconds=round(monotonic()-t,2),peak_rss_mib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024/1024,1))
 reports.append(report);print(json.dumps(report,ensure_ascii=False),flush=True)
print(json.dumps({'files':len(reports),'rows':sum(r['rows'] for r in reports),'nonblank_cells':sum(r['nonblank_cells'] for r in reports),'mismatches':sum(r['mismatches'] for r in reports)},ensure_ascii=False))
