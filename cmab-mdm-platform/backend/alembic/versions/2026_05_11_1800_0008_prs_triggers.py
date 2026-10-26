"""prs / ref triggers: before_update / assign_code / status_history + audit hooks

Revision ID: 0008_prs_triggers
Revises: 0007_ref_init
Create Date: 2026-05-11 18:00:00.000000

把 PRS 4 张表和 ref.project_substance 接入 M2.0 v2 审计底座：
  - prs.fn_project_before_update：updated_at + version+1（与 srs.fn_substance_before_update 同构）
  - prs.fn_project_assign_code：BEFORE INSERT 自动分配 PRJ-XXXXXXX
  - prs.fn_touch_updated_at + 子表 BEFORE UPDATE 触发器
  - prs.fn_project_status_change：AFTER UPDATE 写 project_status_history（M2.2 状态机端点上线即生效）
  - audit.fn_audit_trigger 挂到 prs 4 张表 + ref.project_substance
    （子表/ref 表用 v2 的第 3 参数 parent_ref 让 entity_code 回填 project_code）
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0008_prs_triggers"
down_revision: str | None = "0007_ref_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== 通用 updated_at 触发器 ==============
    op.execute("""
        CREATE OR REPLACE FUNCTION prs.fn_touch_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # ============== project BEFORE UPDATE：updated_at + version+1 ==============
    op.execute("""
        CREATE OR REPLACE FUNCTION prs.fn_project_before_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at := NOW();
            NEW.version    := OLD.version + 1;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_project_before_update
        BEFORE UPDATE ON prs.project
        FOR EACH ROW EXECUTE FUNCTION prs.fn_project_before_update();
    """)

    # ============== project BEFORE INSERT：自动分配 PRJ-XXXXXXX（兜底）==============
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
    op.execute("""
        CREATE TRIGGER trg_project_assign_code
        BEFORE INSERT ON prs.project
        FOR EACH ROW EXECUTE FUNCTION prs.fn_project_assign_code();
    """)

    # ============== project_milestone / project_team BEFORE UPDATE ==============
    op.execute("""
        CREATE TRIGGER trg_project_milestone_touch
        BEFORE UPDATE ON prs.project_milestone
        FOR EACH ROW EXECUTE FUNCTION prs.fn_touch_updated_at();
    """)
    op.execute("""
        CREATE TRIGGER trg_project_team_touch
        BEFORE UPDATE ON prs.project_team
        FOR EACH ROW EXECUTE FUNCTION prs.fn_touch_updated_at();
    """)

    # ============== project 状态变更自动写历史 ==============
    op.execute("""
        CREATE OR REPLACE FUNCTION prs.fn_project_status_change()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status IS DISTINCT FROM NEW.status THEN
                INSERT INTO prs.project_status_history (
                    project_id, old_status, new_status, change_reason, changed_by
                ) VALUES (
                    NEW.project_id,
                    OLD.status,
                    NEW.status,
                    COALESCE(NULLIF(current_setting('app.change_reason', TRUE), ''), 'status changed'),
                    NEW.updated_by
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_project_status_change
        AFTER UPDATE ON prs.project
        FOR EACH ROW EXECUTE FUNCTION prs.fn_project_status_change();
    """)

    # ============== 接入审计（v2，子表 / ref 表传 parent_ref）==============
    op.execute("""
        CREATE TRIGGER trg_project_audit
        AFTER INSERT OR UPDATE OR DELETE ON prs.project
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('project_id', 'project_code');
    """)
    op.execute("""
        CREATE TRIGGER trg_project_milestone_audit
        AFTER INSERT OR UPDATE OR DELETE ON prs.project_milestone
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'milestone_id', '', 'prs.project:project_id:project_code:project_id'
        );
    """)
    op.execute("""
        CREATE TRIGGER trg_project_team_audit
        AFTER INSERT OR UPDATE OR DELETE ON prs.project_team
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'team_id', '', 'prs.project:project_id:project_code:project_id'
        );
    """)
    op.execute("""
        CREATE TRIGGER trg_ref_project_substance_audit
        AFTER INSERT OR UPDATE OR DELETE ON ref.project_substance
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'link_id', '', 'prs.project:project_id:project_code:project_id'
        );
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_ref_project_substance_audit ON ref.project_substance")
    op.execute("DROP TRIGGER IF EXISTS trg_project_team_audit ON prs.project_team")
    op.execute("DROP TRIGGER IF EXISTS trg_project_milestone_audit ON prs.project_milestone")
    op.execute("DROP TRIGGER IF EXISTS trg_project_audit ON prs.project")
    op.execute("DROP TRIGGER IF EXISTS trg_project_status_change ON prs.project")
    op.execute("DROP FUNCTION IF EXISTS prs.fn_project_status_change()")
    op.execute("DROP TRIGGER IF EXISTS trg_project_team_touch ON prs.project_team")
    op.execute("DROP TRIGGER IF EXISTS trg_project_milestone_touch ON prs.project_milestone")
    op.execute("DROP TRIGGER IF EXISTS trg_project_assign_code ON prs.project")
    op.execute("DROP FUNCTION IF EXISTS prs.fn_project_assign_code()")
    op.execute("DROP TRIGGER IF EXISTS trg_project_before_update ON prs.project")
    op.execute("DROP FUNCTION IF EXISTS prs.fn_project_before_update()")
    op.execute("DROP FUNCTION IF EXISTS prs.fn_touch_updated_at()")
