"""status_change triggers read app.e_signature_id session var

Revision ID: 0009_signature_session_var
Revises: 0008_prs_triggers
Create Date: 2026-05-11 19:00:00.000000

M2.5.1 电子签名底座：
  - 修改 srs.fn_substance_status_change：读 app.e_signature_id PG session var，
    写入 substance_status_history.e_signature_id
  - 修改 prs.fn_project_status_change：同上，写入 project_status_history.e_signature_id

业务流程（service 层）：
  1. ESignatureService.sign() 验证密码 → INSERT e_signature → SET LOCAL app.e_signature_id
  2. service 执行状态变更（UPDATE substance.status / project.status）
  3. AFTER UPDATE 触发器读 session var，把签名 id 关联到 status_history

未提供签名时（CRUD 或非 GxP 关键动作），session var 为空，e_signature_id 写 NULL，
现有 status_history 行为不变。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0009_signature_session_var"
down_revision: str | None = "0008_prs_triggers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SRS_FN_V2 = """
CREATE OR REPLACE FUNCTION srs.fn_substance_status_change()
RETURNS TRIGGER AS $$
DECLARE
    v_sig_id BIGINT;
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        v_sig_id := NULLIF(current_setting('app.e_signature_id', TRUE), '')::BIGINT;
        INSERT INTO srs.substance_status_history (
            substance_id, old_status, new_status, change_reason, changed_by, e_signature_id
        ) VALUES (
            NEW.substance_id,
            OLD.status,
            NEW.status,
            COALESCE(NULLIF(current_setting('app.change_reason', TRUE), ''), 'status changed'),
            NEW.updated_by,
            v_sig_id
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_SRS_FN_V1 = """
CREATE OR REPLACE FUNCTION srs.fn_substance_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO srs.substance_status_history (
            substance_id, old_status, new_status, change_reason, changed_by
        ) VALUES (
            NEW.substance_id,
            OLD.status,
            NEW.status,
            COALESCE(NULLIF(current_setting('app.change_reason', TRUE), ''), 'status changed'),
            NEW.updated_by
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_PRS_FN_V2 = """
CREATE OR REPLACE FUNCTION prs.fn_project_status_change()
RETURNS TRIGGER AS $$
DECLARE
    v_sig_id BIGINT;
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        v_sig_id := NULLIF(current_setting('app.e_signature_id', TRUE), '')::BIGINT;
        INSERT INTO prs.project_status_history (
            project_id, old_status, new_status, change_reason, changed_by, e_signature_id
        ) VALUES (
            NEW.project_id,
            OLD.status,
            NEW.status,
            COALESCE(NULLIF(current_setting('app.change_reason', TRUE), ''), 'status changed'),
            NEW.updated_by,
            v_sig_id
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_PRS_FN_V1 = """
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
"""


def upgrade() -> None:
    op.execute(_SRS_FN_V2)
    op.execute(_PRS_FN_V2)


def downgrade() -> None:
    op.execute(_PRS_FN_V1)
    op.execute(_SRS_FN_V1)
