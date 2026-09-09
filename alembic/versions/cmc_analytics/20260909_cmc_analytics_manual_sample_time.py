"""cmc_analytics: manual.sample_result 加取样时刻与样品名，支持同一样品一天多次取样（2026-09-09）

负责人要求：渗透压录入要带取样时刻（自动从 Nova / Vi-CELL 原始记录带出），一天多次取样时可各自
录入时刻并给样品名加 -T1 这类尾缀。因此：
  - 加 sampled_at（timestamptz，取样时刻，可空：历史补录的没有）、sample_name（标准样品名，可空）。
  - "最新值"视图 mart.fact_manual_latest 的去重键从 (批次, 指标, 天) 改为 (批次, 指标, 天, 样品名)，
    同一天不同样品名（-T1 / -T2）各留一行；样品名为空的老数据仍按天一行。

Revision ID: cmc_analytics_manual_sample_time
Revises: cmc_analytics_manual_sample
Create Date: 2026-09-09
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_manual_sample_time"
down_revision = "cmc_analytics_manual_sample"
branch_labels = None
depends_on = None

_READERS = "lims_reader, quality_user"

_VIEW = """
    CREATE VIEW mart.fact_manual_latest AS
    SELECT DISTINCT ON (batch_key, metric_code, culture_day, coalesce(sample_name, ''))
        result_id, batch_key, culture_day, sample_date, sampled_at, sample_name, metric_code, value, unit,
        note, source_sample_ids, entered_by, entered_by_name, entered_at
    FROM manual.sample_result
    ORDER BY batch_key, metric_code, culture_day, coalesce(sample_name, ''), entered_at DESC, result_id DESC
"""


def upgrade() -> None:
    op.execute("ALTER TABLE manual.sample_result ADD COLUMN sampled_at timestamptz")
    op.execute("ALTER TABLE manual.sample_result ADD COLUMN sample_name varchar(64)")
    op.execute("COMMENT ON COLUMN manual.sample_result.sampled_at IS '取样时刻（自动从仪器记录带出或手填）；历史补录为空'")
    op.execute("COMMENT ON COLUMN manual.sample_result.sample_name IS '标准样品名，如 0092-26001-A1-D05 / 一天多次取样带 -T1 尾缀'")
    op.execute(
        "CREATE INDEX ix_manual_sample_result_name ON manual.sample_result "
        "(batch_key, metric_code, culture_day, coalesce(sample_name, ''), entered_at DESC)"
    )
    op.execute("DROP VIEW IF EXISTS mart.fact_manual_latest")
    op.execute(_VIEW)
    op.execute(
        "COMMENT ON VIEW mart.fact_manual_latest IS "
        "'人工录入结果的最新值（每批次每指标每培养天每样品名一行）；看板生化曲线/数据表读这里'"
    )
    op.execute(f"GRANT SELECT ON mart.fact_manual_latest TO {_READERS}")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS mart.fact_manual_latest")
    op.execute("DROP INDEX IF EXISTS manual.ix_manual_sample_result_name")
    op.execute("ALTER TABLE manual.sample_result DROP COLUMN sample_name")
    op.execute("ALTER TABLE manual.sample_result DROP COLUMN sampled_at")
    op.execute(
        """
        CREATE VIEW mart.fact_manual_latest AS
        SELECT DISTINCT ON (batch_key, metric_code, culture_day)
            result_id, batch_key, culture_day, sample_date, metric_code, value, unit,
            note, source_sample_ids, entered_by, entered_by_name, entered_at
        FROM manual.sample_result
        ORDER BY batch_key, metric_code, culture_day, entered_at DESC, result_id DESC
        """
    )
    op.execute(f"GRANT SELECT ON mart.fact_manual_latest TO {_READERS}")
