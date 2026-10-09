import hashlib
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from app import db
from app.core import require_view, require_export, settings
from app.analysis import *

log=logging.getLogger('water.audit')
logging.basicConfig(level=logging.INFO)
@asynccontextmanager
async def lifespan(app):
    await db.preflight()
    yield
    await db.engine.dispose()
app=FastAPI(title='制药用水看板',lifespan=lifespan)

@app.middleware('http')
async def audit(request: Request,call_next):
    request.state.request_id=str(uuid.uuid4()); start=time.monotonic()
    response=await call_next(request)
    response.headers['X-Request-ID']=request.state.request_id
    log.info(json.dumps({'request_id':request.state.request_id,'path':request.url.path,'actor':getattr(request.state,'actor_id',None),'status':response.status_code,'seconds':round(time.monotonic()-start,3)},ensure_ascii=False))
    return response
@app.exception_handler(HTTPException)
async def errors(request,exc):
    codes={401:'UNAUTHORIZED',403:'FORBIDDEN',404:'NOT_FOUND',409:'DATA_CONTEXT_CHANGED',413:'EXPORT_TOO_LARGE',422:'INVALID_REQUEST',503:'DATA_UNAVAILABLE'}
    return JSONResponse(status_code=exc.status_code,content={'code':'EXPORT_NO_RESULTS' if exc.detail=='当前条件无结果，不能导出' else codes.get(exc.status_code,'ERROR'),'message':exc.detail,'request_id':request.state.request_id})
@app.exception_handler(RequestValidationError)
async def validation(request,exc): return JSONResponse(status_code=422,content={'code':'INVALID_REQUEST','message':'筛选或请求格式无效','request_id':request.state.request_id})
@app.exception_handler(SQLAlchemyError)
async def unavailable(request,exc):
    log.error('数据库查询失败 request_id=%s type=%s',request.state.request_id,type(exc).__name__)
    return JSONResponse(status_code=503,content={'code':'DATA_UNAVAILABLE','message':'数据暂不可用，请重试或联系维护人员','request_id':request.state.request_id})

def get_filter(request: Request) -> FilterSpec:
    allowed=set(FilterSpec.model_fields)
    if request.url.path=='/api/v1/trends': allowed.add('comparison_group')
    if set(request.query_params)-allowed: raise HTTPException(422,'未知筛选参数')
    values={k:request.query_params[k] for k in FilterSpec.model_fields if k in request.query_params and k!='sample_status'}
    if 'sample_status' in request.query_params: values['sample_status']=request.query_params.getlist('sample_status')
    try: return FilterSpec.model_validate(values)
    except ValueError: raise HTTPException(422,'筛选格式、日期或状态无效') from None
Filter=Annotated[FilterSpec,Depends(get_filter)]
def source_notes(origin):
    if origin=='legacy_xlsx':
        return ('历史 Excel 派生分析数据；raw 已同步不代表 staging 已刷新','当前分析层仍含旧 Excel 日期；历史 HH24:MM:ss 导出导致分钟不准确，需由 QC ETL 刷新 staging 后复核')
    if origin=='oracle_etl':
        return ('QC ETL 从 Oracle 同步 raw 后生成 staging','日期保留源数据库值；趋势日期具体来源见每条记录的日期来源字段')
    return ('QC staging；装载来源待核实','日期保留 staging 值；是否已从最新 raw 刷新需核对 QC ETL 装载记录')

async def context(session):
    w=db.models['wide']
    source_description,timestamp_note=source_notes(settings.staging_data_origin)
    result=(await session.execute(select(func.min(w.trend_dt),func.max(w.trend_dt),func.max(w._etl_loaded_at)).where(*db.scope()))).one()
    return {'environment':settings.app_env,'source_system':SOURCE,'source_description':source_description,'staging_data_origin':settings.staging_data_origin,'current_date':today().isoformat(),'timezone':'Asia/Shanghai','min_result_at':result[0],'max_result_at':result[1],'loaded_at_hint':result[2],'source_cutoff':None,'context_id':None,'consistency_note':'一致性上下文未核实；单响应及单个导出内部为同次只读取数，不承诺跨接口或长期可复现','timestamp_note':timestamp_note,'selection_rules':RULES,'analysis_rule_version':RULE,'mapping_status':('水点编号/名称来自当前 LIMS 主表快照；历史有效期及系统归属未核实' if hasattr(w,'samplepoint_code') else '未确认现场水点编号、点位名称与系统映射'),'limit_status':'未配置限度','freshness_status':'QC job 新鲜度未核实'}

def digest(rows): return hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def envelope(ctx,**data): return {'data_context':ctx,'context_id':None,'analysis_rule_version':RULE,**data}
@app.get('/api/health')
async def health(): return {'status':'ok'}
@app.get('/api/v1/context')
async def get_context(user=Depends(require_view)):
    async with db.transaction() as s:
        ctx=await context(s)
    ctx['capabilities']={'view':True,'export':bool(settings.export_roles.intersection(user['roles']))}
    return ctx
@app.get('/api/v1/filters')
async def filters(f:Filter,user=Depends(require_view)):
    async with db.transaction() as s:
        options,point_options=await db.read_options(s,f)
        return envelope(await context(s),options=options,point_options=point_options,filter=f.model_dump(mode='json'))

