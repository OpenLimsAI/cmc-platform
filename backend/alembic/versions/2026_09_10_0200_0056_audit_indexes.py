"""审计与登录历史补索引；删掉一条从未被用过的死索引

Revision ID: 0056_audit_indexes
Revises: 0055_dept_admin
Create Date: 2026-09-10 02:00:00.000000

2026-09-10 体检发现（EXPLAIN ANALYZE 实测，Linux 正式库）：三个高频查询都没有可用索引，
现在表还小（audit_log 1672 行）所以感觉不出来，但 audit_log 是 append-only 且无保留策略，
涨到百万行后这三处会明显变慢，届时再加索引就得挑停服务窗口。趁小赶紧加。

1) 实体审计 Tab（物质/项目/物料/资产/靶点详情页的「审计」）
   查询：WHERE entity_table = 'material' AND entity_id = 123 ORDER BY log_id DESC LIMIT 50
   现状：现有 ix_audit_log_entity 前导列是 entity_schema，而这些查询**不带 entity_schema**，
        索引用不上 → 实测走 Seq Scan + Sort（46 个缓冲块只为取 0 行）。
   加：ix_audit_log_entity_tab_log (entity_table, entity_id, log_id DESC)
       带 WHERE entity_table IS NOT NULL —— 登录/登出类记录该列为空，占 32%（541/1672），
       排除掉可省三分之一体积；PG 能推出 `entity_table = 'x'` 蕴含 `IS NOT NULL`，照样命中。
   注：ix_audit_log_entity 仍保留 —— 靶点域的查询确实带 entity_schema（target/services.py:487）。

2) 全局审计按操作人筛选
   查询：WHERE username = 'admin' ORDER BY log_id DESC LIMIT 50
   现状：username 上没有任何索引 → 沿主键倒着扫并逐行过滤（实测为取 50 行丢弃 366 行）。
   加：ix_audit_log_username_log (username, log_id DESC)

3) 个人中心「登录历史」
   查询：WHERE user_id = 1 ORDER BY login_at DESC LIMIT 20
   现状：只有 (login_at DESC) 单列索引，user_id 只能当过滤条件（实测为取 20 行丢弃 288 行）。
   加：ix_login_history_user_time (user_id, login_at DESC)

4) 删 ix_audit_log_user_time (user_id, timestamp DESC)
   全仓库没有任何查询按 AuditLog.user_id 过滤（审计筛选用的是 username 字符串快照），
   pg_stat_user_indexes 里 idx_scan = 0 —— 它只在每次写审计时白白多维护一次。
   审计由触发器在每次业务写入时插入，这条开销是持续的。将来若真要按 user_id 查，再加回来即可。

安全性：纯索引变更，不动任何数据；建索引期间会短暂锁表写入，当前表小（<2 MB）耗时毫秒级。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0056_audit_indexes"
down_revision: str | None = "0055_dept_admin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_audit_log_entity_tab_log
            ON audit.audit_log (entity_table, entity_id, log_id DESC)
         WHERE entity_table IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_audit_log_username_log
            ON audit.audit_log (username, log_id DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_login_history_user_time
            ON auth.login_history (user_id, login_at DESC)
    """)
    op.execute("DROP INDEX IF EXISTS audit.ix_audit_log_user_time")


def downgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_audit_log_user_time
            ON audit.audit_log (user_id, "timestamp" DESC)
    """)
    op.execute("DROP INDEX IF EXISTS auth.ix_login_history_user_time")
    op.execute("DROP INDEX IF EXISTS audit.ix_audit_log_username_log")
    op.execute("DROP INDEX IF EXISTS audit.ix_audit_log_entity_tab_log")
