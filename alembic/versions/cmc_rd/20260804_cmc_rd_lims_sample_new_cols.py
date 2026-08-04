"""cmc_rd: raw_rd_lims_samplemanager.sample 补 LIMS 侧 2026-07 新增的 2 列

Oracle LABLIMS.SAMPLE 在 2026-07 由 LIMS 侧加了 ENZ_ACT（酶活，VARCHAR2(32)）
和 TRIALSAMPLE（试制样标记 T/F，VARCHAR2(10)）两列。rd-lims-etl v0.4 是
全字段保真抽取（SELECT *），源表多出的列在 UPSERT 时因 raw 表无对应列报
KeyError: 'trialsample'。本迁移按「raw 全字段保真」原则补齐这两列（TEXT，
与 raw 层其他 VARCHAR2 列的落地类型一致）。

与 rd-lims-etl 的 sql/01_cmc_rd_raw.sql（参考 DDL 同步补列）对齐。

Revision ID: cmc_rd_lims_newcols
Revises: cmc_rd_nova_grant
Create Date: 2026-08-04
"""
from __future__ import annotations

from alembic import op


revision = "cmc_rd_lims_newcols"
down_revision = "cmc_rd_nova_grant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE raw_rd_lims_samplemanager.sample
            ADD COLUMN IF NOT EXISTS enz_act     TEXT,
            ADD COLUMN IF NOT EXISTS trialsample TEXT
        """
    )
    op.execute(
        "COMMENT ON COLUMN raw_rd_lims_samplemanager.sample.enz_act IS "
        "'酶活（源 LABLIMS.SAMPLE.ENZ_ACT，2026-07 LIMS 侧新增）'"
    )
    op.execute(
        "COMMENT ON COLUMN raw_rd_lims_samplemanager.sample.trialsample IS "
        "'试制样标记 T/F（源 LABLIMS.SAMPLE.TRIALSAMPLE，2026-07 LIMS 侧新增）'"
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE raw_rd_lims_samplemanager.sample
            DROP COLUMN IF EXISTS enz_act,
            DROP COLUMN IF EXISTS trialsample
        """
    )
