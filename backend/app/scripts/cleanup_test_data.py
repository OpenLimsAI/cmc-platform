"""清理自动化测试在 dev/staging 库累积的垃圾数据（自定义角色 + 测试用户）。

多机环境（Mac/PC/Linux 各自独立 PG 实例）通用。**默认 dry-run 只报告，
加 `--apply` 才真正删除**。删除前对每个候选用户扫描全部外键引用，
凡在业务表（substance/material/asset/... 的 created_by 等）留有引用的一律
跳过（不强删，避免破坏审计/业务数据链）。

匹配规则（自动化测试生成物的命名特征）：
  - 角色：role_code ~ '^CUSTOM_[0-9A-F]{8}$'（建角色接口自动生成的 8 位 hex 码）
  - 用户：username ~ '^(e2e|u|sec|ru)_[0-9a-f]+$'

用法（Linux 原生 venv）：
  cd backend && .venv/bin/python -m app.scripts.cleanup_test_data          # dry-run 报告
  cd backend && .venv/bin/python -m app.scripts.cleanup_test_data --apply  # 实际删除

用法（Mac docker dev）：
  docker compose -f deploy/docker-compose.dev.yml exec backend \
      python -m app.scripts.cleanup_test_data [--apply]

幂等：无垃圾时输出 no-op 正常退出。
"""

import argparse
import asyncio
import sys

from loguru import logger
from sqlalchemy import text

from app.core.database import AsyncSessionLocal

ROLE_PATTERN = r"^CUSTOM_[0-9A-F]{8}$"
USER_PATTERN = r"^(e2e|u|sec|ru)_[0-9a-f]+$"

# 删除用户时这三张 auth 域表的引用行会被一并清理（非业务数据）
AUTH_DEP_TABLES = {"user_role", "login_history", "refresh_token"}


async def _candidate_roles(session):
    rows = (
        await session.execute(
            text(
                "SELECT r.role_code, r.role_name, count(ur.user_id) AS user_count "
                "FROM auth.role r "
                "LEFT JOIN auth.user_role ur ON ur.role_id = r.role_id "
                "WHERE r.role_code ~ :pat "
                "GROUP BY r.role_code, r.role_name ORDER BY r.role_code"
            ),
            {"pat": ROLE_PATTERN},
        )
    ).all()
    return rows


async def _user_fk_columns(session):
    """所有外键引用 auth.user(user_id) 的 (schema, table, column)。"""
    return (
        await session.execute(
            text(
                "SELECT tc.table_schema, tc.table_name, kcu.column_name "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON kcu.constraint_name = tc.constraint_name "
                "JOIN information_schema.constraint_column_usage ccu "
                "  ON ccu.constraint_name = tc.constraint_name "
                "WHERE tc.constraint_type = 'FOREIGN KEY' "
                "  AND ccu.table_schema = 'auth' AND ccu.table_name = 'user' "
                "  AND ccu.column_name = 'user_id'"
            )
        )
    ).all()


async def _candidate_users(session):
    """返回 [(username, user_id, business_ref_count)]；business_ref_count>0 的不可删。"""
    users = (
        await session.execute(
            text(
                "SELECT user_id, username FROM auth.\"user\" WHERE username ~ :pat "
                "ORDER BY username"
            ),
            {"pat": USER_PATTERN},
        )
    ).all()
    if not users:
        return []

    ids = [u.user_id for u in users]
    fk_cols = await _user_fk_columns(session)

    # 统计每个候选用户在「业务表」（排除 3 张 auth 依赖表）的引用数
    ref_count = dict.fromkeys(ids, 0)
    for sch, tbl, col in fk_cols:
        if sch == "auth" and tbl in AUTH_DEP_TABLES:
            continue
        rows = (
            await session.execute(
                text(
                    f'SELECT "{col}" AS uid, count(*) AS c '
                    f'FROM "{sch}"."{tbl}" WHERE "{col}" = ANY(:ids) GROUP BY "{col}"'
                ),
                {"ids": ids},
            )
        ).all()
        for r in rows:
            ref_count[r.uid] = ref_count.get(r.uid, 0) + r.c

    return [(u.username, u.user_id, ref_count.get(u.user_id, 0)) for u in users]


async def main(apply: bool) -> None:
    async with AsyncSessionLocal() as session:
        roles = await _candidate_roles(session)
        users = await _candidate_users(session)

        deletable_users = [(n, i) for (n, i, c) in users if c == 0]
        skipped_users = [(n, i, c) for (n, i, c) in users if c > 0]

        logger.info("=== 测试垃圾数据清理 ({}） ===".format("APPLY" if apply else "DRY-RUN"))
        logger.info(f"候选自定义角色（{ROLE_PATTERN}）：{len(roles)}")
        for code, name, uc in roles:
            logger.info(f"  - {code}  «{name}»  持有用户={uc}")
        logger.info(f"候选测试用户（{USER_PATTERN}）：{len(users)}"
                    f"，可删={len(deletable_users)}，跳过(有业务引用)={len(skipped_users)}")
        for n, _i, c in skipped_users:
            logger.warning(f"  ! 跳过 {n}（业务表引用={c}，不强删）")

        if not roles and not deletable_users:
            logger.info("no-op：没有可清理的测试垃圾。")
            return

        if not apply:
            logger.info("")
            logger.info("以上为 DRY-RUN。确认无误后加 --apply 实际删除。")
            return

        # ---- 实际删除（单事务）----
        role_codes = [r.role_code for r in roles]
        user_ids = [i for (_n, i) in deletable_users]

        if role_codes:
            await session.execute(
                text(
                    "DELETE FROM auth.user_role WHERE role_id IN "
                    "(SELECT role_id FROM auth.role WHERE role_code = ANY(:codes))"
                ),
                {"codes": role_codes},
            )
            await session.execute(
                text(
                    "DELETE FROM auth.role_permission WHERE role_id IN "
                    "(SELECT role_id FROM auth.role WHERE role_code = ANY(:codes))"
                ),
                {"codes": role_codes},
            )
            await session.execute(
                text("DELETE FROM auth.role WHERE role_code = ANY(:codes)"),
                {"codes": role_codes},
            )

        if user_ids:
            for tbl in ("user_role", "login_history", "refresh_token"):
                await session.execute(
                    text(f"DELETE FROM auth.{tbl} WHERE user_id = ANY(:ids)"),
                    {"ids": user_ids},
                )
            await session.execute(
                text('DELETE FROM auth."user" WHERE user_id = ANY(:ids)'),
                {"ids": user_ids},
            )

        await session.commit()
        logger.info(f"✓ 已删除 {len(role_codes)} 个角色 + {len(user_ids)} 个用户。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="清理测试累积的垃圾角色/用户")
    parser.add_argument("--apply", action="store_true", help="实际删除（缺省为 dry-run）")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(apply=args.apply)))
