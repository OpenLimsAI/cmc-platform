"""cmc_analytics: batch 容器字段编辑审计表（2026-07-11）

状态流转已有触发器审计（batch_vessel_status_history）。容器字段编辑
（拟定天数/物理罐/罐号、加/删容器）此前无留痕，这里补字段级审计表。
changed_by 由应用从 JWT 取真实操作人写入。

Revision ID: cmc_analytics_batch_edit_log
Revises: cmc_analytics_batch_multiparent
Create Date: 2026-07-11
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_edit_log"
down_revision = "cmc_analytics_batch_multiparent"
branch_labels = None
depends_on = None

_READERS = "lims_reader, quality_user"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE batch.batch_vessel_edit_log (
            id          bigserial   PRIMARY KEY,
            batch_id    bigint      NOT NULL,
            vessel_id   bigint,                       -- 删除后置空
            stage_code  varchar(8),                   -- 快照，便于删除后仍可读
            action      varchar(16) NOT NULL,         -- add / update / delete
            field       varchar(32),                  -- update 时的字段名
            old_value   text,
            new_value   text,
            changed_by  varchar(64) NOT NULL DEFAULT 'system',
            changed_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_bvel_vessel ON batch.batch_vessel_edit_log(vessel_id)")
    op.execute("CREATE INDEX ix_bvel_batch ON batch.batch_vessel_edit_log(batch_id)")
    op.execute(f"GRANT SELECT ON batch.batch_vessel_edit_log TO {_READERS}")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS batch.batch_vessel_edit_log")
