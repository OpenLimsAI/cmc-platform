"""Disposable PostgreSQL and explicit PM transport doubles; not browser E2E."""
import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from app.core.config import settings
from app.core.exceptions import ConflictError
from app.domains.auth.models import User
from app.domains.prs.pm_create import (
    CreatePMProject,
    PMCreateClient,
    PMCreateConflictError,
    PMCreateReceipt,
    PMCreateRemoteError,
    ProjectPMCreateService,
)
from app.domains.prs.pm_links import ProjectPMLinkService
from app.domains.prs.pm_reference import PMReference
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


@pytest.fixture(autouse=True)
def isolated_only():
    assert os.environ.get("TEST_DB") == "cmab_test"
    assert settings.DATABASE_URL_SYNC.endswith("/cmab_test")


def payload(**changes):
    body = {"client_request_id": str(uuid4()), "change_reason": "显式确认创建隔离执行项目", "project": {
        "code": "PM-CREATE-" + uuid4().hex[:12], "name": "隔离创建关联",
        "product_type": "单抗", "current_stage": "IND", "target_stage": "BLA",
        "owner_id": "pm-user-explicit", "planned_start": "2026-10-26", "planned_end": "2026-11-26",
    }}
    body.update(changes)
    return CreatePMProject.model_validate(body)


def receipt(request):
    project = request["project"]
    return PMCreateReceipt.model_validate({
        "request_id": request["request_id"], "source_id": request["source_id"],
        "source_project_id": request["source_project_id"], "project_id": "pm-" + request["request_id"],
        "code": project["code"], "name": project["name"], "status": "活跃", "bindable": True,
        "created_by": "pm-user-explicit", "project": {"id": "pm-" + request["request_id"],
            "code": project["code"], "name": project["name"], "status": "活跃", "bindable": True},
    })


class ContractPM:
    """Controlled transport boundary, while MDM persistence/locking uses real PG."""
    def __init__(self):
        self.records = {}
        self.created = 0
        self.fail_after_create = False

    async def lookup(self, request_id):
        return self.records.get(str(request_id))

    async def create(self, request):
        key = request["request_id"]
        if key not in self.records:
            self.records[key] = receipt(request)
            self.created += 1
        if self.fail_after_create:
            self.fail_after_create = False
            raise PMCreateRemoteError()
        return self.records[key]


async def new_project(client):
    response = await client.post("/api/v1/projects", json={"project_name": "创建关联隔离登记", "project_type": "cmc"})
    assert response.status_code == 201, response.text
    return response.json()["data"]["project_code"]


async def test_create_endpoint_permissions_and_no_implicit_static_writer(admin_client, readonly_client, http_client):
    code = await new_project(admin_client)
    url = f"/api/v1/projects/{code}/pm-create"
    body = payload().model_dump(mode="json")
    assert (await http_client.get(url)).status_code == 401
    assert (await http_client.post(url, json=body)).status_code == 401
    assert (await readonly_client.post(url, json=body)).status_code == 403
    # A native MDM JWT or phase1 global reference config cannot become a PM creator.
    assert (await admin_client.post(url, json=body)).status_code in {401, 403}
    assert (await admin_client.get(url)).json()["data"]["operation"] is None


async def test_repeated_and_concurrent_creation_have_one_link_and_one_audit(admin_client):
    code = await new_project(admin_client)
    body, pm = payload(), ContractPM()
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def create():
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            return await ProjectPMCreateService(db, pm, source_id="mdm").create(code, body, user)

    try:
        first, second = await asyncio.gather(create(), create())
        final = await create()
        assert final["operation"]["status"] == "linked"
        assert first["operation"]["request_id"] == second["operation"]["request_id"] == str(body.client_request_id)
        assert pm.created == 1
        assert final["operation"]["link"]["pm_project_id"] == "pm-" + str(body.client_request_id)
        async with engine.connect() as db:
            assert (await db.execute(text("SELECT count(*) FROM prs.project_pm_create_request WHERE request_id=:key"), {"key": str(body.client_request_id)})).scalar_one() == 1
            assert (await db.execute(text("SELECT count(*) FROM audit.audit_log WHERE entity_table='project_pm_link' AND entity_code=:code"), {"code": code})).scalar_one() == 1
        changed = body.model_copy(update={"change_reason": "同一请求不允许被更改为其他原因"})
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            with pytest.raises(ConflictError):
                await ProjectPMCreateService(db, pm, source_id="mdm").create(code, changed, user)
    finally:
        await engine.dispose()


