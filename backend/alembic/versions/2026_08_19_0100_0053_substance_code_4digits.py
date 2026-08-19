"""物质编码位数 7 → 4：SUB-0000001 → SUB-0001

Revision ID: 0053_substance_code_4digits
Revises: 0052_tgt_sequence
Create Date: 2026-08-19 01:00:00.000000

负责人 2026-08-19 决定：物质模块尚未正式上线，SUB- 后数字由 7 位改为 4 位（LPAD 只补齐不截断，
超过 9999 会自然变 5 位）。取号逻辑不变（meta.fn_next_code 读 padding_length），只改序列配置；
同时把已存在的、数值 ≤ 9999 的编码重写为 4 位（生产库当时仅 SUB-0000001 一条），并同步审计里的 entity_code。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0053_substance_code_4digits"
down_revision: str | None = "0052_tgt_sequence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE meta.code_sequence
           SET padding_length = 4,
               description = 'Substance 编码序列：SUB-0001 ...（2026-08-19 起 4 位）',
               updated_at = NOW()
         WHERE sequence_name = 'substance'
    """)
    # 已有编码：SUB-0000001 → SUB-0001（只处理纯数字且 ≤ 9999 的；触发器不重跑取号）
    op.execute("SELECT set_config('app.change_reason', '物质编码位数 7→4（migration 0053）', true)")
    op.execute("""
        UPDATE audit.audit_log a
           SET entity_code = 'SUB-' || LPAD(substring(a.entity_code from 5)::int::text, 4, '0')
         WHERE a.entity_table IN ('substance')
           AND a.entity_code ~ '^SUB-[0-9]{7}$'
           AND substring(a.entity_code from 5)::int <= 9999
    """)
    op.execute("""
        UPDATE srs.substance
           SET substance_code = 'SUB-' || LPAD(substring(substance_code from 5)::int::text, 4, '0')
         WHERE substance_code ~ '^SUB-[0-9]{7}$'
           AND substring(substance_code from 5)::int <= 9999
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE srs.substance
           SET substance_code = 'SUB-' || LPAD(substring(substance_code from 5)::int::text, 7, '0')
         WHERE substance_code ~ '^SUB-[0-9]{4}$'
    """)
    op.execute("""
        UPDATE audit.audit_log
           SET entity_code = 'SUB-' || LPAD(substring(entity_code from 5)::int::text, 7, '0')
         WHERE entity_table = 'substance' AND entity_code ~ '^SUB-[0-9]{4}$'
    """)
    op.execute("""
        UPDATE meta.code_sequence
           SET padding_length = 7, updated_at = NOW()
         WHERE sequence_name = 'substance'
    """)
