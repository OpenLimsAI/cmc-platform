"""Real isolated PG business transaction; synthetic provider is UNIT scope only."""
import os
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import uuid4

import pytest
from app.core.config import settings
from app.core.exceptions import SignatureInvalidError
from app.domains.audit.models import ESignature
from app.domains.audit.schemas import SignatureBlock
from app.domains.auth.models import User
from app.domains.auth.oidc.config import OIDCConfig
from app.domains.auth.oidc.models import OIDCIdentity, OIDCSession, OIDCSignatureChallenge
from app.domains.auth.oidc.service import seal
from app.domains.prs.models import Project
from app.domains.prs.schemas import ProjectCreate
from app.domains.prs.services import ProjectService
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import NullPool


async def test_project_signature_consumes_fresh_proof_in_business_transaction(monkeypatch):
    from app.domains.auth.oidc.signing import SigningRequest, SigningService

    assert os.environ["TEST_DB"].startswith("cmab_test")
    monkeypatch.setattr(settings, "MDM_SIGNATURE_MODE", "oidc_fresh")
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            user = (await db.execute(select(User).options(selectinload(User.roles)).where(User.username == "admin"))).scalar_one()
            issuer = "http://localhost:19081/" + uuid4().hex
            config = OIDCConfig(issuer=issuer, public_url="http://localhost:19090/mdm", client_id="login",
                client_secret="synthetic", organization="synthetic", account_status_visible=True,
                signature_client_id="sign", signature_client_secret="synthetic", signature_password_only=True)
            identity = OIDCIdentity(issuer=issuer, subject=uuid4().hex, user_id=user.user_id, active=True,
                created_by=user.user_id, change_reason="隔离测试显式映射")
            db.add(identity)
            await db.flush()
            now = datetime.now(UTC)
            session = OIDCSession(id=uuid4().hex * 2, identity_id=identity.identity_id, issued_at=now,
                expires_at=now + timedelta(minutes=5), idle_expires_at=now + timedelta(minutes=5),
                provider_issued_at=int(time.time()), secret_data=seal({"client_id":"login","access_token":"unit-synthetic-access"}))
            db.add(session)
            await db.commit()
            db.info["oidc_session_id"] = session.id
            project = await ProjectService(db).create(ProjectCreate(project_name="合成签署事务", project_type="cmc"), user)
            await db.commit()

            class Provider:
                async def signing_login_hint(self, access, *, subject):
                    assert access == "unit-synthetic-access" and subject == identity.subject
                    return "e2e.signer"

                async def authorization_url(self, params):
                    self.params = params
                    return issuer + "/authorize?" + urlencode(params)

                async def exchange(self, code, verifier, nonce, **kwargs):
                    assert code == "synthetic-code" and nonce == self.params["nonce"]
                    return {"iss": issuer, "sub": identity.subject, "auth_time": int(time.time())}, {}

            provider = Provider()
            service = SigningService(db, config=config, provider=provider)
            request = SigningRequest(entity_type="project", entity_code=project.project_code, action="approve",
                comment="隔离测试确认立项", reason="资料复核通过确认签名")
            pending = await service.begin(request, user=user, session=session)
            assert provider.params["prompt"] == "login" and provider.params["max_age"] == "0"
            assert provider.params["login_hint"] == "e2e.signer" and provider.params["language"] == "zh"
            assert provider.params["login_hint"] != user.username
            await service.complete(pending["challenge_id"], code="synthetic-code", state=pending["state"], user=user, session=session)
            result = await ProjectService(db).change_status(project.project_code, "approve", request.comment, user,
                SignatureBlock(challenge_id=pending["challenge_id"], reason=request.reason))
            assert result.new_status == "initiated" and result.signature_id
            signature = await db.get(ESignature, result.signature_id)
            assert signature.user_id == user.user_id and signature.signature_reason == request.reason
            proof = await service.receipt(pending["challenge_id"], user=user, session=session)
            assert proof["status"] == "consumed" and proof["signature_id"] == result.signature_id
            with pytest.raises(SignatureInvalidError):
                await service.complete(pending["challenge_id"], code="synthetic-code", state=pending["state"], user=user, session=session)
            cancel = request.model_copy(update={"action": "cancel"})

            pending = await service.begin(cancel, user=user, session=session)
            await service.cancel(pending["challenge_id"], user=user, session=session)
            with pytest.raises(SignatureInvalidError):
                await service.complete(pending["challenge_id"], code="synthetic-code", state=pending["state"], user=user, session=session)

            pending = await service.begin(cancel, user=user, session=session)
            with pytest.raises(SignatureInvalidError):
                await service.complete(pending["challenge_id"], code="synthetic-code", state="wrong-state", user=user, session=session)
            await service.cancel(pending["challenge_id"], user=user, session=session)

            pending = await service.begin(cancel, user=user, session=session)
            await service.complete(pending["challenge_id"], code="synthetic-code", state=pending["state"], user=user, session=session)
            row = await db.get(OIDCSignatureChallenge, pending["challenge_id"])
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await db.commit()
            with pytest.raises(SignatureInvalidError):
                await ProjectService(db).change_status(project.project_code, "cancel", cancel.comment, user,
                    SignatureBlock(challenge_id=pending["challenge_id"], reason=cancel.reason))

            pending = await service.begin(cancel, user=user, session=session)
            await service.complete(pending["challenge_id"], code="synthetic-code", state=pending["state"], user=user, session=session)
            await db.execute(update(Project).where(Project.project_code == project.project_code).values(project_name="签名后内容已变更"))
            await db.commit()
            with pytest.raises(SignatureInvalidError):
                await ProjectService(db).change_status(project.project_code, "cancel", cancel.comment, user,
                    SignatureBlock(challenge_id=pending["challenge_id"], reason=cancel.reason))

            pending = await service.begin(cancel, user=user, session=session)
            await service.complete(pending["challenge_id"], code="synthetic-code", state=pending["state"], user=user, session=session)
            async with async_sessionmaker(engine, expire_on_commit=False)() as other_transaction:
                await other_transaction.execute(update(OIDCSession).where(OIDCSession.id == session.id).values(revoked_at=datetime.now(UTC)))
                await other_transaction.commit()
            with pytest.raises(SignatureInvalidError):
                await ProjectService(db).change_status(project.project_code, "cancel", cancel.comment, user,
                    SignatureBlock(challenge_id=pending["challenge_id"], reason=cancel.reason))
    finally:
        await engine.dispose()
