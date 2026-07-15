"""幂等新增「上游」三角色（供 rd-batch-registry 按 role_code 做权限分级）。

这些角色不授予 MDM 内部权限，只作为身份标签写入 JWT.roles，由研发批号登记系统解释：
  - CMC_USP_OPERATOR    上游操作员     只读 + 打印标签
  - CMC_USP_RESEARCHER  上游工艺研究员  操作员权限 + 新建批次 + 设开始日期 + 日常容器操作
  - CMC_USP_MANAGER     上游经理       研究员权限 + 修改已录入的开始日期等更高权限

反复运行安全：按 role_code 判重（仅未软删的行），已存在则跳过。
运行：`uv run python -m app.scripts.seed_usp_roles`
"""
import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.domains.auth.models import Role

USP_ROLES = [
    ("CMC_USP_OPERATOR", "上游操作员", "研发批号系统：只读 + 打印标签"),
    ("CMC_USP_RESEARCHER", "上游工艺研究员", "研发批号系统：操作员权限 + 新建批次 + 设开始日期 + 日常容器操作"),
    ("CMC_USP_MANAGER", "上游经理", "研发批号系统：研究员权限 + 修改已录入的开始日期等更高权限"),
]


async def main() -> int:
    created: list[str] = []
    skipped: list[str] = []
    async with AsyncSessionLocal() as db:
        for code, name, desc in USP_ROLES:
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
