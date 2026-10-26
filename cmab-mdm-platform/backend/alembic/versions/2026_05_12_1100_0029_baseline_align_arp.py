"""baseline align ARS/PRS/REF: ref.ps deleted_by FK + status_change de-GUC + prs index rename

Revision ID: 0029_baseline_align_arp
Revises: 0028_srs_baseline_align
Create Date: 2026-05-12 11:00:00.000000

§8 ARS / §9 PRS / §11 REF 独立复核发现的偏离回归（V1.2_draft §6/§3/§4 自我声明 100%
对齐，实际差 22 项）。本次走 Batch D（DB 基线回归）+ Batch E（service 层合规校验）：

  R1. ref.project_substance 补 fk_ref_ps_deleted_by FK
      - migration 0012 加了 deleted_by 列但漏加 FK
      - migration 0027 给 ref.asset_substance / ref.project_asset 补了，但漏补 ps 表
      - 与 V1.1 §11.2 行 1667 显式要求冲突

  A3. ars.fn_asset_status_change 去 GUC 读取，写字面量 'status changed'
      - 与 V1.1 §8.4 注释一致；change_reason 由 service 后置 UPDATE 回填
      - 沿用 SRS migration 0028 / S8 同模式

  P1. prs.fn_project_status_change 同 A3 同款
      - 与 V1.1 §9.5 注释一致

  P2. prs.project 索引命名 + 补 ix_project_dates 复合索引
      - V1.1 §9.2 行 1426-1431 命名：ix_project_type / ix_project_pm / ix_project_name
      - migration 0006 实际：ix_project_project_type / ix_project_manager / ix_project_project_name
      - 完全缺失：ix_project_dates (planned_start_date, planned_end_date)
      - ix_project_phase 是实施侧加强，保留不动

预检（2026-05-12 dev 库）：ref.project_substance.deleted_by 0 孤儿可加 FK。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0029_baseline_align_arp"
down_revision: str | None = "0028_srs_baseline_align"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ARS_FN_NO_GUC = """
CREATE OR REPLACE FUNCTION ars.fn_asset_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO ars.asset_status_history (
            asset_id, old_status, new_status, change_reason, changed_by
        ) VALUES (
            NEW.asset_id,
            OLD.status,
            NEW.status,
            'status changed',
            NEW.updated_by
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_ARS_FN_WITH_GUC = """
CREATE OR REPLACE FUNCTION ars.fn_asset_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO ars.asset_status_history (
            asset_id, old_status, new_status, change_reason, changed_by
        ) VALUES (
            NEW.asset_id,
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

_PRS_FN_NO_GUC = """
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
            'status changed',
            NEW.updated_by
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_PRS_FN_WITH_GUC = """
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
    # R1. ref.project_substance 补 fk_ref_ps_deleted_by
    op.create_foreign_key(
        "fk_ref_ps_deleted_by",
        "project_substance", "user",
        ["deleted_by"], ["user_id"],
        source_schema="ref", referent_schema="auth",
    )

    # A3 + P1. status_change 触发器去 GUC
    op.execute(_ARS_FN_NO_GUC)
    op.execute(_PRS_FN_NO_GUC)

    # P2. prs.project 索引命名回归 + 补 ix_project_dates
    op.execute("ALTER INDEX prs.ix_project_project_type RENAME TO ix_project_type")
    op.execute("ALTER INDEX prs.ix_project_manager      RENAME TO ix_project_pm")
    op.execute("ALTER INDEX prs.ix_project_project_name RENAME TO ix_project_name")
    op.execute(
        "CREATE INDEX ix_project_dates "
        "ON prs.project(planned_start_date, planned_end_date)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS prs.ix_project_dates")
    op.execute("ALTER INDEX prs.ix_project_name RENAME TO ix_project_project_name")
    op.execute("ALTER INDEX prs.ix_project_pm   RENAME TO ix_project_manager")
    op.execute("ALTER INDEX prs.ix_project_type RENAME TO ix_project_project_type")

    op.execute(_PRS_FN_WITH_GUC)
    op.execute(_ARS_FN_WITH_GUC)

    op.drop_constraint(
        "fk_ref_ps_deleted_by", "project_substance",
        schema="ref", type_="foreignkey",
    )
