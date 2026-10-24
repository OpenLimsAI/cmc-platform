"""cmc_analytics: batch 看板消费维度视图 + 样品名→批号函数 + 只读授权（2026-07-11）

给看板 cmc-rd-usp-dashboard JOIN 用：
  - batch.v_batch_dim       一行一容器批号（罐号/代次/物理罐/用途/父批号/batch_key）
  - batch.v_batch_lineage   谱系边
  - batch.fn_sample_to_batch(text) 样品名→批号（剥 -D##[-T#]）
只读账号（lims_reader, quality_user）授 USAGE + SELECT（视图）+ EXECUTE（函数）。
看板用法：JOIN batch.v_batch_dim ON batch_no = batch.fn_sample_to_batch(sample_id)。

Revision ID: cmc_analytics_batch_views
Revises: cmc_analytics_batch_schema
Create Date: 2026-07-11
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_views"
down_revision = "cmc_analytics_batch_schema"
branch_labels = None
depends_on = None

_READERS = "lims_reader, quality_user"


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION batch.fn_sample_to_batch(sample_name text)
        RETURNS text LANGUAGE sql IMMUTABLE AS $$
          SELECT substring(
            sample_name FROM '^([0-9]{3}-[0-9]{4}-[A-Z]{1,3}[0-9]{0,2})(-D[0-9]{1,2}(-T[0-9]+)?)?$'
          );
        $$
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW batch.v_batch_dim AS
        SELECT
            r.business_batch_no                                       AS batch_no,
            (r.project_code || '-' || r.year_yy || r.seq)             AS lot_core,
            r.project_code,
            r.project_ref,
            r.project_source,
            r.year_yy,
            r.seq,
            r.stage_code                                              AS bioreactor_id,
            r.train_stage                                             AS generation,
            r.equipment_ref,
            r.campaign_type                                           AS culture_campaign,
            r.status,
            r.gen_date,
            (r.project_code || '_' || r.year_yy || r.seq || '_' || r.stage_code) AS batch_key,
            p.business_batch_no                                       AS seeded_from_batch_no
        FROM batch.batch_register r
        LEFT JOIN LATERAL (
            SELECT pr.business_batch_no
            FROM batch.batch_genealogy g
            JOIN batch.batch_register pr ON pr.batch_id = g.parent_batch_id
            WHERE g.child_batch_id = r.batch_id AND g.relation = 'seeded_from'
            ORDER BY pr.batch_id
            LIMIT 1
        ) p ON true
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW batch.v_batch_lineage AS
        SELECT
            pp.business_batch_no AS parent_batch_no,
            cc.business_batch_no AS child_batch_no,
            g.relation
        FROM batch.batch_genealogy g
        JOIN batch.batch_register pp ON pp.batch_id = g.parent_batch_id
        JOIN batch.batch_register cc ON cc.batch_id = g.child_batch_id
        """
    )

    op.execute(f"GRANT USAGE ON SCHEMA batch TO {_READERS}")
    op.execute(f"GRANT SELECT ON batch.v_batch_dim, batch.v_batch_lineage TO {_READERS}")
    op.execute(f"GRANT EXECUTE ON FUNCTION batch.fn_sample_to_batch(text) TO {_READERS}")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS batch.v_batch_lineage")
    op.execute("DROP VIEW IF EXISTS batch.v_batch_dim")
    op.execute("DROP FUNCTION IF EXISTS batch.fn_sample_to_batch(text)")
