"""backfill missing sequence_hash_hc/lc

Revision ID: 0004_backfill_sequence_hash
Revises: 0003_srs_triggers
Create Date: 2026-05-11 15:00:00.000000

Phase 1 早期种子 / 通过低版本 service 创建的 substance_protein 行可能没有 hash 字段，
导致同一性判定（check-sameness）无法基于序列匹配。本次迁移用 PG 端 SHA-256（pgcrypto）
回填，逻辑与 Python 端 _hash_sequence 等价：UPPER → 剔除非 A-Z → SHA-256 hex
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0004_backfill_sequence_hash"
down_revision: str | None = "0003_srs_triggers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE srs.substance_protein
           SET sequence_hash_hc = encode(
                 digest(regexp_replace(UPPER(heavy_chain_sequence), '[^A-Z]', '', 'g'), 'sha256'),
                 'hex'
               )
         WHERE heavy_chain_sequence IS NOT NULL
           AND heavy_chain_sequence <> ''
           AND sequence_hash_hc IS NULL;
    """)
    op.execute("""
        UPDATE srs.substance_protein
           SET sequence_hash_lc = encode(
                 digest(regexp_replace(UPPER(light_chain_sequence), '[^A-Z]', '', 'g'), 'sha256'),
                 'hex'
               )
         WHERE light_chain_sequence IS NOT NULL
           AND light_chain_sequence <> ''
           AND sequence_hash_lc IS NULL;
    """)


def downgrade() -> None:
    # 不回滚回填本身（数据修复是单向的）；如需重置可手动 UPDATE ... SET hash = NULL
    pass
