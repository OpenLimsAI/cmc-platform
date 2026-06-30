"""align meta.etl_watermark with lucullus ETL（多实例水位）

把 cmc_rd baseline 里早期的 2 列水位设计
    PK (job_name, source_table) + (watermark_col, last_watermark)
对齐到 rd-lucullus-etl 实际读写的多实例设计
    PK (job_name, source_system, source_instance, target_table) + last_success_ts

原 (job_name, source_table) 无法区分多台工作站(ws01/ws02)跑同一 job，
ETL 代码（SQL_GET_WATERMARK / SQL_UPSERT_WATERMARK）按新列写水位，
旧结构会因列不存在而报错。本迁移消除该 schema drift。

Revision ID: cmc_rd_wm_align
Revises: cmc_rd_baseline
Create Date: 2026-06-30
"""
from __future__ import annotations

from alembic import op


revision = "cmc_rd_wm_align"
down_revision = "cmc_rd_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) 新增目标列。source_system / target_table 暂挂 server_default '' 以便
    #    给历史行回填后再去掉默认值（与 ETL schema 保持一致：二者无默认值）。
    op.execute(
        """
        ALTER TABLE meta.etl_watermark
            ADD COLUMN source_system   TEXT NOT NULL DEFAULT '',
            ADD COLUMN source_instance TEXT NOT NULL DEFAULT '',
            ADD COLUMN target_table    TEXT NOT NULL DEFAULT '',
            ADD COLUMN last_success_ts TIMESTAMP
        """
    )

    # 2) 回填历史数据：旧 source_table≈新 target_table，旧 last_watermark≈新 last_success_ts。
    #    旧设计无 source_system，留空字符串（与新 PK 的 NOT NULL 兼容）。
    op.execute(
        """
        UPDATE meta.etl_watermark
        SET target_table    = source_table,
            last_success_ts = last_watermark
        """
    )

    # 3) 切换主键：先去旧 PK，再去旧列，最后建新 PK。
    op.execute("ALTER TABLE meta.etl_watermark DROP CONSTRAINT etl_watermark_pkey")
    op.execute(
        """
        ALTER TABLE meta.etl_watermark
            DROP COLUMN source_table,
            DROP COLUMN watermark_col,
            DROP COLUMN last_watermark
        """
    )
    # source_instance 保留 DEFAULT ''（纯字典表用 '' 占位，避免 NULL 进 PK）；
    # source_system / target_table 去掉临时默认值，与 ETL schema 完全一致。
    op.execute(
        """
        ALTER TABLE meta.etl_watermark
            ALTER COLUMN source_system DROP DEFAULT,
            ALTER COLUMN target_table  DROP DEFAULT
        """
    )
    op.execute(
        """
        ALTER TABLE meta.etl_watermark
            ADD CONSTRAINT etl_watermark_pkey
            PRIMARY KEY (job_name, source_system, source_instance, target_table)
        """
    )

    op.execute(
        "COMMENT ON TABLE meta.etl_watermark IS "
        "'每个 (job, 源系统, 源实例, 目标表) 的增量水位。仅存上次成功同步到的时间点，运行明细见 etl_run。'"
    )


def downgrade() -> None:
    # 回退到 baseline 的 2 列设计。
    op.execute(
        """
        ALTER TABLE meta.etl_watermark
            ADD COLUMN source_table   TEXT NOT NULL DEFAULT '',
            ADD COLUMN watermark_col  TEXT NOT NULL DEFAULT '',
            ADD COLUMN last_watermark TIMESTAMP
        """
    )
    op.execute(
        """
        UPDATE meta.etl_watermark
        SET source_table   = target_table,
            last_watermark = last_success_ts
        """
    )
    op.execute("ALTER TABLE meta.etl_watermark DROP CONSTRAINT etl_watermark_pkey")
    op.execute(
        """
        ALTER TABLE meta.etl_watermark
            DROP COLUMN source_system,
            DROP COLUMN source_instance,
            DROP COLUMN target_table,
            DROP COLUMN last_success_ts
        """
    )
    op.execute(
        """
        ALTER TABLE meta.etl_watermark
            ALTER COLUMN source_table  DROP DEFAULT,
            ALTER COLUMN watermark_col DROP DEFAULT
        """
    )
    op.execute(
        """
        ALTER TABLE meta.etl_watermark
            ADD CONSTRAINT etl_watermark_pkey PRIMARY KEY (job_name, source_table)
        """
    )
