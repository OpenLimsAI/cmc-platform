"""cmc_analytics: batch 容器谱系改多父（支持合并接种，2026-07-11）

实际会有「多个摇瓶种子合并接种下一级罐」的情况，一个容器可有多个父。
把 batch_vessel.parent_vessel_id（单父列）改为 batch_vessel_genealogy（边表，多父）。

Revision ID: cmc_analytics_batch_multiparent
Revises: cmc_analytics_batch_model_v2
Create Date: 2026-07-11
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_multiparent"
down_revision = "cmc_analytics_batch_model_v2"
branch_labels = None
depends_on = None

_READERS = "lims_reader, quality_user"


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS batch.v_batch_lineage")
    op.execute("DROP VIEW IF EXISTS batch.v_batch_dim")

    op.execute(
        """
        CREATE TABLE batch.batch_vessel_genealogy (
            parent_vessel_id bigint      NOT NULL REFERENCES batch.batch_vessel(vessel_id) ON DELETE CASCADE,
            child_vessel_id  bigint      NOT NULL REFERENCES batch.batch_vessel(vessel_id) ON DELETE CASCADE,
            relation         varchar(16) NOT NULL DEFAULT 'seeded_from',
            created_at       timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (parent_vessel_id, child_vessel_id, relation),
            CONSTRAINT ck_bvg_no_self CHECK (parent_vessel_id <> child_vessel_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_bvg_child ON batch.batch_vessel_genealogy(child_vessel_id)")
    op.execute("CREATE INDEX ix_bvg_parent ON batch.batch_vessel_genealogy(parent_vessel_id)")

    # 迁移旧的单父数据 → 边表
    op.execute(
        """
        INSERT INTO batch.batch_vessel_genealogy(parent_vessel_id, child_vessel_id, relation)
        SELECT parent_vessel_id, vessel_id, 'seeded_from'
        FROM batch.batch_vessel WHERE parent_vessel_id IS NOT NULL
        """
    )
    op.execute("ALTER TABLE batch.batch_vessel DROP COLUMN parent_vessel_id")

    # 维度视图：父容器可能多个 → 聚合成字符串
    op.execute(
        """
        CREATE VIEW batch.v_batch_dim AS
        SELECT
            (r.business_batch_no || '-' || v.stage_code)  AS vessel_key,
            r.business_batch_no                            AS batch_no,
            r.project_code, r.project_ref, r.project_source, r.year_yy, r.seq,
            v.stage_code                                   AS bioreactor_id,
            v.kind,
            v.train_stage                                  AS generation,
            v.equipment_ref,
            v.planned_days,
            v.status,
            r.campaign_type                                AS culture_campaign,
            r.gen_date,
            (r.project_code || '_' || r.year_yy || r.seq || '_' || v.stage_code) AS batch_key,
            (SELECT string_agg(p.stage_code, ',' ORDER BY p.stage_code)
               FROM batch.batch_vessel_genealogy g
               JOIN batch.batch_vessel p ON p.vessel_id = g.parent_vessel_id
              WHERE g.child_vessel_id = v.vessel_id)       AS seeded_from_stages
        FROM batch.batch_vessel v
        JOIN batch.batch_register r ON r.batch_id = v.batch_id
        """
    )
    op.execute(
        """
        CREATE VIEW batch.v_batch_lineage AS
        SELECT
            (r.business_batch_no || '-' || p.stage_code) AS parent_vessel_key,
            (r.business_batch_no || '-' || c.stage_code) AS child_vessel_key,
            g.relation
        FROM batch.batch_vessel_genealogy g
        JOIN batch.batch_vessel c ON c.vessel_id = g.child_vessel_id
        JOIN batch.batch_vessel p ON p.vessel_id = g.parent_vessel_id
        JOIN batch.batch_register r ON r.batch_id = c.batch_id
        """
    )
    op.execute(f"GRANT SELECT ON batch.v_batch_dim, batch.v_batch_lineage TO {_READERS}")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS batch.v_batch_lineage")
    op.execute("DROP VIEW IF EXISTS batch.v_batch_dim")
    op.execute("ALTER TABLE batch.batch_vessel ADD COLUMN parent_vessel_id bigint REFERENCES batch.batch_vessel(vessel_id)")
    op.execute(
        """
        UPDATE batch.batch_vessel v SET parent_vessel_id = (
            SELECT g.parent_vessel_id FROM batch.batch_vessel_genealogy g
            WHERE g.child_vessel_id = v.vessel_id ORDER BY g.parent_vessel_id LIMIT 1)
        """
    )
    op.execute("DROP TABLE IF EXISTS batch.batch_vessel_genealogy")
    # 视图恢复见 batch_model_v2（此处从简，仅回列）
