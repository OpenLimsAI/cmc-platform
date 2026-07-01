"""cmc_rd: raw_rd_usp_lucullus.process_src.timeunit 从 BIGINT 改为 TEXT

baseline 把 process_src.timeunit 建成了 BIGINT，但 Lucullus 源表
lucullus.s_proctab.TIMEUNIT 实际是 VARCHAR2（取值如 'h' 表示小时）。
参考表全量同步时往 BIGINT 列写 'h' 会报 invalid input syntax for type bigint。
本迁移把该列改成 TEXT。

与 rd-lucullus-etl 的 schema.sql（同步改为 TEXT）对齐。

Revision ID: cmc_rd_timeunit_txt
Revises: cmc_rd_tstz
Create Date: 2026-07-01
"""
from __future__ import annotations

from alembic import op


revision = "cmc_rd_timeunit_txt"
down_revision = "cmc_rd_tstz"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE raw_rd_usp_lucullus.process_src "
        "ALTER COLUMN timeunit TYPE TEXT USING timeunit::text"
    )


def downgrade() -> None:
    # 注意：若列内已有非数字文本（如 'h'），回退到 BIGINT 会失败——这是预期的，
    # 因为文本单位码本就无法塞进 BIGINT。
    op.execute(
        "ALTER TABLE raw_rd_usp_lucullus.process_src "
        "ALTER COLUMN timeunit TYPE BIGINT USING timeunit::bigint"
    )
