"""eqp.equipment 新增「别名/曾用名」正式字段，并把已存在 extra 里的值搬过来

Revision ID: 0059_eqp_alias
Revises: 0058_revoke_legacy_tokens
Create Date: 2026-09-11 01:00:00.000000

负责人 2026-09-11：设备部台账有「别名/曾用名」一列（老员工习惯叫 BR1-1、发酵线1 这类旧称），
此前导入脚本把它塞进 extra 这个附加信息袋里，界面看不到、搜索也搜不到，等于没有。
拍板：给它一个正式字段，不再占用别的字段。

本迁移：
  1) 加列 alias VARCHAR(255)（正式库现有最长 44 字符，255 足够）
  2) 把 extra->>'别名' 搬进 alias，单元格折行（\n）连同两侧空格去掉
     —— 台账里是「Nutrient Tank 600/400;⏎NT1-3;⏎生物反应器系统1;⏎发酵线1」这种排版折行，
     多个别名之间本来就有 ; / ； 分隔，去掉折行后可读且不丢信息
  3) 从 extra 里删掉「别名」键，避免同一份数据两处存放、日后不一致

影响：正式库 63 台设备有别名值。extra 里其余键（历史编号/位置/级别/总重/出厂日期/证书编号/
设备IP/域名）本次不动，需要时再逐个转正。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0059_eqp_alias"
down_revision: str | None = "0058_revoke_legacy_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("equipment", sa.Column("alias", sa.String(255)), schema="eqp")
    op.execute("COMMENT ON COLUMN eqp.equipment.alias IS '别名/曾用名（多个用 ; 分隔，来自设备部台账）'")

    # 搬家：extra->>'别名' → alias（去掉单元格折行）
    op.execute(r"""
        UPDATE eqp.equipment
           SET alias = NULLIF(regexp_replace(extra->>'别名', '\s*\n\s*', '', 'g'), '')
         WHERE jsonb_typeof(extra) = 'object'
           AND extra ? '别名'
    """)
    # 搬完从 extra 删掉，避免两处存放
    op.execute("""
        UPDATE eqp.equipment
           SET extra = extra - '别名'
         WHERE jsonb_typeof(extra) = 'object'
           AND extra ? '别名'
    """)


def downgrade() -> None:
    # 回滚时把值搬回 extra，不丢数据
    op.execute("""
        UPDATE eqp.equipment
           SET extra = coalesce(extra, '{}'::jsonb) || jsonb_build_object('别名', alias)
         WHERE alias IS NOT NULL
    """)
    op.drop_column("equipment", "alias", schema="eqp")
