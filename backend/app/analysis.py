"""Versioned, conservative display rules. Never replace source strings."""
import base64
import calendar
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field, model_validator

TZ = ZoneInfo('Asia/Shanghai')
RULE = 'water_dashboard_analysis_v1'
OVERVIEW_RULE = 'water_overview_counts_v1'
WATER_CARDS = (('WFI','注射用水'),('PW','纯化水'),('PS','纯蒸汽'))
SOURCE = 'gmp_labvantage'
WATERS = ('纯化水','注射用水','纯蒸汽')
RULES = ('water_system_v1','water_conductivity_method1_numeric_v1')
KEY = ('source_system','sdcid','keyid1','keyid2','keyid3','paramlistid','paramlistversionid','variantid','dataset','paramid','paramtype','replicateid')
GROUP = ('samplesubtypeid','samplepointid','workitemid','paramlistid','paramlistversionid','variantid','paramid','paramtype','unit')
NUM = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'

def today() -> date: return datetime.now(TZ).date()
def months_before(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 - months
    year, month = divmod(index, 12)
    return date(year, month+1, min(day.day,calendar.monthrange(year,month+1)[1]))

class FilterSpec(BaseModel):
    model_config = {'extra': 'forbid'}
    water_type: Literal['纯化水','注射用水','纯蒸汽'] | None = None
    samplepoint_id: str | None = Field(None,max_length=200)
    samplepoint_code: str | None = Field(None,min_length=1,max_length=200)
    workitem_id: str | None = Field(None,max_length=300)
    paramlist_id: str | None = Field(None,max_length=300)
    paramlist_version_id: str | None = Field(None,max_length=100)
    variant_id: str | None = Field(None,max_length=300)
    param_id: str | None = Field(None,max_length=300)
    unit: str | None = Field(None,max_length=100)
    date_from: date = Field(default_factory=lambda: months_before(today(),12))
    date_to: date = Field(default_factory=lambda: today()+timedelta(days=1))
    sample_status: list[Literal['Reviewed','Completed']] = Field(default_factory=lambda:['Reviewed'])
    @model_validator(mode='before')
    @classmethod
    def freeze_default_date(cls,values):
        values=dict(values)
        if 'date_from' not in values or 'date_to' not in values:
            current=today()
            values.setdefault('date_from',months_before(current,12))
            values.setdefault('date_to',current+timedelta(days=1))
        return values
    @model_validator(mode='after')
    def bounds(self):
        if self.date_from >= self.date_to or (self.date_to-self.date_from).days>3660 or not self.sample_status:
            raise ValueError('日期必须递增、范围不超过十年且状态不能为空')
        return self

def encode(value) -> str:
    return 'v1.' + base64.urlsafe_b64encode(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()).decode().rstrip('=')
def decode(value: str):
    if not value.startswith('v1.') or len(value)>10000: raise ValueError('非法标识')
    return json.loads(base64.b64decode(value[3:]+'='*(-len(value[3:])%4),altchars=b'-_',validate=True))

def source_key(row):
    return {k: str(row[k]) if isinstance(row[k],Decimal) else row[k] for k in KEY}

def parse(raw):
    if raw is None or not raw.strip(): return {'result_kind':'missing','numeric_value':None,'operator':None,'bound':None,'parse_reason':'源结果为空'}
    s=raw.strip()
    if re.fullmatch(NUM,s): return {'result_kind':'exact_numeric','numeric_value':str(Decimal(s)),'operator':None,'bound':None,'parse_reason':None}
    match=re.fullmatch(r'(<=|>=|<|>|≤|≥|＜|＞)\s*('+NUM+')',s)
    if match: return {'result_kind':'censored','numeric_value':None,'operator':match[1],'bound':str(Decimal(match[2])),'parse_reason':'界值不是实测值；不进入普通均值'}
    if s in {'符合规定','合格','未检出','不符合规定','不合格','无色澄清液体','无色透明液体'}:
        return {'result_kind':'qualitative','numeric_value':None,'operator':None,'bound':None,'parse_reason':'定性原文；未作合格率判断'}
    return {'result_kind':'unparsed','numeric_value':None,'operator':None,'bound':None,'parse_reason':'未配置该原文的解析规则'}

def normalize(row):
    r=dict(row)
    for k,v in r.items():
        if isinstance(v,datetime): r[k]=v.astimezone(TZ).isoformat()
        elif isinstance(v,Decimal): r[k]=str(v)
    key=source_key(row)
    group=[r.get(k) for k in GROUP]
    # Unknown units cannot be assumed to represent a comparable quantity.
    if not r.get('unit') or not r.get('samplepointid'): group.append(key)
    r.update(source_key=key,result_id=encode(key),comparison_group=encode(group),mapping_status=('已关联当前 LIMS 水点主表；历史有效期及系统未核实' if r.get('samplepoint_mapping_scope') == 'current_master' else '现场水点编号、名称及系统未映射'),samplepoint_name=r.get('samplepoint_name'),samplepoint_code=r.get('samplepoint_code'),limit_status='未配置限度',**parse(r.get('displayvalue')))
    r.update(display_value=r.get('displayvalue'),source_unit=r.get('unit'),sample_id=r.get('s_sampleid'),sample_status=r.get('samplestatus'),water_type=r.get('samplesubtypeid'),samplepoint_id=r.get('samplepointid'),trend_at=r.get('trend_dt'),trend_date_source=r.get('trend_dt_source'),batch_number=r.get('u_batchno'))
    reason = 'LIMS 点位内部 ID 缺失，不能归入点位趋势' if not r.get('samplepoint_id') else ('趋势日期缺失' if not r.get('trend_at') else ('单位缺失，量纲未确认' if not r.get('unit') else (None if r['result_kind'] in {'exact_numeric','censored'} else r['parse_reason'])))
    r['plot_status']='plotted' if reason is None else 'not_plotted'
    r['not_plotted_reason']=reason
    return r

def metrics(rows):
    return {'sample_count':len({(r['source_system'],r['s_sampleid']) for r in rows}), 'dataset_count':len({tuple(r[k] for k in KEY[:9]) for r in rows}), 'result_count':len(rows), 'kinds':dict(Counter(r['result_kind'] for r in rows)), 'plot_count':sum(r['plot_status']=='plotted' for r in rows)}
