"""cmc_analytics：mart.fact_vicell —— Vi-CELL 生长曲线事实（2026-07-03）

Phase 1：把 staging.stg_vicell_run 与批次维度 mart.dim_batch 按 batch_key 关联，
每 (批次-罐-培养天) 一行，供看板画 VCD/viability 生长曲线并带批次上下文
（实验目的/产线/发酵起止）。视图形态（v1），将来汇入工艺曲线时可扩展/物化。

Phase 2（未做）：并入每天工艺参数需先有 signal_timeseries 的按天聚合中间层。

Revision ID: cmc_analytics_fact_vicell
Revises: cmc_analytics_bioreactor_id
Create Date: 2026-07-03
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_fact_vicell"
down_revision = "cmc_analytics_bioreactor_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE VIEW mart.fact_vicell AS
        SELECT
            v.run_id,
            v.source_instance,
            v.sample_id,
            v.batch_key,
            v.project_id,
            v.batch_number,
            v.bioreactor_id,
            v.culture_day,
            v.run_date,
            v.log_date,
            v.viable_per_ml,          -- VCD 活细胞密度（×10^6/mL）
            v.viability_pct,          -- 活率 %
            v.total_per_ml,
            v.total_cells,
            v.viable_cells,
            v.avg_diameter_um,
            v.avg_circularity,
            v.parse_status,
            -- 批次维度（按 batch_key 关联 dim_batch）
            b.experiment_purpose,
            b.line_code,
            b.batch_year,
            b.procid          AS lucullus_procid,
            b.starttime       AS batch_starttime,
            b.endtime         AS batch_endtime,
            b.duration_days   AS batch_duration_days,
            b.parse_status    AS batch_parse_status
        FROM staging.stg_vicell_run v
        LEFT JOIN mart.dim_batch b ON b.batch_key = v.batch_key;

        COMMENT ON VIEW mart.fact_vicell IS
            'Vi-CELL 生长曲线事实（每批次-罐-培养天一行）。stg_vicell_run 左连 dim_batch。'
            'Phase 2 将并入每天工艺参数。';
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS mart.fact_vicell")
