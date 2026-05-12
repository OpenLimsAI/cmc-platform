"""prs.project schema realignment to DM-MDM-001 V1.0 §9.2

Revision ID: 0013_prs_proj_v2
Revises: 0012_ref_ps_v2
Create Date: 2026-05-11 23:00:00.000000

M3.0.2 第 1 步：prs.project 主表回归 §9.2 基准（详见 docs/...偏离说明 V1.1_draft.md §3）。

改动顺序（保证 alembic upgrade 在含 dev demo 数据时能跑通）：
  1. 临时去除现有 status / project_type CHECK 约束
  2. UPDATE 现有数据：状态值与类型枚举映射
       status: draft → proposed, planned → initiated
       project_type: discovery → preclinical, tech_transfer → other,
                     lifecycle → commercial（其他保留）
  3. 字段重命名：phase → project_phase, project_owner_id → project_manager_id
  4. 移除 approved_at / approved_by（同等信息由 project_status_history 推断）
  5. 移除 phase 的 CHECK 约束（§9.2 允许任意 VARCHAR(32)）
  6. 加新字段：parent_project_id / program_name / sponsor_id / department /
              budget_total / budget_currency / budget_actual / objective /
              scope / deliverables / success_criteria / priority / confidentiality
  7. 加 ck_project_dates CHECK
  8. 加新 status / project_type CHECK 约束（按 §9.2 枚举值）
  9. project_code 生成函数改为按年（PRJ-YYYY-XXXX）
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_prs_proj_v2"
down_revision: str | None = "0012_ref_ps_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== 1. 移除旧 CHECK 约束 ==============
    # 注意：SQLAlchemy naming convention 给约束加了 ck_<table>_ 前缀，所以 PG 实际名是
    # ck_project_ck_project_status 这种"双前缀"形式。drop 时用真实名。
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_ck_project_status")
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_ck_project_project_type")
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_ck_project_phase")
    # 兼容性：如果未来用 raw SQL 加的约束（无双前缀），也尝试 drop
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_status")
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_project_type")
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_phase")

    # ============== 2. 数据映射（dev demo 数据兼容；生产部署前需迁移演练）==============
    op.execute("""
        UPDATE prs.project SET status = 'proposed' WHERE status = 'draft';
        UPDATE prs.project SET status = 'initiated' WHERE status = 'planned';
    """)
    op.execute("""
        UPDATE prs.project SET project_type = 'preclinical' WHERE project_type = 'discovery';
        UPDATE prs.project SET project_type = 'other' WHERE project_type = 'tech_transfer';
        UPDATE prs.project SET project_type = 'commercial' WHERE project_type = 'lifecycle';
    """)

    # ============== 3. 字段重命名 ==============
    op.alter_column("project", "phase", new_column_name="project_phase", schema="prs")
    op.alter_column(
        "project", "project_owner_id", new_column_name="project_manager_id", schema="prs"
    )

    # ============== 4. 移除 approved_at / approved_by（§9.2 不含此字段）==============
    op.drop_column("project", "approved_at", schema="prs")
    op.drop_column("project", "approved_by", schema="prs")

    # 同步重建 project_owner 索引为 project_manager
    op.drop_index("ix_project_owner", table_name="project", schema="prs")
    op.create_index(
        "ix_project_manager", "project", ["project_manager_id"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="prs",
    )

    # ============== 5. 加新字段（§9.2 缺失项）==============
    op.add_column("project", sa.Column("parent_project_id", sa.BigInteger), schema="prs")
    op.add_column("project", sa.Column("program_name", sa.String(128)), schema="prs")
    op.add_column("project", sa.Column("sponsor_id", sa.BigInteger), schema="prs")
    op.add_column("project", sa.Column("department", sa.String(64)), schema="prs")
    op.add_column("project", sa.Column("budget_total", sa.Numeric(18, 2)), schema="prs")
    op.add_column(
        "project",
        sa.Column("budget_currency", sa.String(8), nullable=True, server_default="CNY"),
        schema="prs",
    )
    op.add_column("project", sa.Column("budget_actual", sa.Numeric(18, 2)), schema="prs")
    op.add_column("project", sa.Column("objective", sa.Text), schema="prs")
    op.add_column("project", sa.Column("scope", sa.Text), schema="prs")
    op.add_column("project", sa.Column("deliverables", sa.Text), schema="prs")
    op.add_column("project", sa.Column("success_criteria", sa.Text), schema="prs")
    op.add_column("project", sa.Column("priority", sa.String(16)), schema="prs")
    op.add_column(
        "project",
        sa.Column("confidentiality", sa.String(16), nullable=False, server_default="internal"),
        schema="prs",
    )

    # parent_project 索引 + FK
    op.create_index(
        "ix_project_parent", "project", ["parent_project_id"], schema="prs"
    )
    op.create_foreign_key(
        "fk_project_parent", "project", "project",
        ["parent_project_id"], ["project_id"],
        source_schema="prs", referent_schema="prs",
    )

    # sponsor FK
    op.create_foreign_key(
        "fk_project_sponsor", "project", "user",
        ["sponsor_id"], ["user_id"],
        source_schema="prs", referent_schema="auth",
    )

    # ============== 6. ck_project_dates ==============
    op.create_check_constraint(
        "ck_project_dates",
        "project",
        "planned_end_date IS NULL OR planned_start_date IS NULL "
        "OR planned_end_date >= planned_start_date",
        schema="prs",
    )

    # ============== 7. 加新 status / project_type CHECK ==============
    op.create_check_constraint(
        "ck_project_status",
        "project",
        "status IN ('proposed','initiated','active','on_hold','completed','terminated')",
        schema="prs",
    )
    op.create_check_constraint(
        "ck_project_type",
        "project",
        "project_type IN ('cmc','preclinical','clinical','regulatory',"
        "'commercial','platform','other')",
        schema="prs",
    )

    # ============== 8. 改默认 status 为 proposed ==============
    op.alter_column(
        "project", "status",
        server_default="proposed",
        schema="prs",
    )

    # ============== 9. project_code 改按年生成函数 ==============
    # §9.2 设计：PRJ-YYYY-XXXX；用 meta.fn_ensure_year_sequence 动态创建年度序列
    op.execute("""
        CREATE OR REPLACE FUNCTION meta.fn_ensure_year_sequence(
            p_kind VARCHAR, p_prefix VARCHAR, p_year INT, p_padding INT
        ) RETURNS VARCHAR AS $$
        DECLARE
            v_seq_name VARCHAR;
        BEGIN
            v_seq_name := p_kind || '_' || p_year::text;
            INSERT INTO meta.code_sequence (sequence_name, prefix, padding_length, description)
            VALUES (
                v_seq_name,
                p_prefix || p_year::text || '-',
                p_padding,
                'Year-scoped sequence for ' || p_kind || ' in ' || p_year::text
            )
            ON CONFLICT (sequence_name) DO NOTHING;
            RETURN v_seq_name;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION prs.fn_project_assign_code()
        RETURNS TRIGGER AS $$
        DECLARE
            v_year     INT;
            v_seq_name VARCHAR;
        BEGIN
            IF NEW.project_code IS NULL OR NEW.project_code = '' THEN
                v_year := EXTRACT(YEAR FROM NOW())::INT;
                v_seq_name := meta.fn_ensure_year_sequence('project', 'PRJ-', v_year, 4);
                NEW.project_code := meta.fn_next_code(v_seq_name);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    # 老的全局 'project' 序列保留（已有 PRJ-XXXXXXX 编码不回填）；新创建走年度序列。


