"""cmc_analytics: 批号 PROJ 段放开——核心号正则 ^\\d{3}-\\d{5}$ → ^[A-Za-z0-9]+-\\d{5}$（2026-07-16）

PROJ（项目短码）原强制 3 位数字，现暂放开为「≥1 位、数字或英文字母、不含分隔符 -」，
以适配多位数字或含字母的项目号（如 12345 / CMAB007）。YYSEQ 及其后各段不变。

结构改动：仅重建 batch_register 的核心号 CHECK 约束 ck_batch_register_core_format。
  - 不动列/视图/计数器。
  - 兼容性：既有批号均为纯数字 ^\\d{3}-\\d{5}$，是新正则的子集，ADD CONSTRAINT 校验既有行不会失败。

权威：正则单一来源见 docs/种子链批号与样品命名规则.md §7 + backend naming.py，本迁移与之一致。

Revision ID: cmc_analytics_batch_proj_open
Revises: cmc_analytics_batch_audit_name
Create Date: 2026-07-16
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_proj_open"
down_revision = "cmc_analytics_batch_audit_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE batch.batch_register DROP CONSTRAINT IF EXISTS ck_batch_register_core_format"
    )
    op.execute(
        r"""
        ALTER TABLE batch.batch_register
          ADD CONSTRAINT ck_batch_register_core_format
          CHECK (business_batch_no ~ '^[A-Za-z0-9]+-[0-9]{5}$')
        """
    )


def downgrade() -> None:
    # 收回到「PROJ 仅 3 位数字」。注：若期间已发过含字母/非 3 位 PROJ 的批号，
    # 这些行不满足旧正则，ADD CONSTRAINT 会报错，需先人工处理再回滚。
    op.execute(
        "ALTER TABLE batch.batch_register DROP CONSTRAINT IF EXISTS ck_batch_register_core_format"
    )
    op.execute(
        r"""
        ALTER TABLE batch.batch_register
          ADD CONSTRAINT ck_batch_register_core_format
          CHECK (business_batch_no ~ '^[0-9]{3}-[0-9]{5}$')
        """
    )
