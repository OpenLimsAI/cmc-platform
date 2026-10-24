"""cmc_analytics: 研发批号系统审计追踪表 batch.audit_log（2026-07-15）

记录用户操作留痕（合规）：登录 / 登出 / 新建批次 / 修改 / 删除 / 打印标签 等，
含操作人、动作、对象、明细、客户端 IP。append-only，只查不改。

Revision ID: cmc_analytics_batch_audit_log
Revises: cmc_analytics_batch_seq3_global
Create Date: 2026-07-15
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_audit_log"
down_revision = "cmc_analytics_batch_seq3_global"
branch_labels = None
depends_on = None

_READERS = "lims_reader, quality_user"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE batch.audit_log (
            id          bigserial   PRIMARY KEY,
            ts          timestamptz NOT NULL DEFAULT now(),
            username    varchar(64) NOT NULL,
            action      varchar(24) NOT NULL,   -- login/logout/create/modify/delete/print/...
            target_type varchar(32),            -- experiment/vessel/sample/session...
            target_id   varchar(64),            -- 业务批号 / vessel_id / ...
            detail      text,                    -- 人读描述（或 JSON 片段）
            ip_address  varchar(64),             -- 客户端 IP（经 nginx X-Forwarded-For）
            user_agent  varchar(256)
        )
        """
    )
    op.execute("CREATE INDEX ix_audit_log_ts ON batch.audit_log (ts DESC)")
    op.execute("CREATE INDEX ix_audit_log_username ON batch.audit_log (username)")
    op.execute("CREATE INDEX ix_audit_log_action ON batch.audit_log (action)")
    op.execute(f"GRANT SELECT ON batch.audit_log TO {_READERS}")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS batch.audit_log")
