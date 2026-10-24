"""cmc_analytics: batch_vessel_edit_log 补外键（删批级联 / 删容器置空）

batch_vessel_edit_log（容器字段编辑审计）建表时未挂外键：删批次时
它不随主表级联清除、会留孤儿行（清理测试批时踩到，须手工删）。这里补两个外键，
各司其职、与建表注释一致：

  - batch_id  → batch_register(batch_id)  ON DELETE CASCADE
      删整批时审计随批一起清（符合"删除整个批次"语义）。
  - vessel_id → batch_vessel(vessel_id)   ON DELETE SET NULL
      删单个容器时审计行**保留**、vessel_id 置空（stage_code 已是快照，
      "删除后仍可读"——保住字段级审计留痕）。

加外键前先修历史悬空行：batch_id 孤儿删除、vessel_id 悬空置空，
保证约束能建上。幂等（悬空为 0 时无副作用）。

Revision ID: cmc_analytics_batch_editlog_fk
Revises: cmc_analytics_stg_nova_prod
Create Date: 2026-07-30

注：本迁移逻辑上属 batch 域，但 cmc_analytics 是全库单一线性链，新迁移须接在
链尾（当前 head = stg_nova_prod），不能挂回 batch_startconf（那样会劈叉成多 head）。
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_editlog_fk"
down_revision = "cmc_analytics_stg_nova_prod"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) 清历史悬空行（否则加外键会失败）
    op.execute(
        """
        DELETE FROM batch.batch_vessel_edit_log el
        WHERE NOT EXISTS (
            SELECT 1 FROM batch.batch_register r WHERE r.batch_id = el.batch_id
        )
        """
    )
    op.execute(
        """
        UPDATE batch.batch_vessel_edit_log el
        SET vessel_id = NULL
        WHERE el.vessel_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM batch.batch_vessel v WHERE v.vessel_id = el.vessel_id
          )
        """
    )
    # 2) 补外键
    op.execute(
        """
        ALTER TABLE batch.batch_vessel_edit_log
          ADD CONSTRAINT fk_bvel_batch
            FOREIGN KEY (batch_id) REFERENCES batch.batch_register(batch_id)
            ON DELETE CASCADE,
          ADD CONSTRAINT fk_bvel_vessel
            FOREIGN KEY (vessel_id) REFERENCES batch.batch_vessel(vessel_id)
            ON DELETE SET NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE batch.batch_vessel_edit_log
          DROP CONSTRAINT IF EXISTS fk_bvel_vessel,
          DROP CONSTRAINT IF EXISTS fk_bvel_batch
        """
    )