async def test_remote_success_timeout_recovers_same_request_without_duplicate(admin_client):
    code = await new_project(admin_client)
    body, pm = payload(), ContractPM()
    pm.fail_after_create = True
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            service = ProjectPMCreateService(db, pm, source_id="mdm")
            unknown = await service.create(code, body, user)
            assert unknown["operation"]["status"] == "retryable_error"
            assert unknown["operation"]["last_error"] == "pm_unavailable"
            assert unknown["operation"]["link"] is None
            recovered = await service.retry(code, user)
            assert recovered["operation"]["status"] == "linked"
        assert pm.created == 1
    finally:
        await engine.dispose()


async def test_crash_after_remote_success_and_lease_expiry_recovers_receipt(admin_client, monkeypatch):
    code = await new_project(admin_client)
    body, pm = payload(), ContractPM()
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            service = ProjectPMCreateService(db, pm, source_id="mdm")
            async def simulated_process_failure(*args, **kwargs):
                raise RuntimeError("controlled process crash after PM committed")
            monkeypatch.setattr(service, "_finish", simulated_process_failure)
            with pytest.raises(RuntimeError, match="controlled process crash"):
                await service.create(code, body, user)
        # Only this fresh test row: model an owned process dying before its lease ends.
        async with engine.begin() as db:
            await db.execute(text("UPDATE prs.project_pm_create_request SET lease_expires_at=:old WHERE request_id=:key"),
                {"old": datetime.now(UTC) - timedelta(seconds=1), "key": str(body.client_request_id)})
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            recovered = await ProjectPMCreateService(db, pm, source_id="mdm").retry(code, user)
            assert recovered["operation"]["status"] == "linked"
        assert pm.created == 1
    finally:
        await engine.dispose()


async def test_local_commit_failure_rolls_back_link_but_preserves_remote_receipt(admin_client, monkeypatch):
    code = await new_project(admin_client)
    body, pm = payload(), ContractPM()
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            real_commit = db.commit
            async def fail_completion_commit():
                if any(getattr(item, "status", None) == "linked" for item in db.dirty):
                    raise RuntimeError("controlled local completion commit failure")
                return await real_commit()
            monkeypatch.setattr(db, "commit", fail_completion_commit)
            with pytest.raises(RuntimeError, match="controlled local completion commit"):
                await ProjectPMCreateService(db, pm, source_id="mdm").create(code, body, user)
        async with engine.begin() as db:
            assert (await db.execute(text("SELECT count(*) FROM prs.project_pm_link l JOIN prs.project p USING(project_id) WHERE p.project_code=:code"), {"code": code})).scalar_one() == 0
            assert (await db.execute(text("SELECT status FROM prs.project_pm_create_request WHERE request_id=:key"), {"key": str(body.client_request_id)})).scalar_one() == "remote_created"
            await db.execute(text("UPDATE prs.project_pm_create_request SET lease_expires_at=:old WHERE request_id=:key"),
                {"old": datetime.now(UTC) - timedelta(seconds=1), "key": str(body.client_request_id)})
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            assert (await ProjectPMCreateService(db, pm).retry(code, user))["operation"]["status"] == "linked"
        assert pm.created == 1
    finally:
        await engine.dispose()


async def test_pending_intent_blocks_manual_binding_and_old_worker_cannot_overwrite_new_result(admin_client):
    code = await new_project(admin_client)
    body, pm = payload(), ContractPM()
    entered, release = asyncio.Event(), asyncio.Event()
    original_create = pm.create
    async def delayed_response(request):
        result = await original_create(request)
        entered.set()
        await release.wait()
        return result
    pm.create = delayed_response
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async def create():
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            return await ProjectPMCreateService(db, pm).create(code, body, user)
    first = asyncio.create_task(create())
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        duplicate = await create()
        assert duplicate["operation"]["status"] == "in_progress"
        assert duplicate["operation"]["can_retry"] is False
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            class Reference:
                async def get(self, project_id):
                    return PMReference(id=project_id, code="PM-OTHER", name="其他执行项目", status="活跃", bindable=True)
            with pytest.raises(ConflictError, match="已有 PM 创建请求"):
                await ProjectPMLinkService(db, Reference()).bind(code, "pm-other", "创建期间不能另行抢绑", user)
        async with engine.begin() as db:
            await db.execute(text("UPDATE prs.project_pm_create_request SET lease_expires_at=:old WHERE request_id=:key"),
                {"old": datetime.now(UTC) - timedelta(seconds=1), "key": str(body.client_request_id)})
        # The old HTTP response is still blocked; the newer worker restores from PM.
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            assert (await ProjectPMCreateService(db, pm).retry(code, user))["operation"]["status"] == "linked"
        release.set()
        assert (await first)["operation"]["status"] == "linked"
        assert pm.created == 1
        async with engine.connect() as db:
            assert (await db.execute(text("SELECT count(*) FROM audit.audit_log WHERE entity_table='project_pm_link' AND entity_code=:code"), {"code": code})).scalar_one() == 1
    finally:
        release.set()
        if not first.done():
            first.cancel()
            await asyncio.gather(first, return_exceptions=True)
        await engine.dispose()


