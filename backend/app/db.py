"""Read-only reflected ORM; no schema creation or writes."""
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from sqlalchemy import MetaData, select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import registry
from app.core import settings
from app.analysis import SOURCE, WATERS, RULES, KEY, TZ, WATER_CARDS, normalize

engine=create_async_engine(settings.database_url, isolation_level='REPEATABLE READ', connect_args={'server_settings':{'default_transaction_read_only':'on','statement_timeout':'30000','application_name':'water_dashboard'}})
metadata=MetaData(schema='staging')
mapper=registry()
models={}
TABLES={'wide':'stg_lv_test_result_wide','sample':'stg_lv_sample','dataset':'stg_lv_dataset','dataitem':'stg_lv_dataitem','workitem':'stg_lv_workitem'}
# The order is the UI cascade. A field's choices use only earlier selections.
FILTER_FIELDS=(('water_type','samplesubtypeid'),('samplepoint_code','samplepoint_code'),('samplepoint_id','samplepointid'),('workitem_id','workitemid'),('paramlist_id','paramlistid'),('paramlist_version_id','paramlistversionid'),('variant_id','variantid'),('param_id','paramid'),('unit','unit'))
REQUIRED={'wide':set(KEY)|{'s_sampleid','samplesubtypeid','samplestatus','samplepointid','locationid','samplepoint_code','samplepoint_name','samplepoint_mapping_source','samplepoint_mapping_scope','samplepoint_source_moddt','samplepoint_extracted_at','workitemid','displayvalue','unit','trend_dt','trend_dt_source','selection_rule','selection_reason','_etl_loaded_at'},'sample':{'source_system','s_sampleid','samplesubtypeid','samplestatus','samplepointid','samplepoint_code','samplepoint_name','eventdt','collectiondt','receiveddt','createdt'},'dataset':set(KEY[:9])|{'workitemid','workiteminstance'},'dataitem':set(KEY)|{'displayvalue','releasedflag','valuestatus','calcexcludeflag'},'workitem':set(KEY[:5])|{'workitemid','workiteminstance'}}
async def preflight():
    async with engine.connect() as conn:
        await conn.run_sync(lambda c: metadata.reflect(bind=c,only=list(TABLES.values())))
        for name,table in TABLES.items():
            t=metadata.tables['staging.'+table]
            if REQUIRED[name]-set(t.c.keys()): raise RuntimeError('QC staging 必需字段不兼容')
            cls=type(name.title(),(),{'__table__':t})
            mapper.map_imperatively(cls,t)
            models[name]=cls
            if await conn.scalar(select(func.has_table_privilege(func.current_user(), 'staging.'+table,'INSERT,UPDATE,DELETE,TRUNCATE'))):
                raise RuntimeError('查询账号拥有业务写权限，拒绝启动')
            await conn.execute(select(cls).limit(1))
        if await conn.scalar(text('SHOW transaction_read_only'))!='on': raise RuntimeError('必须只读连接')
        w=models['wide'].__table__
        for name in ('trend_dt','_etl_loaded_at'):
            if not getattr(w.c[name].type,'timezone',False): raise RuntimeError('时间字段必须包含时区')
        for name in ('dataset','replicateid'):
            if w.c[name].type.python_type.__name__!='Decimal': raise RuntimeError('来源数字键类型不兼容')

@asynccontextmanager
async def transaction():
    async with AsyncSession(engine,expire_on_commit=False) as session:
        async with session.begin():
            await session.execute(text('SET TRANSACTION READ ONLY'))
            yield session

def scope():
    w=models['wide']
    return [w.source_system==SOURCE,w.sdcid=='Sample',w.samplesubtypeid.in_(WATERS),w.selection_rule.in_(RULES),w.samplestatus=='Reviewed']
def conditions(f):
    w=models['wide']; out=scope()+[w.samplestatus.in_(f.sample_status)]
    for api,col in FILTER_FIELDS:
        value=getattr(f,api)
        if value is not None: out.append(getattr(w,col)==value)
    out += [w.trend_dt>=datetime.combine(f.date_from,time.min,TZ),w.trend_dt<datetime.combine(f.date_to,time.min,TZ)]
    return out

async def read_overview(session, current: date):
    """Count identities in SQL; companion parameters must never add samples."""
    w=models['wide']
    start=date(current.year,1,1)
    end=current+timedelta(days=1)
    annual=(w.trend_dt>=datetime.combine(start,time.min,TZ),
            w.trend_dt<datetime.combine(end,time.min,TZ))
    statement=select(
        w.samplesubtypeid.label('water_type'),
        func.count(func.distinct(w.samplepointid)).filter(
            w.samplepointid.is_not(None),w.samplepointid!='').label('point_count'),
        func.count(func.distinct(w.s_sampleid)).filter(
            w.s_sampleid.is_not(None),w.s_sampleid!='',*annual).label('annual_sample_count'),
    ).where(*scope(),w.samplestatus.in_(['Reviewed'])).group_by(w.samplesubtypeid)
    counts={r['water_type']:r for r in (await session.execute(statement)).mappings()}
    return {'year':current.year,'date_from':start.isoformat(),'date_to':end.isoformat(),
            'sample_status':['Reviewed'],'point_scope':'all_available_selected_results',
            'water_cards':[{'code':code,'water_type':water,
                            'point_count':counts[water]['point_count'] if water in counts else 0,
                            'annual_sample_count':counts[water]['annual_sample_count'] if water in counts else 0}
                           for code,water in WATER_CARDS]}

def option_filter(f, field):
    names=[name for name,_ in FILTER_FIELDS]
    # Preserve the resolved dates and statuses; never recalculate today here.
    return f.model_copy(update={name:None for name in names[names.index(field):]})

async def read_options(session,f):
    w=models['wide']; options={}; point_options=[]
    for field,col in FILTER_FIELDS:
        predicates=conditions(option_filter(f,field))
        column=getattr(w,col)
        options[col]=list((await session.scalars(select(column).where(*predicates).distinct().order_by(column))).all())
        if field=='samplepoint_id':
            points=(await session.execute(select(w.samplepointid,w.samplepoint_code,w.samplepoint_name).where(*predicates).distinct().order_by(w.samplepoint_code,w.samplepointid,w.samplepoint_name))).all()
            point_options=[{'value':point_id,'code':code,'label':' / '.join(str(v) for v in (code or '现场编号缺失',name,point_id) if v)} for point_id,code,name in points if point_id]
    return options,point_options

def record(obj):
    from decimal import Decimal
    result={}
    for c in obj.__table__.columns:
        value=getattr(obj,c.name)
        if isinstance(value,Decimal): value=str(value)
        elif isinstance(value,datetime): value=value.astimezone(TZ).isoformat()
        result[c.name]=value
    return result
async def read_rows(session,f):
    w=models['wide']
    predicates=conditions(f)
    rows=(await session.scalars(select(w).where(*predicates).order_by(*(getattr(w,k) for k in KEY)).limit(settings.max_rows+1))).all()
    if len(rows)>settings.max_rows:
        from fastapi import HTTPException
        raise HTTPException(413,'范围超过允许行数，请缩小筛选')
    return [normalize(record(r)) for r in rows]
