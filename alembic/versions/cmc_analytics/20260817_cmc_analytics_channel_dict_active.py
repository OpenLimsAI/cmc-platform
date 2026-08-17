"""cmc_analytics：dim.channel_dict.is_active 语义收紧为「看板是否列出」；m_air 设为不列（2026-08-17）

之前 is_active=false 同时表示"占位/预计无数据"和"不显示"，两层意思混在一起：占位通道将来若开始有数据会被误藏。
现在：is_active 只表示**看板是否列出**（有数据才会出现，所以占位通道保持 true 无副作用）；
唯一设为 false 的是 ws01 旧命名 `m_air`——它在全部 49 个批次里都与其它通道逐点重复
（A4 罐 = m_mfc1 表层空气；A1/A3/A5 罐 = m_o2 2 / m_mfc2 深层空气），且对应 MFC 随罐不同无法归并，列出来只会多一个重复按钮。

Revision ID: cmc_analytics_chdict_active
Revises: cmc_analytics_chdict_short2
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_chdict_active"
down_revision = "cmc_analytics_chdict_short2"
branch_labels = None
depends_on = None

_WAS_INACTIVE = (
    "sp_mfc5", "dm_mfc5", "dm_air2", "sp_spump1", "sp_spump1_perc", "sp_spump2", "sp_spump2_perc",
    "sp_spump3", "sp_spump3_perc", "sp_spump4", "sp_spump4_perc", "sp_spump5", "sp_spump6",
    "dm_spump2", "dm_spump3", "dm_spump4", "m_level2", "cs_level2",
)


def upgrade() -> None:
    op.execute("UPDATE dim.channel_dict SET is_active = true, updated_at = now() WHERE source_system = 'lucullus'")
    op.execute(
        """
        UPDATE dim.channel_dict SET is_active = false, updated_at = now(),
            notes = 'ws01 旧命名。全部 49 批逐点比对：A4 罐 = m_mfc1(表层)，A1/A3/A5 罐 = m_o2 2 / m_mfc2(深层)——'
                    '对应 MFC 随罐不同无法归并，且总有等价通道，看板不列（is_active=false）。数据仍在 raw 层。'
        WHERE source_system = 'lucullus' AND channel_code = 'm_air'
        """
    )
    op.execute(
        "COMMENT ON COLUMN dim.channel_dict.is_active IS "
        "'看板是否列出该通道（有数据才会出现）。false 仅用于与其它通道逐点重复、又无法归并的冗余通道（如 ws01 m_air）。'"
    )


def downgrade() -> None:
    op.execute("UPDATE dim.channel_dict SET is_active = true WHERE source_system = 'lucullus' AND channel_code = 'm_air'")
    codes = ", ".join(f"'{c}'" for c in _WAS_INACTIVE)
    op.execute(f"UPDATE dim.channel_dict SET is_active = false WHERE source_system = 'lucullus' AND channel_code IN ({codes})")
    op.execute(
        "COMMENT ON COLUMN dim.channel_dict.is_active IS "
        "'false = 占位/预计长期无数据（如 sp_mfc5、dm_mfc5、步进泵）；看板默认不列，但仍可 join。'"
    )
