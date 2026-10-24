"""cmc_analytics: 批号 CHECK 放行「历史实际批号」形态（补录历史批次改回真实批号用）

背景：系统上线前的历史批次先按系统规则发了号（如 807-26009），之后需在后台把它们改回
当时的实际批号（如 807-R2601 / 007-R2601-HCP / 0071-R2601）。这些实际批号不满足
系统核心号正则 ^[A-Za-z0-9]+-[0-9]{5}$，被 ck_batch_register_core_format 拒绝。

结构改动：仅重建该 CHECK，在原系统格式之外**额外**放行一种历史形态：
    ^[A-Za-z0-9]+-R[0-9]{4}(-[A-Za-z0-9]+)?$      例 807-R2601、007-R2601-HCP
  - 系统发号规则（naming.py / 速查 §7）不变，新批号仍只会是 PROJ-YYSEQ；
    本约束只是数据库兜底，放行历史号不影响发号。
  - 不动列/视图/计数器。既有行均满足原正则，ADD CONSTRAINT 不会失败。

Revision ID: cmc_analytics_batch_legacy_no
Revises: cmc_analytics_chdict_active
Create Date: 2026-08-19
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_legacy_no"
down_revision = "cmc_analytics_chdict_active"
branch_labels = None
depends_on = None

_SYS = r"^[A-Za-z0-9]+-[0-9]{5}$"
_LEGACY = r"^[A-Za-z0-9]+-R[0-9]{4}(-[A-Za-z0-9]+)?$"


def upgrade() -> None:
    op.execute("ALTER TABLE batch.batch_register DROP CONSTRAINT IF EXISTS ck_batch_register_core_format")
    op.execute(
        f"""
        ALTER TABLE batch.batch_register
          ADD CONSTRAINT ck_batch_register_core_format
          CHECK (business_batch_no ~ '{_SYS}' OR business_batch_no ~ '{_LEGACY}')
        """
    )


def downgrade() -> None:
    # 收回到仅系统格式。若已有行改成了历史实际批号，ADD CONSTRAINT 会报错，需先人工改回再回滚。
    op.execute("ALTER TABLE batch.batch_register DROP CONSTRAINT IF EXISTS ck_batch_register_core_format")
    op.execute(
        f"""
        ALTER TABLE batch.batch_register
          ADD CONSTRAINT ck_batch_register_core_format
          CHECK (business_batch_no ~ '{_SYS}')
        """
    )
