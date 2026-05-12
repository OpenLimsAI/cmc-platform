"""ref.project_asset per DM-MDM-001 V1.0 §11.4

Revision ID: 0026_ref_pa
Revises: 0025_ref_as
Create Date: 2026-05-12 01:10:00.000000

M3.3 第 2 步：建 ref.project_asset（项目-资产关系）。

§11.4 实际设计：
  - 复合 PK (project_id, asset_id) — relation_type 是属性不是 PK
    （一对 project↔asset 只能有一个 relation_type 关联，与 §11.2 复合三键不同）
  - relation_type 文档未限定 CHECK 枚举，但前端建议值 primary/supporting/derivative/...
  - 软删除 deleted_at

audit trigger 接入：parent_ref 回填 project_code（业务上项目是主体）。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_ref_pa"
down_revision: str | None = "0025_ref_as"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_asset",
        sa.Column("project_id", sa.BigInteger,
                  sa.ForeignKey("prs.project.project_id"), nullable=False),
        sa.Column("asset_id", sa.BigInteger,
                  sa.ForeignKey("ars.asset.asset_id"), nullable=False),
        sa.Column("relation_type", sa.String(32), nullable=False, server_default="primary"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("project_id", "asset_id", name="pk_ref_project_asset"),
        schema="ref",
    )
    op.create_index(
        "ix_ref_pa_project", "project_asset", ["project_id"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="ref",
    )
    op.create_index(
        "ix_ref_pa_asset", "project_asset", ["asset_id"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="ref",
    )

    # 接入审计：parent_ref 回填 project_code
    op.execute("""
        CREATE TRIGGER trg_ref_pa_audit
        AFTER INSERT OR UPDATE OR DELETE ON ref.project_asset
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'project_id', '', 'prs.project:project_id:project_code:project_id'
        );
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_ref_pa_audit ON ref.project_asset")
    op.drop_table("project_asset", schema="ref")