def downgrade() -> None:
    # 回退到 0012 时期的 prs.project 结构。dev 环境紧急回滚使用，生产慎用。
    op.execute("""
        CREATE OR REPLACE FUNCTION prs.fn_project_assign_code()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.project_code IS NULL OR NEW.project_code = '' THEN
                NEW.project_code := meta.fn_next_code('project');
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("DROP FUNCTION IF EXISTS meta.fn_ensure_year_sequence(VARCHAR, VARCHAR, INT, INT)")

    op.alter_column("project", "status", server_default="draft", schema="prs")
    op.drop_constraint("ck_project_type", "project", schema="prs", type_="check")
    op.drop_constraint("ck_project_status", "project", schema="prs", type_="check")
    op.drop_constraint("ck_project_dates", "project", schema="prs", type_="check")

    op.drop_constraint("fk_project_sponsor", "project", schema="prs", type_="foreignkey")
    op.drop_constraint("fk_project_parent", "project", schema="prs", type_="foreignkey")
    op.drop_index("ix_project_parent", table_name="project", schema="prs")

    for col in [
        "confidentiality", "priority", "success_criteria", "deliverables", "scope",
        "objective", "budget_actual", "budget_currency", "budget_total", "department",
        "sponsor_id", "program_name", "parent_project_id",
    ]:
        op.drop_column("project", col, schema="prs")

    op.create_index(
        "ix_project_owner", "project", ["project_manager_id"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="prs",
    )
    op.drop_index("ix_project_manager", table_name="project", schema="prs")

    op.add_column("project", sa.Column("approved_by", sa.BigInteger), schema="prs")
    op.add_column("project", sa.Column("approved_at", sa.DateTime(timezone=True)), schema="prs")
    op.alter_column(
        "project", "project_manager_id", new_column_name="project_owner_id", schema="prs"
    )
    op.alter_column("project", "project_phase", new_column_name="phase", schema="prs")

    op.execute("""
        UPDATE prs.project SET status = 'planned' WHERE status = 'initiated';
        UPDATE prs.project SET status = 'draft' WHERE status = 'proposed';
    """)
    op.create_check_constraint(
        "ck_project_status",
        "project",
        "status IN ('draft','planned','active','on_hold','completed','terminated')",
        schema="prs",
    )
    op.create_check_constraint(
        "ck_project_project_type",
        "project",
        "project_type IN ('discovery','preclinical','clinical','cmc',"
        "'tech_transfer','lifecycle','other')",
        schema="prs",
    )
    op.create_check_constraint(
        "ck_project_phase",
        "project",
        "phase IS NULL OR phase IN ('discovery','preclinical','phase_1','phase_2','phase_3',"
        "'submission','approved','marketed','discontinued','na')",
        schema="prs",
    )
