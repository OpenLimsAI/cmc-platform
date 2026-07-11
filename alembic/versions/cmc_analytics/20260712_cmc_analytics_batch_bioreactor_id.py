"""cmc_analytics: batch 容器物理罐字段 equipment_ref → bioreactor_id（2026-07-12）

统一"罐号 = 物理罐 = 同一个东西"的模型：不再有独立"物理罐"字段，
容器的物理罐编号统一叫 bioreactor_id（值如 A1/B3/R2）。

- batch_vessel.equipment_ref 列改名为 bioreactor_id。
- 重建 v_batch_dim：去掉旧的、含义不准的 `stage_code AS bioreactor_id` 别名；
  改为暴露 stage_code（培养阶段/命名码）+ bioreactor_id（罐号：产物罐=stage_code、
  种子罐=物理罐列、摇瓶=空）。下游看板/vicell 只用 batch_key/generation/
  seeded_from_stages，本次不动这些列，不受影响。

Revision ID: cmc_analytics_batch_bioreactor
Revises: cmc_analytics_batch_edit_log
Create Date: 2026-07-12
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_bioreactor"
down_revision = "cmc_analytics_batch_edit_log"
branch_labels = None
depends_on = None

_READERS = "lims_reader, quality_user"


def _create_view(bioreactor_expr: str) -> None:
    op.execute("DROP VIEW IF EXISTS batch.v_batch_dim")
    op.execute(
        f"""
        CREATE VIEW batch.v_batch_dim AS
        SELECT
            (r.business_batch_no || '-' || v.stage_code)  AS vessel_key,
            r.business_batch_no                            AS batch_no,
            r.project_code, r.project_ref, r.project_source, r.year_yy, r.seq,
            v.stage_code,
            v.kind,
            v.train_stage                                  AS generation,
            {bioreactor_expr}                              AS bioreactor_id,
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
    op.execute(f"GRANT SELECT ON batch.v_batch_dim TO {_READERS}")


def upgrade() -> None:
    # 视图依赖该列，先删视图再改列名，最后按新列重建
    op.execute("DROP VIEW IF EXISTS batch.v_batch_dim")
    op.execute("ALTER TABLE batch.batch_vessel RENAME COLUMN equipment_ref TO bioreactor_id")
    # 罐号：产物罐 = stage_code（本身即罐号）；其余取物理罐列 bioreactor_id
    _create_view(
        "COALESCE(v.bioreactor_id, CASE WHEN v.kind = 'production_reactor' THEN v.stage_code END)"
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS batch.v_batch_dim")
    op.execute("ALTER TABLE batch.batch_vessel RENAME COLUMN bioreactor_id TO equipment_ref")
    # 恢复旧视图定义（stage_code AS bioreactor_id + equipment_ref）
    op.execute(
        f"""
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
    op.execute(f"GRANT SELECT ON batch.v_batch_dim TO {_READERS}")
