"""substance_protein sequence_hash computed by DB trigger (§7.3)

Revision ID: 0021_protein_hash
Revises: 0020_srs_fks
Create Date: 2026-05-12 00:20:00.000000

M3.0.3 第 4 步：

  - 文档 §7.3 设计：sequence_hash_hc/lc + sequence_length_hc/lc 由 BEFORE INSERT/UPDATE 触发器
    `fn_substance_protein_compute_hash` 自动算（与 Python service 不一致风险消除）
  - service 层保留 Python 层 _hash_sequence 函数（同一性判定时仍需对入参算 hash 用于比对），
    但写入路径不再依赖（DB 触发器兜底）

  哈希算法：SHA-256 of UPPER(seq) 剔除非 A-Z 字符后的字符串
  长度：剔除非 A-Z 字符后的字符串长度

  与 0004 backfill_sequence_hash 的 PG 端 SHA-256 算法保持一致。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0021_protein_hash"
down_revision: str | None = "0020_srs_fks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION srs.fn_substance_protein_compute_hash()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.heavy_chain_sequence IS NOT NULL AND NEW.heavy_chain_sequence <> '' THEN
                NEW.sequence_hash_hc := encode(
                    digest(regexp_replace(UPPER(NEW.heavy_chain_sequence), '[^A-Z]', '', 'g'),
                           'sha256'),
                    'hex'
                );
                NEW.sequence_length_hc := length(
                    regexp_replace(UPPER(NEW.heavy_chain_sequence), '[^A-Z]', '', 'g')
                );
            ELSE
                NEW.sequence_hash_hc   := NULL;
                NEW.sequence_length_hc := NULL;
            END IF;
            IF NEW.light_chain_sequence IS NOT NULL AND NEW.light_chain_sequence <> '' THEN
                NEW.sequence_hash_lc := encode(
                    digest(regexp_replace(UPPER(NEW.light_chain_sequence), '[^A-Z]', '', 'g'),
                           'sha256'),
                    'hex'
                );
                NEW.sequence_length_lc := length(
                    regexp_replace(UPPER(NEW.light_chain_sequence), '[^A-Z]', '', 'g')
                );
            ELSE
                NEW.sequence_hash_lc   := NULL;
                NEW.sequence_length_lc := NULL;
            END IF;
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    # 已有 trg_substance_protein_touch 维护 updated_at；本 hash 触发器与之并存或替代。
    # 简化：用新触发器替代旧 touch（hash 触发器同时维护 updated_at）。
    op.execute("DROP TRIGGER IF EXISTS trg_substance_protein_touch ON srs.substance_protein")
    op.execute("""
        CREATE TRIGGER trg_substance_protein_compute_hash
        BEFORE INSERT OR UPDATE ON srs.substance_protein
        FOR EACH ROW EXECUTE FUNCTION srs.fn_substance_protein_compute_hash();
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_substance_protein_compute_hash ON srs.substance_protein"
    )
    op.execute("DROP FUNCTION IF EXISTS srs.fn_substance_protein_compute_hash()")
    # 恢复旧 touch 触发器（仅维护 updated_at）
    op.execute("""
        CREATE TRIGGER trg_substance_protein_touch
        BEFORE UPDATE ON srs.substance_protein
        FOR EACH ROW EXECUTE FUNCTION srs.fn_touch_updated_at();
    """)
