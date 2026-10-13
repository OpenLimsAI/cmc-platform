"""允许物料批号在软删除后复用，保留历史记录和审计。

Revision ID: 0063_mm_batch_partial_unique
Revises: 0062_eqp_total_weight
Create Date: 2026-10-13 01:00:00.000000

负责人已确认方案 B：同物料下仅未删除批次批号唯一。
仅改变唯一性约束，不删除、合并或回填业务数据。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0063_mm_batch_partial_unique"
down_revision: str | None = "0062_eqp_total_weight"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_material_batch_active", "material_batch", ["material_id", "batch_number"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"), schema="mm",
    )
    op.drop_constraint("uq_material_batch", "material_batch", schema="mm", type_="unique")


def downgrade() -> None:
    # 保持约束直至检查结束；从不通过清理历史记录来强行降级。
    op.execute("LOCK TABLE mm.material_batch IN ACCESS EXCLUSIVE MODE")
    duplicate = op.get_bind().execute(sa.text(
        "SELECT 1 FROM mm.material_batch GROUP BY material_id, batch_number "
        "HAVING count(*) > 1 LIMIT 1"
    )).first()
    if duplicate is not None:
        raise RuntimeError("存在复用批号的历史记录，拒绝恢复全表唯一约束；须单独评估回退")
    op.create_unique_constraint(
        "uq_material_batch", "material_batch", ["material_id", "batch_number"], schema="mm",
    )
    op.drop_index("uq_material_batch_active", table_name="material_batch", schema="mm")
