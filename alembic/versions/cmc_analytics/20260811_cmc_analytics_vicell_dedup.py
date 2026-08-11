"""cmc_analytics：mart.fact_vicell 去重 dim_batch 关联（2026-08-11）

与 cmc_analytics_fact_nova_dedup 同因同修：dim_batch 有 23 个 batch_key 重复
（同批号多条工艺记录，如中途重启），LEFT JOIN 后 fact_vicell 行数(16701)比
stg_vicell_run(16620)多 81 行，生长曲线会出重复点。改为先按 batch_key 去重再
关联：优先取有 Lucullus 关联(procid 非空)、starttime 最新的一条。

列名列序与原版完全一致，看板接口无感。

Revision ID: cmc_analytics_fact_vicell_dedup
Revises: cmc_analytics_fact_nova_dedup
Create Date: 2026-08-11

注：revision id 保持 ≤32 字符，否则超 alembic_version.version_num varchar(32) 会落库失败。
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_fact_vicell_dedup"
down_revision = "cmc_analytics_fact_nova_dedup"
branch_labels = None
depends_on = None

_SELECT_COLS = """
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
            -- 批次维度（batch_key 先去重再关联）
            b.experiment_purpose,
            b.line_code,
            b.batch_year,
            b.procid          AS lucullus_procid,
            b.starttime       AS batch_starttime,
            b.endtime         AS batch_endtime,
            b.duration_days   AS batch_duration_days,
            b.parse_status    AS batch_parse_status
        FROM staging.stg_vicell_run v
"""


def upgrade() -> None:
    op.execute(
        f"""
        DROP VIEW mart.fact_vicell;
        CREATE VIEW mart.fact_vicell AS
        {_SELECT_COLS}
        LEFT JOIN (
            SELECT DISTINCT ON (batch_key) *
            FROM mart.dim_batch
            WHERE batch_key IS NOT NULL
            ORDER BY batch_key, (procid IS NULL), starttime DESC NULLS LAST
        ) b ON b.batch_key = v.batch_key;

        COMMENT ON VIEW mart.fact_vicell IS
            'Vi-CELL 生长曲线事实（每批次-罐-培养天一行）。stg_vicell_run 左连去重后的 dim_batch。'
            'Phase 2 将并入每天工艺参数。';

        GRANT SELECT ON mart.fact_vicell TO lims_reader, quality_user;
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DROP VIEW mart.fact_vicell;
        CREATE VIEW mart.fact_vicell AS
        {_SELECT_COLS}
        LEFT JOIN mart.dim_batch b ON b.batch_key = v.batch_key;
        GRANT SELECT ON mart.fact_vicell TO lims_reader, quality_user;
        """
    )