async def collection(f):
    async with db.transaction() as s:
        rows=await db.read_rows(s,f); ctx=await context(s)
    return rows,ctx
@app.get('/api/v1/overview')
async def overview(request: Request,user=Depends(require_view)):
    if request.query_params: raise HTTPException(422,'总览不接受筛选参数')
    current=today()
    async with db.transaction() as session:
        counts=await db.read_overview(session,current)
        ctx=await context(session)
        ctx['current_date']=current.isoformat()
    return envelope(ctx,overview_rule_version=OVERVIEW_RULE,**counts)

@app.get('/api/v1/comparison-groups')
async def comparison_groups(f:Filter,user=Depends(require_view)):
    rows,ctx=await collection(f)
    groups={}
    for r in rows:
        g=r['comparison_group']
        if g not in groups: groups[g]={'id':g,'label':' / '.join(str(v) for v in [r.get('samplepoint_code'),r.get('samplepoint_name')] if v) + (' / ' if r.get('samplepoint_code') or r.get('samplepoint_name') else '') + ' / '.join(str(r.get(k) or '未配置') for k in GROUP),'count':0}
        groups[g]['count']+=1
    return envelope(ctx,metrics=metrics(rows),groups=list(groups.values()),filter=f.model_dump(mode='json'),dataset_digest=digest(rows),count_note='方法数据集数不等同于检测次数；N 为精确数值结果行')
@app.get('/api/v1/trends')
async def trends(f:Filter,comparison_group:str=Query(...,max_length=10000),user=Depends(require_view)):
    rows,ctx=await collection(f); rows=[r for r in rows if r['comparison_group']==comparison_group]
    return envelope(ctx,items=rows,total=len(rows),metrics=metrics(rows),filter=f.model_dump(mode='json'),comparison_group=comparison_group,dataset_digest=digest(rows),limit_status='未配置限度')
@app.get('/api/v1/results/trace')
async def trace(result_id:str=Query(...,max_length=10000),user=Depends(require_view)):
    try:
        key=decode(result_id)
        if not isinstance(key,dict) or set(key)!=set(KEY) or any(not isinstance(v,str) for v in key.values()): raise ValueError()
        for k in ('dataset','replicateid'):
            if not Decimal(key[k]).is_finite(): raise ValueError()
        if key['source_system']!=SOURCE or key['sdcid']!='Sample': raise ValueError()
    except Exception: raise HTTPException(422,'非法来源键') from None
    async with db.transaction() as s:
        w=db.models['wide']; match=[getattr(w,k)==(Decimal(v) if k in ('dataset','replicateid') else v) for k,v in key.items()]
        row=await s.scalar(select(w).where(*db.scope(),*match))
        if row is None: raise HTTPException(404,'未找到授权范围内的结果')
        chain={'result':normalize(db.record(row))}; gaps=[]
        for name,keys in [('sample',{'source_system':SOURCE,'s_sampleid':row.s_sampleid}),('dataitem',key),('dataset',{k:key[k] for k in KEY[:9]})]:
            model=db.models[name]
            obj=await s.scalar(select(model).where(*(getattr(model,k)==(Decimal(v) if k in ('dataset','replicateid') else v) for k,v in keys.items())))
            chain[name]=db.record(obj) if obj else None
            if not obj: gaps.append(name+'关联缺失')
        dataset=chain['dataset']
        if dataset:
            if dataset['workitemid']!=row.workitemid: gaps.append('宽表与数据集检项 ID 不一致')
            model=db.models['workitem']; keys={k:dataset[k] for k in KEY[:5]+('workitemid',)}; keys['workiteminstance']=Decimal(dataset['workiteminstance'])
            obj=await s.scalar(select(model).where(*(getattr(model,k)==v for k,v in keys.items())))
            chain['workitem']=db.record(obj) if obj else None
            if not obj: gaps.append('检项实例关联缺失')
        return envelope(await context(s),chain=chain,gaps=gaps,association_note='staging 保留上游选定关联，不代表所有原始桥接历史')

class ExportRequest(BaseModel):
    model_config={'extra':'forbid'}
    filter: FilterSpec
    comparison_group: str = Field(max_length=10000)
    export_kind: Literal['chart','table','bundle']
    context_id: str | None = None
    dataset_digest: str = Field(min_length=64,max_length=64)
    chart_spec: dict = Field(default_factory=dict)
@app.post('/api/v1/exports')
async def export(payload:ExportRequest,user=Depends(require_export)):
    rows,ctx=await collection(payload.filter)
    rows=[r for r in rows if r['comparison_group']==payload.comparison_group]
    if payload.context_id is not None or digest(rows)!=payload.dataset_digest: raise HTTPException(409,'数据上下文或当前结果已变化，请刷新后再导出')
    if not rows: raise HTTPException(422,'当前条件无结果，不能导出')
    from app.export import generate
    from starlette.concurrency import run_in_threadpool
    try:
        content,mime,filename=await run_in_threadpool(generate,rows,ctx,payload,user)
    except Exception as exc:
        log.error('导出生成失败 type=%s',type(exc).__name__)
        raise HTTPException(503,'导出生成失败，未返回部分文件') from None
    log.info(json.dumps({'event':'export','actor':user['sub'],'rows':len(rows),'kind':payload.export_kind},ensure_ascii=False))
    return Response(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store'})
