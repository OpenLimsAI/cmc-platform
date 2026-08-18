"""tgt.target 增加完整氨基酸序列（UniProt canonical sequence）

Revision ID: 0052_tgt_sequence
Revises: 0051_tgt_uniprot_fields
Create Date: 2026-08-18 03:00:00.000000

负责人要求：靶点保存完整序列（与 UniProt 一致），分子量按 UniProt 原值（Da）展示，MD5 全显。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0052_tgt_sequence"
down_revision: str | None = "0051_tgt_uniprot_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("target", sa.Column("sequence", sa.Text), schema="tgt")           # 单字母氨基酸序列（canonical）
    op.add_column("target", sa.Column("sequence_crc64", sa.String(16)), schema="tgt")


def downgrade() -> None:
    op.drop_column("target", "sequence_crc64", schema="tgt")
    op.drop_column("target", "sequence", schema="tgt")
