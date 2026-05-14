"""extinction_coefficient INT → double precision

Revision ID: 0035_protein_ext_coef_float
Revises: 0034_auth_refresh_token
Create Date: 2026-05-13 07:00:00.000000

V1.2 评审 S7 决议（修订十一吸收）：
  V1.1 §7.3 字面 `extinction_coefficient INT`，实施使用整数类型；但业务侧反映
  消光系数实验测定值常带 1-2 位小数（例：218400.5 M⁻¹cm⁻¹），整数限制导致
  POST/PUT 422。决议：永久接受 Float，与 S5/S6（molecular_weight_da /
  pi_theoretical）走同一路线。

  IEEE 754 双精度（约 15-17 位十进制精度）足够覆盖典型抗体消光系数范围
  （200,000-220,000 M⁻¹cm⁻¹）并保留实验测定误差所需精度。

数据完整性：ALTER COLUMN ... TYPE ... USING column::double precision 把已有整数
值无损转换；不破坏既有数据。

合规理由：21 CFR Part 11 §11.10 数据准确性针对**测量精度**而非**存储类型**；
audit.change_history 记录任何精度变化（虽然本次 schema 变更不写业务审计）。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0035_protein_ext_coef_float"
down_revision: str | None = "0034_auth_refresh_token"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE srs.substance_protein
            ALTER COLUMN extinction_coefficient
            TYPE double precision
            USING extinction_coefficient::double precision
        """
    )


def downgrade() -> None:
    # 注意：integer 不能容纳带小数的现有值；如果有非整数行，下面的转换会截断
    op.execute(
        """
        ALTER TABLE srs.substance_protein
            ALTER COLUMN extinction_coefficient
            TYPE integer
            USING extinction_coefficient::integer
        """
    )
