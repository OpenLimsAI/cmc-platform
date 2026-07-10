"""cmc_analytics: batch 状态历史触发器（F4 审计，2026-07-11）

发号即留痕、每次状态流转自动记 batch_status_history：
  - AFTER INSERT：记初始状态（old=NULL → new=issued）
  - AFTER UPDATE OF status：记 old→new
changed_by 取会话 GUC `batch.actor`（应用可 SET LOCAL），缺省 'system'。

Revision ID: cmc_analytics_batch_status_trig
Revises: cmc_analytics_batch_views
Create Date: 2026-07-11
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_status_trig"
down_revision = "cmc_analytics_batch_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION batch.fn_batch_status_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            actor text := coalesce(nullif(current_setting('batch.actor', true), ''), 'system');
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO batch.batch_status_history(batch_id, old_status, new_status, changed_by)
                VALUES (NEW.batch_id, NULL, NEW.status, actor);
            ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
                INSERT INTO batch.batch_status_history(batch_id, old_status, new_status, changed_by)
                VALUES (NEW.batch_id, OLD.status, NEW.status, actor);
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_batch_status_init
            AFTER INSERT ON batch.batch_register
            FOR EACH ROW EXECUTE FUNCTION batch.fn_batch_status_history()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_batch_status_change
            AFTER UPDATE OF status ON batch.batch_register
            FOR EACH ROW EXECUTE FUNCTION batch.fn_batch_status_history()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_batch_status_change ON batch.batch_register")
    op.execute("DROP TRIGGER IF EXISTS trg_batch_status_init ON batch.batch_register")
    op.execute("DROP FUNCTION IF EXISTS batch.fn_batch_status_history()")
