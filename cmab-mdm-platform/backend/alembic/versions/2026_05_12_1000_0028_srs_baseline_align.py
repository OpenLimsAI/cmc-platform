"""srs baseline align: external_uuid UNIQUE + missing indices + status reason de-GUC (§7)

Revision ID: 0028_srs_baseline_align
Revises: 0027_softdel_by
Create Date: 2026-05-12 10:00:00.000000

DM-MDM-001 V1.1 §7 独立复核发现的偏离回归（V1.2_draft §2 声称 100% 对齐，实际差 5 条）：

  S1. srs.substance.external_uuid 加 UNIQUE（§7.2.2 uq_substance_external_uuid）
  S2. srs.substance_protein 加 hash B-tree 索引 × 2（§7.3）
  S3. srs.substance_xref 加 ix_substance_xref_value（§7.6）
  S4. srs.substance 加 partial ix_substance_internal_code WHERE deleted_at IS NULL（§7.2.2）
  S8. srs.fn_substance_status_change 触发器去掉 current_setting('app.change_reason') GUC 读取，
      改为写入字面量 'status changed'（§7.7 V1.1 DDL/注释要求）；
      change_reason 实际值由 service 层在 flush 后 UPDATE 回填，与 e_signature_id 同模式
      （0010 已对 e_signature_id 应用此模式，本次扩展到 change_reason）

预检（2026-05-12 dev 库 4106 行 substance）：external_uuid 0 重复 0 NULL，UNIQUE 可安全加。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0028_srs_baseline_align"
down_revision: str | None = "0027_softdel_by"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_FN_STATUS_CHANGE_NO_GUC = """
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
            'status changed',
            NEW.updated_by
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_FN_STATUS_CHANGE_WITH_GUC = """
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


def upgrade() -> None:
    # S1. substance.external_uuid 加 UNIQUE
    op.create_unique_constraint(
        "uq_substance_external_uuid", "substance", ["external_uuid"],
        schema="srs",
    )

    # S2. substance_protein 加 hash 索引 × 2
    op.create_index(
        "ix_substance_protein_hc_hash", "substance_protein", ["sequence_hash_hc"],
        schema="srs",
    )
    op.create_index(
        "ix_substance_protein_lc_hash", "substance_protein", ["sequence_hash_lc"],
        schema="srs",
    )

    # S3. substance_xref 加 ix_substance_xref_value
    op.create_index(
        "ix_substance_xref_value", "substance_xref", ["xref_value"],
        schema="srs",
    )

    # S4. substance 加 partial ix_substance_internal_code WHERE deleted_at IS NULL
    op.create_index(
        "ix_substance_internal_code", "substance", ["internal_code"],
        postgresql_where="deleted_at IS NULL",
        schema="srs",
    )

    # S8. fn_substance_status_change 去 GUC
    op.execute(_FN_STATUS_CHANGE_NO_GUC)


def downgrade() -> None:
    op.execute(_FN_STATUS_CHANGE_WITH_GUC)
    op.drop_index("ix_substance_internal_code", "substance", schema="srs")
    op.drop_index("ix_substance_xref_value", "substance_xref", schema="srs")
    op.drop_index("ix_substance_protein_lc_hash", "substance_protein", schema="srs")
    op.drop_index("ix_substance_protein_hc_hash", "substance_protein", schema="srs")
    op.drop_constraint(
        "uq_substance_external_uuid", "substance",
        schema="srs", type_="unique",
    )
