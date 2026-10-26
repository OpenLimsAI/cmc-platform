"""ref.project_substance schema realignment to DM-MDM-001 V1.0 §11.2

Revision ID: 0012_ref_ps_v2
Revises: 0011_auth_locked_at
Create Date: 2026-05-11 22:00:00.000000

M3.0.1 设计基准回归（详见 docs/CMAB_MDM_Portal_设计基准偏离说明_V1.1_draft.md §4.1）：

Phase 2.3 实施的 ref.project_substance 与 §11.2 偏离严重：
  - 主键：自增 link_id  →  复合 (project_id, substance_id, relation_type)
  - 字段名：role         →  relation_type
  - 枚举：primary_target/candidate/backup/excluded/reference
        →  primary/secondary/reference/control/derivative
  - 额外字段：priority INT  →  is_primary BOOLEAN
  - 软删除：unlinked_at/by  →  deleted_at/by（语义 = 取消引用）
  - audit trigger 第 1 参数：'link_id'  →  'project_id'

破坏性迁移：DROP + CREATE。dev 环境 demo 数据由 seed_data --demo 重建。
生产部署前需走数据迁移演练，本迁移不含数据 backfill。

保留实施侧加强（§5.3）：audit trigger 第 3 参数 parent_ref，让 entity_code
自动回填父 project_code，便于按业务编码查审计历史。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_ref_ps_v2"
down_revision: str | None = "0011_auth_locked_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 删除旧表（含触发器、索引、外键）
    op.execute("DROP TABLE IF EXISTS ref.project_substance CASCADE")

    # 按 §11.2 重建
    op.create_table(
        "project_substance",
        sa.Column("project_id", sa.BigInteger,
                  sa.ForeignKey("prs.project.project_id"), nullable=False),
        sa.Column("substance_id", sa.BigInteger,
                  sa.ForeignKey("srs.substance.substance_id"), nullable=False),
        sa.Column("relation_type", sa.String(32), nullable=False, server_default="primary"),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.BigInteger),
        sa.PrimaryKeyConstraint("project_id", "substance_id", "relation_type",
                                 name="pk_ref_project_substance"),
        sa.CheckConstraint(
            "relation_type IN ('primary','secondary','reference','control','derivative')",
            name="ck_ref_ps_type",
        ),
        schema="ref",
    )
    op.create_index(
        "ix_ref_ps_project", "project_substance", ["project_id"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="ref",
    )
    op.create_index(
        "ix_ref_ps_substance", "project_substance", ["substance_id"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="ref",
    )

    # 接入审计：trigger 第 1 参数按文档 §11.2 用 project_id；
    # 第 3 参数 parent_ref 是实施侧加强（V1.1 候选），让 entity_code 自动回填 project_code
    op.execute("""
        CREATE TRIGGER trg_ref_ps_audit
        AFTER INSERT OR UPDATE OR DELETE ON ref.project_substance
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'project_id', '', 'prs.project:project_id:project_code:project_id'
        );
    """)


def downgrade() -> None:
    """回退到 Phase 2.3 自增 link_id 结构。仅供紧急回滚，dev 环境不应常用。"""
    op.execute("DROP TABLE IF EXISTS ref.project_substance CASCADE")

    op.create_table(
        "project_substance",
        sa.Column("link_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("project_id", sa.BigInteger,
                  sa.ForeignKey("prs.project.project_id"), nullable=False),
        sa.Column("substance_id", sa.BigInteger,
                  sa.ForeignKey("srs.substance.substance_id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("priority", sa.Integer),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("linked_by", sa.BigInteger,
                  sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("unlinked_at", sa.DateTime(timezone=True)),
        sa.Column("unlinked_by", sa.BigInteger,
                  sa.ForeignKey("auth.user.user_id")),
        sa.Column("notes", sa.Text),
        sa.CheckConstraint(
            "role IN ('primary_target','candidate','backup','excluded','reference')",
            name="ck_project_substance_role",
        ),
        sa.CheckConstraint(
            "(unlinked_at IS NULL AND unlinked_by IS NULL) "
            "OR (unlinked_at IS NOT NULL AND unlinked_by IS NOT NULL)",
            name="ck_project_substance_unlink_consistency",
        ),
        schema="ref",
    )
    op.create_index("ix_project_substance_project", "project_substance",
                    ["project_id"], schema="ref")
    op.create_index("ix_project_substance_substance", "project_substance",
                    ["substance_id"], schema="ref")
    op.execute("""
        CREATE UNIQUE INDEX uq_project_substance_active
        ON ref.project_substance (project_id, substance_id, role)
        WHERE unlinked_at IS NULL
    """)
    op.execute("""
        CREATE TRIGGER trg_ref_project_substance_audit
        AFTER INSERT OR UPDATE OR DELETE ON ref.project_substance
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'link_id', '', 'prs.project:project_id:project_code:project_id'
        );
    """)
