"""Generate every export from one frozen read. Raw strings remain text."""
import csv
import hashlib
import io
import json
import threading
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from app.analysis import TZ,RULE,metrics
from app.core import settings

LOCK=threading.Lock()
COLUMNS=['sample_id','water_type','samplepoint_id','samplepoint_code','samplepoint_name','samplepoint_mapping_source','samplepoint_mapping_scope','samplepoint_source_moddt','samplepoint_extracted_at','mapping_status','workitemid','paramlistid','paramlistversionid','variantid','paramid','paramtype','replicateid','dataset','display_value','source_unit','enteredvalue','transformvalue','valuestatus','trend_at','trend_date_source','collectiondt','sample_eventdt','receiveddt','sample_createdt','sample_status','selection_rule','selection_reason','numeric_value','plot_value','plot_value_rule','result_role','result_operator','result_bound','operator','bound','result_kind','plot_status','not_plotted_reason','source_key','sdidataitemid','locationid','batch_number','releasedflag','dataitem_reportflag','spec_reportflag','u_statisticflag']
def cell(value): return json.dumps(value,ensure_ascii=False,sort_keys=True) if isinstance(value,(dict,list)) else ('' if value is None else str(value))

def png(rows,manifest):
    font_path=Path(settings.png_font_path)
    if not font_path.is_file(): raise RuntimeError('Chinese PNG font missing')
    font=FontProperties(fname=str(font_path))
    with LOCK:
        fig,ax=plt.subplots(figsize=(14,7))
        fig.subplots_adjust(left=.07,right=.98,top=.82,bottom=.23)
        plotted=[r for r in rows if r['plot_status']=='plotted']
        for kind,marker,label,color in [('exact_numeric','o','精确数值','#167d9a'),('censored','v','删失结果（非实测值）','#c27c21')]:
            items=[r for r in plotted if r['result_kind']==kind]
            if items:
                ax.scatter([datetime.fromisoformat(r['trend_at']) for r in items],[float(r['plot_value']) for r in items],marker=marker,label=label,c=color,s=35)
                if kind=='censored':
                    for r in items: ax.annotate(r['display_value'],(mdates.date2num(datetime.fromisoformat(r['trend_at'])),float(r['plot_value'])),xytext=(3,5),textcoords='offset points',fontproperties=font)
        f=manifest['filter']; first=rows[0]
        ax.set_xlim(datetime.fromisoformat(f['date_from']).replace(tzinfo=TZ),datetime.fromisoformat(f['date_to']).replace(tzinfo=TZ))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d',tz=TZ)); ax.tick_params(axis='x',rotation=25)
        ax.set_title(f"{first['water_type']} · {first.get('samplepoint_code') or '现场编号缺失'} / {first.get('samplepoint_name') or '名称缺失'} / LIMS ID {first['samplepoint_id'] or '内部 ID 缺失'} · {first['paramlistid']} v{first['paramlistversionid']}\n{first['variantid']} / {first['paramid']} / {first['source_unit'] or '单位缺失'}",fontproperties=font,fontsize=15)
        ax.set_xlabel('趋势日期（Asia/Shanghai；来源见数据表）',fontproperties=font)
        ax.set_ylabel(first['source_unit'] or '单位未确认',fontproperties=font)
        ax.grid(alpha=.2)
        if plotted: ax.legend(prop=font)
        else: ax.text(.5,.5,'该组没有可绘图数值；原文见数据表',transform=ax.transAxes,ha='center',fontproperties=font)
        fig.text(.02,.035,f"未配置限度 · 原始结果 {len(rows)} 行 / 图点 {len(plotted)} 个 · {manifest['data_context'].get('timestamp_note','日期来源待核实')}\n导出 ID {manifest['export_id']} · 期间 [{f['date_from']}, {f['date_to']}) · 一致性上下文未核实",fontproperties=font,fontsize=9)
        out=io.BytesIO()
        try: fig.savefig(out,format='png',dpi=140,bbox_inches='tight')
        finally: plt.close(fig)
        return out.getvalue()

def xlsx(rows,manifest):
    book=Workbook(); notes=book.active; notes.title='导出说明'
    notes.append(['项目','说明'])
    for k,v in manifest.items(): notes.append([k,cell(v)])
    sheet=book.create_sheet('原始结果'); sheet.append(COLUMNS)
    for r in rows:
        sheet.append([cell(r.get(k)) for k in COLUMNS])
        for c in sheet[sheet.max_row]: c.data_type='s'; c.number_format='@'
    for ws in book:
        ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
        for c in ws[1]: c.font=Font(bold=True,color='FFFFFF'); c.fill=PatternFill('solid',fgColor='174E63')
        for col in ws.columns:
            letter=col[0].column_letter
            ws.column_dimensions[letter].width=28 if ws==sheet else (28 if letter=='A' else 105)
        for row in ws:
            for c in row:
                c.alignment=Alignment(vertical='top',wrap_text=True)
                if ws==notes and c.column==2: c.data_type='s'
    out=io.BytesIO(); book.save(out); return out.getvalue()

def generate(rows,ctx,payload,user):
    ctx=json.loads(json.dumps(ctx,default=str))
    manifest={'export_id':str(uuid.uuid4()),'export_kind':payload.export_kind,'generated_at':datetime.now(TZ).isoformat(),'timezone':'Asia/Shanghai','actor_id':user['sub'],'filter':payload.filter.model_dump(mode='json'),'comparison_group':payload.comparison_group,'data_context':ctx,'context_id':None,'analysis_rule_version':RULE,'graphic_rule_version':'water_chart_v2','selection_rules':sorted({r['selection_rule'] for r in rows}),'metrics':metrics(rows),'not_plotted_counts':dict(__import__('collections').Counter(r['not_plotted_reason'] for r in rows if r['plot_status']!='plotted')),'known_gaps':['当前主表映射不能证明历史有效期；系统归属未核实','限度未配置',ctx.get('timestamp_note','日期来源待核实'),'来源截止与跨请求上下文未核实'],'plot_note':'微生物限度报告值 <1 按 0 绘图；原文和阈值保留，0 不是精确实测值','csv_note':'以 = + - @ 开头的文本加单引号防公式；JSONL/Excel 保存原文'}
    files={}
    if payload.export_kind in {'chart','bundle'}: files['trend.png']=png(rows,manifest)
    if payload.export_kind in {'table','bundle'}: files['results.xlsx']=xlsx(rows,manifest)
    if payload.export_kind=='bundle':
        output=io.StringIO(newline=''); writer=csv.writer(output); writer.writerow(COLUMNS)
        for row in rows:
            values=[cell(row.get(k)) for k in COLUMNS]
            writer.writerow(["'"+v if v.lstrip().startswith(('=','+','-','@')) else v for v in values])
        files['results.csv']=output.getvalue().encode('utf-8-sig')
        files['results.jsonl']=(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)).encode()
        manifest['sha256']={k:hashlib.sha256(v).hexdigest() for k,v in files.items()}
        files['manifest.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode()
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            for name,content in files.items(): z.writestr(name,content)
        return out.getvalue(),'application/zip','water-bundle.zip'
    if payload.export_kind=='chart': return files['trend.png'],'image/png','water-trend.png'
    return files['results.xlsx'],'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','water-results.xlsx'