def test_input_collects_required_fields_without_invented_owner_or_plan():
    body = payload().model_dump(mode="json")
    for field in ["owner_id", "current_stage", "target_stage", "planned_start", "planned_end"]:
        incomplete = json.loads(json.dumps(body))
        del incomplete["project"][field]
        with pytest.raises(ValidationError):
            CreatePMProject.model_validate(incomplete)
    body["project"]["planned_end"] = "2026-01-01"
    with pytest.raises(ValidationError):
        CreatePMProject.model_validate(body)
    body["project"]["budget"] = 0
    with pytest.raises(ValidationError):
        CreatePMProject.model_validate(body)


async def test_client_checks_bounded_receipt_and_never_returns_credentials():
    body = payload()
    request = {"request_id": str(body.client_request_id), "source_id": "mdm", "source_project_id": "12", "project": body.project.model_dump(mode="json")}
    expected = receipt(request)
    seen = []
    async def handler(incoming):
        seen.append(incoming)
        return httpx.Response(201 if incoming.method == "POST" else 200, json=expected.model_dump(mode="json"))
    client = PMCreateClient("http://127.0.0.1:8088", "synthetic-only-access", transport=httpx.MockTransport(handler))
    result = await client.create(request)
    assert result.project.id == expected.project_id
    assert seen[0].headers["Authorization"] == "Bearer synthetic-only-access"
    assert "synthetic-only-access" not in result.model_dump_json()
    assert "access" not in str(seen[0].url)
    async def oversized(incoming):
        return httpx.Response(200, content=b"x" * 65537)
    with pytest.raises(PMCreateRemoteError):
        await PMCreateClient("http://127.0.0.1:8088", "synthetic-only-access", transport=httpx.MockTransport(oversized)).lookup(body.client_request_id)


async def test_different_registration_or_namespace_receipt_is_rejected():
    body = payload()
    request = {"request_id": str(body.client_request_id), "source_id": "mdm", "source_project_id": "12", "project": body.project.model_dump(mode="json")}
    invalid = receipt(request).model_dump(mode="json")
    invalid["source_project_id"] = "99"
    async def handler(incoming):
        return httpx.Response(201, json=invalid)
    with pytest.raises(PMCreateRemoteError):
        await PMCreateClient("http://127.0.0.1:8088", "synthetic-only-access", transport=httpx.MockTransport(handler)).create(request)


async def test_known_remote_receipt_missing_never_posts_another_project(admin_client):
    code = await new_project(admin_client)
    body, pm = payload(), ContractPM()
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            service = ProjectPMCreateService(db, pm)
            async def interrupted(*args):
                raise RuntimeError("interrupted after durable receipt")
            service._finish = interrupted
            with pytest.raises(RuntimeError, match="durable receipt"):
                await service.create(code, body, user)
        pm.records.clear()
        async with engine.begin() as db:
            await db.execute(text("UPDATE prs.project_pm_create_request SET lease_expires_at=:old WHERE request_id=:key"),
                {"old": datetime.now(UTC) - timedelta(seconds=1), "key": str(body.client_request_id)})
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            with pytest.raises(PMCreateConflictError):
                await ProjectPMCreateService(db, pm).retry(code, user)
            state = await ProjectPMCreateService(db, pm).get(code)
            assert state["operation"]["status"] == "reconciliation_required"
            assert state["operation"]["last_error"] == "pm_conflict"
            assert state["operation"]["remote_project_id"] == "pm-" + str(body.client_request_id)
            assert state["operation"]["link"] is None
        assert pm.created == 1
    finally:
        await engine.dispose()
