"""
电子签名 service：验证密码 → 计算哈希 → 写 e_signature → 返回签名对象

调用方（srs/prs services）拿到返回的 signature 后：
  1. 执行业务状态变更 flush（触发器写 status_history，e_signature_id=NULL）
  2. UPDATE status_history.e_signature_id = sig.signature_id

为什么不再用 SET LOCAL + 触发器读 session var：asyncpg + AsyncSession 快速连续请求
下观察到 SET LOCAL 的 GUC 偶发跨事务泄漏（pytest 全集 ~10% 失败率，表现为相邻请求
的 status_history 共用同一 sig_id 或 commit 静默回滚）。显式 UPDATE 模式无此问题。
"""
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import SignatureInvalidError
from app.core.security import verify_password
from app.domains.audit.models import AuditLog, ESignature
from app.domains.auth.models import User
from app.shared.audit_context import audit_ip, audit_request_id
from app.shared.signature import compute_signature_hash, compute_signed_content_hash


class ESignatureService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def sign(
        self,
        user: User,
        password: str | None,
        entity_schema: str,
        entity_table: str,
        entity_id: int,
        entity_code: str | None,
        meaning: str,
        reason: str,
        content_for_hash: dict[str, Any],
        challenge_id: str | None = None,
    ) -> ESignature:
        """验证密码 + 写电子签名 + 设置 PG session var

        失败：写一条 SIGN 失败 audit_log + 增 failed_login_count + 抛 SignatureInvalidError
        成功：返回 ESignature 实例（已 flushed，signature_id 可用）
        """
        ip = audit_ip.get()
        from app.core.config import settings
        proof = None
        if settings.MDM_SIGNATURE_MODE == "oidc_fresh":
            from app.domains.auth.oidc.signing import consume
            if password or not challenge_id:
                raise SignatureInvalidError("此部署仅允许通过 Casdoor 再次认证签名")
            proof = await consume(self.db, challenge_id, user=user, entity_schema=entity_schema,
                entity_table=entity_table, entity_id=entity_id, meaning=meaning,
                content_hash=compute_signed_content_hash(content_for_hash))
        elif challenge_id or not password or not verify_password(password, user.password_hash):
            # 签名失败审计 + 累计 failed_login_count 必须独立落地，
            # 即使主事务最终 rollback（21 CFR Part 11 §11.300）。
            # 用独立 session 旁路写入，独立 commit。
            await _persist_signature_failure(
                user_id=user.user_id,
                username=user.username,
                entity_schema=entity_schema,
                entity_table=entity_table,
                entity_id=entity_id,
                entity_code=entity_code,
                meaning=meaning,
                ip=ip,
                request_id=audit_request_id.get(),
            )
            raise SignatureInvalidError()

        signed_at = datetime.now(UTC)
        signed_content_hash = compute_signed_content_hash(content_for_hash)
        signature_hash = compute_signature_hash(
            signed_content_hash, user.user_id, signed_at, ip, meaning, reason
        )

        sig = ESignature(
            user_id=user.user_id,
            username=user.username,
            full_name=user.full_name,
            entity_schema=entity_schema,
            entity_table=entity_table,
            entity_id=entity_id,
            entity_code=entity_code,
            signature_meaning=meaning,
            signature_reason=reason,
            signed_content_hash=signed_content_hash,
            signature_hash=signature_hash,
            ip_address=ip,
            signed_at=signed_at,
        )
        self.db.add(sig)
        await self.db.flush()
        if proof is not None:
            proof.signature_id = sig.signature_id
            await self.db.flush()
        return sig


async def _persist_signature_failure(
    *,
    user_id: int,
    username: str,
    entity_schema: str,
    entity_table: str,
    entity_id: int,
    entity_code: str | None,
    meaning: str,
    ip: str | None,
    request_id: str | None,
) -> None:
    """独立 session 写 SIGN 失败审计 + failed_login_count++ + 触发锁定

    必须独立 commit，否则外层主事务 rollback 会一起把这条审计回滚，违反 GxP 不可篡改要求。
    与登录失败共享同一锁定阈值（LOGIN_MAX_FAILED_ATTEMPTS）。
    """
    from sqlalchemy import select

    from app.core.config import settings

    async with AsyncSessionLocal() as side_session:
        # 注入审计上下文，让 audit.fn_audit_trigger 能在 user UPDATE 时拿到 user_id
        await side_session.execute(
            text(
                """
                SELECT
                    set_config('app.user_id',    :user_id,    true),
                    set_config('app.username',   :username,   true),
                    set_config('app.request_id', :request_id, true),
                    set_config('app.ip_address', :ip,         true)
                """
            ),
            {
                "user_id": str(user_id),
                "username": username,
                "request_id": request_id or "",
                "ip": ip or "",
            },
        )

        # 1) 直写 audit_log SIGN 失败
        side_session.add(
            AuditLog(
                user_id=user_id,
                username=username,
                action="SIGN",
                entity_schema=entity_schema,
                entity_table=entity_table,
                entity_id=entity_id,
                entity_code=entity_code,
                reason=f"电子签名失败：密码错误（{meaning}）",
                ip_address=ip,
                request_id=request_id,
            )
        )

        # 2) 累计 failed_login_count；达阈值锁定
        u_result = await side_session.execute(
            select(User).where(User.user_id == user_id)
        )
        side_user = u_result.scalar_one_or_none()
        if side_user is not None:
            side_user.failed_login_count = (side_user.failed_login_count or 0) + 1
            if side_user.failed_login_count >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
                side_user.status = "locked"
                side_user.locked_at = datetime.now(UTC)

        await side_session.commit()
