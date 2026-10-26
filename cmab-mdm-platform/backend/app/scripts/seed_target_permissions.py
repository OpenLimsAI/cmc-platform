"""幂等新增靶点域权限码并挂到既有角色（不重跑 make seed）。

背景：权限码只在 seed_data.py 定义；dev/prod 库禁止重跑 make seed（真实物料/设备数据），
所以新域权限用本脚本定向补齐。与 seed_data.PERMISSIONS / ROLES 保持一致（单一事实来源在那边）。

  - target:create / target:read / target:update / target:approve
  - 角色挂载：SUBSTANCE_STEWARD(read/update/approve)、CMC_RESEARCHER(create/read/update)、
    PROJECT_MANAGER / QA_REVIEWER / READ_ONLY_USER(read)；SYS_ADMIN 代码里短路无需挂

反复运行安全：权限码/角色-权限对按存在性判重；缺失的角色只告警不创建。
运行（容器内 / Linux .venv）：`python -m app.scripts.seed_target_permissions`
"""
import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.domains.auth.models import Permission, Role, RolePermission
from app.scripts.seed_data import PERMISSIONS, ROLES

TARGET_PERM_CODES = [p for p in PERMISSIONS if p[0].startswith("target:")]


async def main() -> int:
    created_perms: list[str] = []
    granted: list[str] = []
    missing_roles: list[str] = []
    async with AsyncSessionLocal() as db:
        # 1) 权限码
        for code, resource, action, desc in TARGET_PERM_CODES:
            existing = (
                await db.execute(select(Permission).where(Permission.permission_code == code))
            ).scalar_one_or_none()
            if existing is None:
                db.add(Permission(permission_code=code, resource=resource, action=action,
                                  description=desc, is_system=True))
                created_perms.append(code)
        await db.flush()
        perm_map = {
            p.permission_code: p.permission_id
            for p in (await db.execute(select(Permission))).scalars()
        }

        # 2) 角色挂载（按 seed_data.ROLES 里的 target:* 授权）
        for role_code, _name, _desc, perm_codes in ROLES:
            if perm_codes == "ALL":
                continue  # SYS_ADMIN 代码短路
            wanted = [c for c in perm_codes if c.startswith("target:")]
            if not wanted:
                continue
            role = (
                await db.execute(
                    select(Role).where(Role.role_code == role_code, Role.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            if role is None:
                missing_roles.append(role_code)
                continue
            for c in wanted:
                pid = perm_map[c]
                rp = (
                    await db.execute(
                        select(RolePermission).where(
                            RolePermission.role_id == role.role_id,
                            RolePermission.permission_id == pid,
                        )
                    )
                ).scalar_one_or_none()
                if rp is None:
                    db.add(RolePermission(role_id=role.role_id, permission_id=pid))
                    granted.append(f"{role_code}:{c}")
        await db.commit()
    await engine.dispose()
    print(f"created_permissions={created_perms}")
    print(f"granted={granted}")
    if missing_roles:
        print(f"WARN missing roles (skipped)={missing_roles}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
