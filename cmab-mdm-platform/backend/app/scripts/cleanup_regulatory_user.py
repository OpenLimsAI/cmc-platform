"""一次性清理脚本：移除 REGULATORY_USER 角色（E12 方案 A，2026-06-06 决议）。

背景：
  DM-MDM-001 V1.1 §4.3 seed 列有 REGULATORY_USER，但 seed_data.py 从未包含该角色，
  正常通过 make seed 初始化的库不会存在此行。本脚本用于多机环境（Mac/PC/Linux 各自
  PG 实例）兜底——若某台机器曾按 DM 文档手工执行过 §4.3 的 INSERT，则按以下步骤清理：

  1. 查 auth.role 中 role_code='REGULATORY_USER'（未软删）的 role_id
  2. 物理删除 auth.user_role 中关联该 role_id 的行（先输出受影响 user_id 供手动通知）
  3. 软删除 auth.role 该行（deleted_at=NOW()，保留审计，不物理删）

幂等：角色不存在或已软删时输出 no-op 并正常退出。

用法：
  docker compose -f deploy/docker-compose.dev.yml exec backend \
      python -m app.scripts.cleanup_regulatory_user
"""

import asyncio

from loguru import logger
from sqlalchemy import text

from app.core.database import AsyncSessionLocal

ROLE_CODE = "REGULATORY_USER"


async def main() -> None:
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                text(
                    "SELECT role_id, deleted_at FROM auth.role "
                    "WHERE role_code = :code"
                ),
                {"code": ROLE_CODE},
            )
        ).first()

        if row is None:
            logger.info(f"no-op：auth.role 不存在 {ROLE_CODE}（本机从未 seed 过该角色）")
            return
        if row.deleted_at is not None:
            logger.info(f"no-op：{ROLE_CODE}（role_id={row.role_id}）已于 {row.deleted_at} 软删除")
            return

        role_id = row.role_id

        user_ids = [
            r.user_id
            for r in (
                await session.execute(
                    text("SELECT user_id FROM auth.user_role WHERE role_id = :rid"),
                    {"rid": role_id},
                )
            ).all()
        ]
        if user_ids:
            logger.warning(
                f"以下 {len(user_ids)} 个用户持有 {ROLE_CODE}，解除绑定后请手动通知："
                f"user_id={user_ids}"
            )
            await session.execute(
                text("DELETE FROM auth.user_role WHERE role_id = :rid"),
                {"rid": role_id},
            )
        else:
            logger.info(f"{ROLE_CODE} 无任何用户绑定")

        await session.execute(
            text("UPDATE auth.role SET deleted_at = NOW() WHERE role_id = :rid"),
            {"rid": role_id},
        )
        await session.commit()
        logger.info(f"完成：{ROLE_CODE}（role_id={role_id}）已软删除，user_role 解绑 {len(user_ids)} 行")


if __name__ == "__main__":
    asyncio.run(main())
