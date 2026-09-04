"""幂等补齐会话策略相关的权限码与角色（不重跑 make seed）。

  - 权限码 system:config（系统配置：会话策略页读写；SYS_ADMIN 代码短路无需挂）
  - 角色 DISPLAY_MODE（展示模式：墙屏/看板账号，空闲超时放宽；不含业务权限）

会话策略数值本身由 migration 0054 写进 meta.system_config，本脚本不碰。
反复运行安全。运行（容器内 / Linux .venv）：`python -m app.scripts.seed_session_policy`
"""
import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.domains.auth.models import Permission, Role
from app.scripts.seed_data import PERMISSIONS, ROLES


async def main() -> int:
    created: list[str] = []
    async with AsyncSessionLocal() as db:
        for code, resource, action, desc in PERMISSIONS:
            if code != "system:config":
                continue
            exists = (
                await db.execute(select(Permission).where(Permission.permission_code == code))
            ).scalar_one_or_none()
            if exists is None:
                db.add(Permission(permission_code=code, resource=resource, action=action,
                                  description=desc, is_system=True))
                created.append(f"permission:{code}")

        for role_code, role_name, desc, _perms in ROLES:
            if role_code != "DISPLAY_MODE":
                continue
            role = (
                await db.execute(
                    select(Role).where(Role.role_code == role_code, Role.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            if role is None:
                db.add(Role(role_code=role_code, role_name=role_name,
                            description=desc, is_system=True))
                created.append(f"role:{role_code}")
        await db.commit()
    await engine.dispose()
    print(f"created={created or '（无，已齐全）'}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
