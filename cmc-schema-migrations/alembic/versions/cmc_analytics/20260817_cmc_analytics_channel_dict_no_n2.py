"""cmc_analytics：dim.channel_dict 数据修订——ws01 "N2" 标签通道定名（罐上无氮气，2026-08-17 负责人确认）

负责人确认：所有罐子都没有氮气气路。ws01 Lucullus 端标签写 N2 的三个通道（m_o2 2 / dm_o2 2 / sp_n2）
经全部批次逐点比对，数据分别等于 MFC2 实时流量 / MFC2 累计量 / MFC1 设定值（表层/深层空气），
与小量程氧气 MFC5 完全对不上——是历史错标签，不是被氧气占用。本迁移只改这 3 行的显示名与备注，去掉"待确认"。

Revision ID: cmc_analytics_chdict_no_n2
Revises: cmc_analytics_dim_channel_dict
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_chdict_no_n2"
down_revision = "cmc_analytics_dim_channel_dict"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE dim.channel_dict SET
            display_name = '深层空气流量计 (MFC2) 实时流量（ws01 旧命名，错标 N2）',
            display_name_en = 'MFC2 sparge air flow (ws01 legacy, mislabelled N2)',
            notes = '长名写 N2 MFC，但罐上没有氮气气路（负责人 2026-08-17 确认）；数据与 m_mfc2 逐点一致（全部批次）。历史错标签。',
            updated_at = now()
        WHERE source_system = 'lucullus' AND channel_code = 'm_o2 2';

        UPDATE dim.channel_dict SET
            display_name = '深层空气流量计 (MFC2) 累计流量（ws01 旧命名，错标 N2）',
            display_name_en = 'MFC2 cumulative (ws01 legacy, mislabelled N2)',
            notes = '长名写 N2 MFC，但罐上没有氮气气路（负责人 2026-08-17 确认）；数据与 dm_mfc2 逐点一致。历史错标签。',
            updated_at = now()
        WHERE source_system = 'lucullus' AND channel_code = 'dm_o2 2';

        UPDATE dim.channel_dict SET
            display_name = '表层空气流量计 (MFC1) 设定值（ws01 旧命名，错标 N2）',
            display_name_en = 'MFC1 setpoint (ws01 legacy, mislabelled N2)',
            notes = '长名写 N2，但罐上没有氮气气路（负责人 2026-08-17 确认）；数据与 sp_mfc1 逐点一致（全部批次）。历史错标签。',
            updated_at = now()
        WHERE source_system = 'lucullus' AND channel_code = 'sp_n2';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE dim.channel_dict SET
            display_name = '深层空气流量计 (MFC2) 实时流量（ws01 旧命名，标签 N2/o2_2）',
            display_name_en = 'MFC2 flow (ws01, labelled N2)',
            notes = '长名写 N2 MFC，但数据与 m_mfc2 逐点一致（全部批次）。ws01 是否真有氮气待现场确认；确认后改名'
        WHERE source_system = 'lucullus' AND channel_code = 'm_o2 2';
        UPDATE dim.channel_dict SET
            display_name = '深层空气流量计 (MFC2) 累计流量（ws01 旧命名，标签 N2/o2_2）',
            display_name_en = 'MFC2 cumulative (ws01, labelled N2)',
            notes = '长名写 N2，数据与 dm_mfc2 逐点一致'
        WHERE source_system = 'lucullus' AND channel_code = 'dm_o2 2';
        UPDATE dim.channel_dict SET
            display_name = '表层空气流量计 (MFC1) 设定值（ws01 旧命名，标签 N2）',
            display_name_en = 'MFC1 setpoint (ws01, labelled N2)',
            notes = '长名写 N2，但数据与 sp_mfc1 逐点一致（全部批次）。待现场确认 MFC1 气体'
        WHERE source_system = 'lucullus' AND channel_code = 'sp_n2';
        """
    )
