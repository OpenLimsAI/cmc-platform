"""cmc_rd: raw_rd_usp_lucullus + meta 的 timestamp 列改 TIMESTAMPTZ(UTC)

白皮书 §2.5 要求时间戳统一用 TIMESTAMPTZ(UTC)。baseline 里 41 个列是
`timestamp without time zone`（naive，存的是工作站本地墙上时间，中国 UTC+8）。
本迁移把这两个 schema 下所有 naive timestamp 列改成 timestamptz，并按
'Asia/Shanghai' 解释存量数据 -> 转成正确的 UTC 绝对时刻。

与 rd-lucullus-etl 的 schema.sql / ETL 代码（方案 B：全程 tz-aware，写入即 UTC）对齐。

Revision ID: cmc_rd_tstz
Revises: cmc_rd_wm_align
Create Date: 2026-07-01
"""
from __future__ import annotations

from alembic import op


revision = "cmc_rd_tstz"
down_revision = "cmc_rd_wm_align"
branch_labels = None
depends_on = None

SCHEMAS = ("raw_rd_usp_lucullus", "meta")
SOURCE_TZ = "Asia/Shanghai"  # 工作站本地时区（现代日期等价于固定 UTC+8）


def _convert(from_type: str, target_type: str) -> None:
    """把 SCHEMAS 下所有 from_type 列动态 ALTER 成 target_type，
    并用 AT TIME ZONE 'Asia/Shanghai' 在 naive 与 timestamptz 之间换算。
    列名用 %I、时区用 %L 经 PG format() 安全转义。"""
    schemas_sql = ", ".join("'%s'" % s for s in SCHEMAS)
    op.execute(
        f"""
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN
                SELECT table_schema, table_name, column_name
                FROM information_schema.columns
                WHERE table_schema IN ({schemas_sql})
                  AND data_type = '{from_type}'
            LOOP
                EXECUTE format(
                    'ALTER TABLE %I.%I ALTER COLUMN %I TYPE {target_type} USING %I AT TIME ZONE %L',
                    r.table_schema, r.table_name, r.column_name, r.column_name, '{SOURCE_TZ}'
                );
            END LOOP;
        END $$;
        """
    )


def upgrade() -> None:
    # naive 本地时间 -> 按 Asia/Shanghai 解释为 timestamptz(UTC)
    _convert("timestamp without time zone", "timestamptz")


def downgrade() -> None:
    # timestamptz -> 取回 Asia/Shanghai 墙上时间，回到 naive
    _convert("timestamp with time zone", "timestamp")
