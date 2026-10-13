"""账号管理审计：字段白名单、同一业务事务、复用现有字段明细。"""
from typing import Any, cast

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.models import AuditLog, ChangeHistory
from app.domains.auth.models import Role, User
from app.shared.audit_context import audit_ip, audit_request_id

USER_FIELDS = (
    "username", "email", "full_name", "full_name_en", "department", "title", "phone",
    "status", "locked_at", "failed_login_count", "force_password_change",
    "password_changed_at", "password_expires_at",
)
ROLE_FIELDS = ("role_code", "role_name", "description", "is_system", "deleted_at")
EXTRA_FIELDS = {
    "actor_scope", "actor_department", "target_department", "roles_before", "roles_after",
    "added", "removed", "field", "old", "new", "operation", "role_before",
}


def user_state(user: User, *, roles: list[str] | None = None) -> dict[str, Any]:
    """只读取公开资料与安全状态；绝不遍历 ORM 或请求体中的密码/令牌。"""
    state = {field: getattr(user, field) for field in USER_FIELDS}
    if roles is not None:
        state["roles"] = sorted(set(roles))
    return cast(dict[str, Any], jsonable_encoder(state))


def role_state(role: Role, permissions: list[str]) -> dict[str, Any]:
    state = {field: getattr(role, field) for field in ROLE_FIELDS}
    state["permissions"] = sorted(set(permissions))
    return cast(dict[str, Any], jsonable_encoder(state))


async def record_auth_change(
    db: AsyncSession,
    actor: User,
    *,
    target: User | Role,
    action: str,
    summary: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """只 flush，不旁路提交；任何后续失败都与业务变更一起回滚。"""
    fields: tuple[str, ...]
    if isinstance(target, User):
        fields = (*USER_FIELDS, "roles")
        entity_table, entity_id, entity_code = "user", target.user_id, target.username
    else:
        fields = (*ROLE_FIELDS, "permissions")
        entity_table, entity_id, entity_code = "role", target.role_id, target.role_code
    old = jsonable_encoder({k: v for k, v in (before or {}).items() if k in fields})
    new = jsonable_encoder({k: v for k, v in (after or {}).items() if k in fields})
    log = AuditLog(
        user_id=actor.user_id,
        username=actor.username,
        action=action,
        entity_schema="auth",
        entity_table=entity_table,
        entity_id=entity_id,
        entity_code=entity_code,
        change_summary=summary,
        ip_address=audit_ip.get(),
        request_id=audit_request_id.get(),
        extra=jsonable_encoder({k: v for k, v in (extra or {}).items() if k in EXTRA_FIELDS}),
    )
    db.add(log)
    await db.flush()
    for field in fields:
        if old.get(field) != new.get(field):
            db.add(ChangeHistory(
                audit_log_id=log.log_id,
                field_name=field,
                old_value=old.get(field),
                new_value=new.get(field),
            ))
