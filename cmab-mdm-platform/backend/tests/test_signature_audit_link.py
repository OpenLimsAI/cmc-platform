"""Real isolated DB: new signature links, rollback and untouched legacy records."""
import os
from datetime import UTC, datetime

from app.core.config import settings
from app.domains.audit.models import AuditLog, ESignature
from app.domains.audit.schemas import ESignatureItem
from app.domains.audit.signature_service import ESignatureService
from app.domains.auth.models import User
from app.scripts.seed_data import USERS
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


async def test_native_signature_audit_is_atomic_and_does_not_backfill_legacy(monkeypatch):
    assert os.environ["TEST_DB"] == "cmab_test"
    monkeypatch.setattr(settings, "MDM_SIGNATURE_MODE", "local_password")
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            legacy = ESignature(user_id=user.user_id, username=user.username,
                full_name=user.full_name, entity_schema="prs", entity_table="project",
                entity_id=987654321, signature_meaning="review", signature_reason="合成历史记录",
                signed_content_hash="0" * 64, signature_hash="1" * 64, signed_at=datetime.now(UTC))
            db.add(legacy)
            await db.commit()
            legacy_id = legacy.signature_id
            password = next(record["password"] for record in USERS if record["username"] == "admin")
            args = {"user": user, "password": password, "entity_schema": "prs", "entity_table": "project",
                "entity_id": 987654321, "entity_code": "synthetic-audit-only", "meaning": "review",
                "reason": "合成审核确认", "content_for_hash": {"version": 1}}
            first = await ESignatureService(db).sign(**args)
            assert first.audit_log_id is not None
            event = await db.get(AuditLog, first.audit_log_id)
            assert event.action == "SIGN" and event.user_id == first.user_id
            assert event.entity_id == first.entity_id and event.reason == first.signature_reason
            assert event.extra["signature_hash"] == first.signature_hash
            assert event.extra["authentication_method"] == "local_password"
            assert ESignatureItem.model_validate(first).audit_log_id == event.log_id
            await db.commit()
            first_id, first_log_id = first.signature_id, first.audit_log_id

            pending = await ESignatureService(db).sign(**args)
            pending_id, pending_log_id = pending.signature_id, pending.audit_log_id
            assert pending_log_id != first_log_id
            # Simulate the enclosing business operation failing after sign().
            await db.rollback()
        async with factory() as verify:
            assert await verify.get(ESignature, pending_id) is None
            assert await verify.get(AuditLog, pending_log_id) is None
            assert (await verify.get(ESignature, first_id)).audit_log_id == first_log_id
            untouched = await verify.get(ESignature, legacy_id)
            assert untouched.audit_log_id is None
            assert ESignatureItem.model_validate(untouched).audit_log_id is None
    finally:
        await engine.dispose()
