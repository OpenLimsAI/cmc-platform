"""三域主表编辑：显式持锁与第二连接排队，不靠 sleep 制造竞态。"""
import asyncio
import os

import pytest
from app.core.config import settings
from app.core.exceptions import VersionConflictError
from app.domains.ars.models import Asset
from app.domains.ars.schemas import AssetUpdate
from app.domains.ars.services import AssetService
from app.domains.auth.models import User
from app.domains.prs.models import Project
from app.domains.prs.schemas import ProjectUpdate
from app.domains.prs.services import ProjectService
from app.domains.srs.models import Substance
from app.domains.srs.schemas import SubstanceUpdate
from app.domains.srs.services import SubstanceService
from app.shared.audit_context import audit_user_id, audit_username, set_audit_session_vars
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import NullPool

DOMAINS = {
    "substance": ("substances", Substance, SubstanceService, SubstanceUpdate, "preferred_name", {"substance_type": "mab", "preferred_name": "原名称"}),
    "project": ("projects", Project, ProjectService, ProjectUpdate, "project_name", {"project_type": "cmc", "project_name": "原名称"}),
    "asset": ("assets", Asset, AssetService, AssetUpdate, "internal_name", {"asset_type": "mab", "internal_name": "原名称"}),
}


@pytest.fixture(autouse=True)
def isolated_only():
    assert os.environ.get("TEST_DB") == "cmab_test"
    assert settings.DATABASE_URL_SYNC.endswith("/cmab_test")


@pytest.mark.parametrize("domain", DOMAINS)
async def test_preloaded_second_editor_reads_fresh_version_after_lock(admin_client, domain):
    route, model, service_type, schema, field, create = DOMAINS[domain]
    r = await admin_client.post("/api/v1/" + route, json=create)
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
async def test_stale_editor_rejected_even_when_changing_different_field(admin_client, domain):
    route, _, _, _, field, create = DOMAINS[domain]
    r = await admin_client.post("/api/v1/" + route, json=create)
    data = r.json()["data"]
    path = f'/api/v1/{route}/{data[domain+"_code"]}'
    first = await admin_client.put(path, json={"version": data["version"], field: "新名称"})
    assert first.status_code == 200
    second = await admin_client.put(path, json={"version": data["version"], "notes": "另一字段"})
    assert second.status_code == 409 and second.json()["code"] == 40904
    fresh = (await admin_client.get(path)).json()["data"]
    assert fresh[field] == "新名称" and fresh["notes"] != "另一字段"


async def test_protein_only_main_form_save_advances_version(admin_client):
    created = (await admin_client.post("/api/v1/substances", json={
        "substance_type": "mab", "preferred_name": "只改蛋白属性",
        "protein": {"isotype": "IgG1"},
    })).json()["data"]
    path = '/api/v1/substances/' + created["substance_code"]
    saved = await admin_client.put(path, json={"version": created["version"], "protein": {"expression_vector": "先保存"}})
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["version"] == created["version"] + 1
    stale = await admin_client.put(path, json={"version": created["version"], "protein": {"expression_vector": "过期保存"}})
    assert stale.status_code == 409 and stale.json()["code"] == 40904
    fresh = (await admin_client.get(path + '?expand=protein')).json()["data"]
    assert fresh["protein"]["expression_vector"] == "先保存"


@pytest.mark.parametrize("domain", DOMAINS)
async def test_editor_opened_before_status_change_is_rejected(admin_client, domain):
    route, model, _, _, field, create = DOMAINS[domain]
    r = await admin_client.post("/api/v1/" + route, json=create)
    data = r.json()["data"]
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(model.__table__.update().where(getattr(model, domain + "_id") == data[domain + "_id"])
                .values(status={"substance": "registered", "project": "initiated", "asset": "active"}[domain]))
        path = f'/api/v1/{route}/{data[domain+"_code"]}'
        r = await admin_client.put(path, json={"version": data["version"], field: "过期编辑"})
        assert r.status_code == 409 and r.json()["code"] == 40904
        assert (await admin_client.get(path)).json()["data"][field] == "原名称"
    finally:
        await engine.dispose()


@pytest.mark.parametrize("domain", DOMAINS)
async def test_commit_failure_leaves_data_and_audit_unchanged(admin_client, domain, monkeypatch):
    route, model, service, schema, field, create = DOMAINS[domain]
    r = await admin_client.post("/api/v1/" + route, json=create)
    data = r.json()["data"]
    code = data[domain + "_code"]
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            actor = (await db.execute(select(User).where(User.username == "admin").options(selectinload(User.roles)))).scalar_one()
            await set_audit_session_vars(db)
            before = (await db.execute(text("SELECT count(*) FROM audit.audit_log WHERE entity_table=:domain AND entity_code=:code"),
                                       {"domain": domain, "code": code})).scalar_one()
            async def fail_commit():
                raise RuntimeError("edit_commit_failure")
            monkeypatch.setattr(db, "commit", fail_commit)
            with pytest.raises(RuntimeError, match="edit_commit_failure"):
                await service(db).update(code, schema(version=data["version"], **{field: "不应保存"}), actor)
            await db.rollback()
            fresh = (await admin_client.get(f"/api/v1/{route}/{code}")).json()["data"]
            assert fresh[field] == "原名称" and fresh["version"] == data["version"]
            after = (await db.execute(text("SELECT count(*) FROM audit.audit_log WHERE entity_table=:domain AND entity_code=:code"),
                                      {"domain": domain, "code": code})).scalar_one()
            assert after == before
    finally:
        await engine.dispose()
