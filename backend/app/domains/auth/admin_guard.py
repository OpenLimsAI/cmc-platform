"""人工减少系统管理员前取得统一管理锁；不介入密码失败自动锁定。"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import OperationNotAllowedError
from app.domains.auth.models import Role, User, UserRole


async def lock_admin_management(db: AsyncSession) -> None:
    # 先锁这个固定角色，再锁各目标用户，所有减少路径遵循相同锁顺序。
    await db.execute(select(Role.role_id).where(
        Role.role_code == "SYS_ADMIN", Role.deleted_at.is_(None)
    ).with_for_update())


async def ensure_admin_remains(db: AsyncSession, target: User, *, removing_role: bool = False) -> None:
    if target.status != "active" or not any(r.role_code == "SYS_ADMIN" for r in target.roles):
        return
    count = (await db.execute(select(func.count(User.user_id.distinct()))
        .join(UserRole, UserRole.user_id == User.user_id)
        .join(Role, Role.role_id == UserRole.role_id)
        .where(User.deleted_at.is_(None), User.status == "active",
               Role.role_code == "SYS_ADMIN", Role.deleted_at.is_(None)))).scalar_one()
    if count <= 1:
        operation = "撤销系统管理员身份" if removing_role else "锁定账号"
        raise OperationNotAllowedError(f"不能{operation}：至少须保留一个可用的系统管理员")
