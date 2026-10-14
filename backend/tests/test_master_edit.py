"""三域主表编辑：显式持锁与第二连接排队，不靠 sleep 制造竞态。"""
import asyncio
import os
from uuid import uuid4

import pytest
from app.core.config import settings
from app.core.exceptions import VersionConflictError
from app.domains.auth.models import User
from app.domains.eqp.models import Equipment
from app.domains.eqp.schemas import EquipmentUpdate
from app.domains.eqp.services import EquipmentService
from app.domains.mm.models import Material
from app.domains.mm.schemas import MaterialUpdate
from app.domains.mm.services import MaterialService
from app.domains.target.models import Target
from app.domains.target.schemas import TargetUpdate
from app.domains.target.services import TargetService
from app.shared.audit_context import audit_user_id, audit_username, set_audit_session_vars
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import NullPool

DOMAINS = {
    "material": ("materials", Material, MaterialService, MaterialUpdate, "material_name", {"material_type": "reagent", "material_name": "原名称"}),
    "equipment": ("equipments", Equipment, EquipmentService, EquipmentUpdate, "equipment_name", {"category": "通用实验室设备", "equipment_name": "原名称"}),
    "target": ("targets", Target, TargetService, TargetUpdate, "target_name", {"target_name": "原名称"}),
}


@pytest.fixture(autouse=True)
def isolated_only():
    assert os.environ.get("TEST_DB") == "cmab_test"
    assert settings.DATABASE_URL_SYNC.endswith("/cmab_test")


@pytest.mark.parametrize("domain", DOMAINS)
async def test_preloaded_second_editor_reads_fresh_version_after_lock(admin_client, domain):
    route, model, service_type, schema, field, create = DOMAINS[domain]
    r = await admin_client.post("/api/v1/" + route, json=({**create, "material_code": "W-"+uuid4().hex[:12]} if domain=="material" else create))
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    code, ident = data[domain + "_code"], data[domain + "_id"]
    engine1 = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    engine2 = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    queued = asyncio.Event()
    def observe(conn, cursor, statement, parameters, context, executemany):
        if "FOR UPDATE" in statement.upper():
            queued.set()
    event.listen(engine2.sync_engine, "before_cursor_execute", observe)
    task = None
    try:
        async with async_sessionmaker(engine1, expire_on_commit=False)() as first, async_sessionmaker(engine2, expire_on_commit=False)() as second:
            actor1 = (await first.execute(select(User).where(User.username == "admin").options(selectinload(User.roles)))).scalar_one()
            actor2 = (await second.execute(select(User).where(User.username == "admin").options(selectinload(User.roles)))).scalar_one()
            audit_user_id.set(actor1.user_id)
            audit_username.set(actor1.username)
            await set_audit_session_vars(first)
            await set_audit_session_vars(second)
            # 第二连接先缓存旧对象；缺少重读会在等待结束后错误地沿用旧版本。
            cached = (await second.execute(select(model).where(getattr(model, domain + "_id") == ident))).scalar_one()
            assert cached.version == data["version"]
            await first.execute(select(model).where(getattr(model, domain + "_id") == ident).with_for_update())
            task = asyncio.create_task(service_type(second).update(code, schema(version=data["version"], **{field: "后来者"}), actor2))
            await asyncio.wait_for(queued.wait(), timeout=5)
            await service_type(first).update(code, schema(version=data["version"], **{field: "先保存者"}), actor1)
            with pytest.raises(VersionConflictError):
                await task
            await second.rollback()
            fresh = await admin_client.get(f"/api/v1/{route}/{code}")
            assert fresh.json()["data"][field] == "先保存者"
            assert fresh.json()["data"]["version"] == data["version"] + 1
            # 另一个连接立即可读，版本只增加一次，且仅一条成功字段变更审计。
            changes = (await first.execute(text("SELECT c.old_value,c.new_value FROM audit.change_history c "
                "JOIN audit.audit_log l ON l.log_id=c.audit_log_id WHERE l.entity_table=:domain "
                "AND l.entity_code=:code AND c.field_name=:field ORDER BY c.history_id"),
                {"domain": domain, "code": code, "field": field})).all()
            assert changes[-1] == ("原名称", "先保存者")
            assert sum(row.new_value == "先保存者" for row in changes) == 1
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await engine1.dispose()
        await engine2.dispose()


