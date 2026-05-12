"""revert: status_change triggers no longer read app.e_signature_id

Revision ID: 0010_revert_signature_session_var
Revises: 0009_signature_session_var
Create Date: 2026-05-11 20:00:00.000000

回退 0009 的 SET LOCAL 方案。原因：

  asyncpg + AsyncSession 在快速连续请求 / 同连接复用场景下，SET LOCAL 的 GUC
  会偶发泄漏到下一事务（pytest 全集观察到 ~10% 失败率，表现为：第 2 条 status_history
  写入了第 1 条事务的 e_signature_id，触发 FK 看似正常但语义错乱；或者 commit 前
  因事务状态混乱被静默回滚导致 200 响应但 DB 无变更）。

  新方案：service 层在 substance/project 状态变更 flush 之后，显式
  UPDATE status_history SET e_signature_id = :sig_id WHERE history_id = (
    SELECT MAX(history_id) FROM ... WHERE entity_id = :id
  )

  触发器恢复 0008 时期的 v1 行为，只负责写入 status_history 主体字段，e_signature_id
  由 service 后置回填。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0010_revert_sig_sessionvar"
down_revision: str | None = "0009_signature_session_var"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
            NEW.substance_id, OLD.status, NEW.status,
            COALESCE(NULLIF(current_setting('app.change_reason', TRUE), ''), 'status changed'),
            NEW.updated_by, v_sig_id
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
            NEW.project_id, OLD.status, NEW.status,
            COALESCE(NULLIF(current_setting('app.change_reason', TRUE), ''), 'status changed'),
            NEW.updated_by, v_sig_id
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(_SRS_FN_V1)
    op.execute(_PRS_FN_V1)


def downgrade() -> None:
    op.execute(_PRS_FN_V2)
    op.execute(_SRS_FN_V2)
