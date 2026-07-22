"""cmc_analytics: 留种供种——batch_vessel 加维持标记 + 跨批种子来源指针（2026-07-22）

支持"在摇瓶/罐子里留一份种子持续维持、供后续批次复用"（设计见 rd-batch-registry
docs/留种供种设计_种子维持与跨批复用.md）。给 batch.batch_vessel 增 4 列：

  - hold_status          维持状态：NULL=非留种 / holding=维持中 / terminated=已终止 / supplied_out=已全部供种
  - hold_ended_on        维持结束日（终止或全部供种当天）；撞罐用它给"开放式占用"封口
  - seed_source_vessel_id 跨批来源指针：本容器种子来自哪只（另一批的）容器（溯源用，非谱系边）
  - seed_supply_mode     取种方式：full=全部 / partial=部分

不改命名/正则/视图；纯加列 + 枚举 CHECK + 自引用 FK + 维持状态索引。既有行 4 列均为
NULL（=非留种、无来源），ADD 约束不会失败。

Revision ID: cmc_analytics_batch_seedhold
Revises: cmc_analytics_batch_proj_open
Create Date: 2026-07-22
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_seedhold"
down_revision = "cmc_analytics_batch_proj_open"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE batch.batch_vessel
          ADD COLUMN hold_status           varchar(16),
          ADD COLUMN hold_ended_on         date,
          ADD COLUMN seed_source_vessel_id bigint,
          ADD COLUMN seed_supply_mode      varchar(8)
        """
    )
    op.execute(
        """
        ALTER TABLE batch.batch_vessel
          ADD CONSTRAINT ck_batch_vessel_hold_status
          CHECK (hold_status IS NULL OR hold_status IN ('holding','terminated','supplied_out'))
        """
    )
    op.execute(
        """
        ALTER TABLE batch.batch_vessel
          ADD CONSTRAINT ck_batch_vessel_supply_mode
          CHECK (seed_supply_mode IS NULL OR seed_supply_mode IN ('full','partial'))
        """
    )
    # 跨批来源指针：自引用 FK；源容器万一被删则置空（不牵连下游容器）
    op.execute(
        """
        ALTER TABLE batch.batch_vessel
          ADD CONSTRAINT fk_batch_vessel_seed_source
          FOREIGN KEY (seed_source_vessel_id)
          REFERENCES batch.batch_vessel (vessel_id) ON DELETE SET NULL
        """
    )
    # "维持中/种子库"页按 hold_status 过滤，加部分索引
    op.execute(
        """
        CREATE INDEX ix_batch_vessel_holding
          ON batch.batch_vessel (hold_status)
          WHERE hold_status = 'holding'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS batch.ix_batch_vessel_holding")
    op.execute("ALTER TABLE batch.batch_vessel DROP CONSTRAINT IF EXISTS fk_batch_vessel_seed_source")
    op.execute("ALTER TABLE batch.batch_vessel DROP CONSTRAINT IF EXISTS ck_batch_vessel_supply_mode")
    op.execute("ALTER TABLE batch.batch_vessel DROP CONSTRAINT IF EXISTS ck_batch_vessel_hold_status")
    op.execute(
        """
        ALTER TABLE batch.batch_vessel
          DROP COLUMN IF EXISTS seed_supply_mode,
          DROP COLUMN IF EXISTS seed_source_vessel_id,
          DROP COLUMN IF EXISTS hold_ended_on,
          DROP COLUMN IF EXISTS hold_status
        """
    )
