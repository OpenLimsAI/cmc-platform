"""cmc_rd: raw_rd_lims_samplemanager.sample 补 LIMS 侧 2026-08 新增的 CELLBANKNAME 列

Oracle LABLIMS.SAMPLE 在 2026-08-25 前后由 LIMS 侧加了 CELLBANKNAME（细胞库名称，
VARCHAR2(200)）。rd-lims-etl v0.4 是全字段保真抽取（SELECT *），源表多出的列在
UPSERT 时因 raw 表无对应列报 KeyError: 'cellbankname'，ETL 自 2026-08-25 16:00 起
每班次失败（有意设计：宁可停，不悄悄丢字段）。本迁移按「raw 全字段保真」原则
补齐该列（TEXT，与 raw 层其他 VARCHAR2 列的落地类型一致）。

与 rd-lims-etl 的 sql/01_cmc_rd_raw.sql（参考 DDL 同步补列）对齐。
处理方式同 2026-08-04 的 cmc_rd_lims_newcols（enz_act / trialsample）。

Revision ID: cmc_rd_lims_cellbank
Revises: cmc_rd_vicell_log_upd
Create Date: 2026-09-08
"""
from __future__ import annotations

from alembic import op


revision = "cmc_rd_lims_cellbank"
down_revision = "cmc_rd_vicell_log_upd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE raw_rd_lims_samplemanager.sample
            ADD COLUMN IF NOT EXISTS cellbankname TEXT
        """
    )
    op.execute(
        "COMMENT ON COLUMN raw_rd_lims_samplemanager.sample.cellbankname IS "
        "'细胞库名称（源 LABLIMS.SAMPLE.CELLBANKNAME，2026-08 LIMS 侧新增）'"
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE raw_rd_lims_samplemanager.sample
            DROP COLUMN IF EXISTS cellbankname
        """
    )