@pytest.mark.parametrize("domain", DOMAINS)
async def test_old_version_different_field_and_missing_version(admin_client, domain):
    route, _, _, _, field, create = DOMAINS[domain]
    data = (await admin_client.post('/api/v1/'+route, json=({**create, "material_code": "W-"+uuid4().hex[:12]} if domain=="material" else create))).json()['data']
    url = f"/api/v1/{route}/{data[domain+'_code']}"
    r = await admin_client.put(url, json={"version": data['version'], field: "新的名称"})
    assert r.status_code == 200, r.text
    stale = await admin_client.put(url, json={"version": data['version'], "notes": "不同字段也不能覆盖"})
    assert stale.status_code == 409 and stale.json()['code'] == 40904
    assert '本次保存未成功' in stale.json()['message']
    assert (await admin_client.get(url)).json()['data']['notes'] is None
    missing = await admin_client.put(url, json={field: "没有版本"})
    assert missing.status_code == 400


@pytest.mark.parametrize("domain", DOMAINS)
async def test_status_change_and_deleted_record_block_old_editor(admin_client, domain):
    route, _, _, _, field, create = DOMAINS[domain]
    data = (await admin_client.post('/api/v1/'+route, json=({**create, "material_code": "W-"+uuid4().hex[:12]} if domain=="material" else create))).json()['data']
    url = f"/api/v1/{route}/{data[domain+'_code']}"
    if domain == 'target':
        changed = await admin_client.post(url+':publish', json={'change_reason':'发布靶点状态'})
    else:
        change = {'status':'quarantine'} if domain=='material' else {'equipment_status':'sealed'}
        changed = await admin_client.put(url, json={'version':data['version'], 'change_reason':'变更主记录状态', **change})
    assert changed.status_code == 200, changed.text
    assert changed.json()['data']['version'] == data['version']+1
    assert (await admin_client.put(url, json={'version':data['version'],field:'旧页面'})).status_code == 409
    deleted = await admin_client.delete(url, json={'change_reason':'取消测试主记录'})
    assert deleted.status_code == 204, deleted.text
    assert (await admin_client.put(url, json={'version':changed.json()['data']['version'],field:'已删除仍尝试保存'})).status_code == 404


@pytest.mark.parametrize("domain", DOMAINS)
async def test_failed_commit_rolls_back_version_and_audit(admin_client, monkeypatch, domain):
    route, model, service, schema, field, create = DOMAINS[domain]
    data = (await admin_client.post('/api/v1/'+route, json=({**create, "material_code": "W-"+uuid4().hex[:12]} if domain=="material" else create))).json()['data']
    code = data[domain+'_code']
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            actor = (await db.execute(select(User).where(User.username=='admin'))).scalar_one()
            before = (await db.execute(text('SELECT count(*) FROM audit.audit_log WHERE entity_code=:code'), {'code':code})).scalar_one()
            async def failed():
                raise RuntimeError('模拟提交失败')
            monkeypatch.setattr(db, 'commit', failed)
            with pytest.raises(RuntimeError, match='模拟提交失败'):
                await service(db).update(code, schema(version=data['version'], **{field:'不得保存'}),actor)
            await db.rollback()
            fresh = (await db.execute(select(model).where(getattr(model,domain+'_code')==code).execution_options(populate_existing=True))).scalar_one()
            assert fresh.version == data['version'] and getattr(fresh,field)==create[field]
            assert (await db.execute(text('SELECT count(*) FROM audit.audit_log WHERE entity_code=:code'), {'code':code})).scalar_one()==before
    finally:
        await engine.dispose()
