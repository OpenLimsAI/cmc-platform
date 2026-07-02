"""cmc_analytics：staging 的 bioreactor_code 改名为 bioreactor_id（2026-07-03）

与 project_code→project_id 同批口径统一：staging.stg_batch 与 staging.stg_vicell_run
的罐号列 bioreactor_code → bioreactor_id。用 RENAME COLUMN 保留数据。

牵连：mart.dim_batch 视图引用该列 -> DROP+重建并补回 GRANT；
配套 ETL rd-lucullus-etl/lucullus_build_batch_dim.py 的 STG_COLUMNS/row 同步改。

Revision ID: cmc_analytics_bioreactor_id
Revises: cmc_analytics_project_id
Create Date: 2026-07-03
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_bioreactor_id"
down_revision = "cmc_analytics_project_id"
branch_labels = None
depends_on = None


def _recreate_dim_batch(reactor_col: str) -> None:
    op.execute("DROP VIEW IF EXISTS mart.dim_batch")
    op.execute(
        f"""
        CREATE VIEW mart.dim_batch AS
        SELECT
            batch_key, project_id, batch_number, batch_year, experiment_purpose,
            {reactor_col}, line_code, source_instance, procid, procname_raw,
            starttime, endtime, duration_days, parse_status
        FROM staging.stg_batch
        """
    )
    op.execute(
        "COMMENT ON VIEW mart.dim_batch IS "
        "'看板消费的批次维度（v1=stg_batch 视图）。将来多数据源汇入时改为物化表。'"
    )
    op.execute("GRANT SELECT ON mart.dim_batch TO lucullus_etl")


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS mart.dim_batch")
    op.execute("ALTER TABLE staging.stg_batch RENAME COLUMN bioreactor_code TO bioreactor_id")
    op.execute("ALTER TABLE staging.stg_vicell_run RENAME COLUMN bioreactor_code TO bioreactor_id")
    _recreate_dim_batch("bioreactor_id")
    op.execute(
        "COMMENT ON COLUMN staging.stg_batch.batch_key IS "
        "'标准批次键 = project_id_batch_number_bioreactor_id（罐号取权威 reactor_name），拼不出则 NULL。'"
    )
    op.execute(
        "COMMENT ON COLUMN staging.stg_batch.bioreactor_id IS '权威罐号，来自 signal_timeseries.reactor_name。'"
    )
    op.execute(
        "COMMENT ON COLUMN staging.stg_vicell_run.batch_key IS "
        "'标准批次键 = project_id_batch_number_bioreactor_id，与 stg_batch 对齐；拼不出则 NULL。'"
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS mart.dim_batch")
    op.execute("ALTER TABLE staging.stg_batch RENAME COLUMN bioreactor_id TO bioreactor_code")
    op.execute("ALTER TABLE staging.stg_vicell_run RENAME COLUMN bioreactor_id TO bioreactor_code")
    _recreate_dim_batch("bioreactor_code")
