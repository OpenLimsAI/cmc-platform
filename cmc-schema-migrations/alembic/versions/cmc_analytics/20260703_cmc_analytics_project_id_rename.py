"""cmc_analytics：staging 的 project_code 统一改名为 project_id（2026-07-03）

staging.stg_batch 与 staging.stg_vicell_run 里表示"项目编号"的列原叫 project_code，
与 cmc_analytics/cmc_rd 主流叫法（stg_sample.project_id 等，均为 text）不一致。
统一改名 project_code -> project_id。用 RENAME COLUMN 保留已有数据。

牵连：mart.dim_batch 视图引用该列 -> 需 DROP + 重建并补回 GRANT；
配套 ETL rd-lucullus-etl/lucullus_build_batch_dim.py 的 STG_COLUMNS/row 同步改。

注意：cmc_data_platform.cost_accounting.projects.project_code 是另一语义（业务编码，
另有 project_id bigint 主键），不在本次改名范围。

Revision ID: cmc_analytics_project_id
Revises: cmc_analytics_stg_vicell
Create Date: 2026-07-03
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_project_id"
down_revision = "cmc_analytics_stg_vicell"
branch_labels = None
depends_on = None

_VIEW_COLS = """
    batch_key,
    {project_col},
    batch_number,
    batch_year,
    experiment_purpose,
    bioreactor_code,
    line_code,
    source_instance,
    procid,
    procname_raw,
    starttime,
    endtime,
    duration_days,
    parse_status
"""


def _recreate_dim_batch(project_col: str) -> None:
    op.execute("DROP VIEW IF EXISTS mart.dim_batch")
    op.execute(
        f"CREATE VIEW mart.dim_batch AS SELECT {_VIEW_COLS.format(project_col=project_col)} "
        "FROM staging.stg_batch"
    )
    op.execute(
        "COMMENT ON VIEW mart.dim_batch IS "
        "'看板消费的批次维度（v1=stg_batch 视图）。将来多数据源汇入时改为物化表。'"
    )
    op.execute("GRANT SELECT ON mart.dim_batch TO lucullus_etl")


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS mart.dim_batch")  # 先撤依赖列的视图
    op.execute("ALTER TABLE staging.stg_batch RENAME COLUMN project_code TO project_id")
    op.execute("ALTER TABLE staging.stg_vicell_run RENAME COLUMN project_code TO project_id")
    _recreate_dim_batch("project_id")
    op.execute(
        "COMMENT ON COLUMN staging.stg_batch.batch_key IS "
        "'标准批次键 = project_id_batch_number_bioreactor_code（罐号取权威 reactor_name），拼不出则 NULL。'"
    )
    op.execute(
        "COMMENT ON COLUMN staging.stg_vicell_run.batch_key IS "
        "'标准批次键 = project_id_batch_number_bioreactor_code，与 stg_batch 对齐；拼不出则 NULL。'"
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS mart.dim_batch")
    op.execute("ALTER TABLE staging.stg_batch RENAME COLUMN project_id TO project_code")
    op.execute("ALTER TABLE staging.stg_vicell_run RENAME COLUMN project_id TO project_code")
    _recreate_dim_batch("project_code")
