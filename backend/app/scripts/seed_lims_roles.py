"""幂等新增「LIMS 看板」三角色（供 cmc-rd-lims-dashboard 按 role_code 做权限分级）。

这些角色不授予 MDM 内部权限，只作为身份标签写入 JWT.roles，由 LIMS 看板系统解释：
  - CMC_LIMS_ANALYST  检验分析员   LIMS 看板：查看
  - CMC_LIMS_CHEMIST  检验化学家   LIMS 看板：查看 + 导出
  - CMC_LIMS_ADMIN    LIMS 管理员  LIMS 看板：查看 + 导出 + Admin 后台维护（标准工时/检项/人员）

反复运行安全：按 role_code 判重（仅未软删的行），已存在则跳过。
运行：`uv run python -m app.scripts.seed_lims_roles`
"""
import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.domains.auth.models import Role

LIMS_ROLES = [
    ("CMC_LIMS_ANALYST", "检验分析员", "LIMS 看板：查看"),
    ("CMC_LIMS_CHEMIST", "检验化学家", "LIMS 看板：查看 + 导出"),
    ("CMC_LIMS_ADMIN", "LIMS 管理员", "LIMS 看板：查看 + 导出 + Admin 后台维护（标准工时/检项/人员）"),
]


async def main() -> int:
    created: list[str] = []
    skipped: list[str] = []
    async with AsyncSessionLocal() as db:
        for code, name, desc in LIMS_ROLES:
            existing = (
                await db.execute(
                    select(Role).where(Role.role_code == code, Role.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            if existing is not None:
                skipped.append(code)
                continue
            db.add(Role(role_code=code, role_name=name, description=desc, is_system=False))
            created.append(code)
        await db.commit()
    await engine.dispose()
    print(f"created={created} skipped(exists)={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
