"""cmc_analytics：dim.channel_dict 显示名再精简——中英混排短名（2026-08-17 负责人要求）

规则：测量值直接 `Temp / pH / DO / 搅拌`；设定值加 ` SP`；控制状态加 ` 状态`；
气路 `Air_mfc(表层)` / `Air_mfc(深层)` / `O2_mfc(0-1000)` / `O2_mfc(0-100)` / `CO2_mfc`，累计量加 ` 累计`；
别名与 ws01 旧命名通道**用同一个名字**（不再写"别名/旧命名"，看板靠 canonical_key + is_preferred 在正主存在时隐藏别名）。
最长 17 字符。原始代号在 channel_code、MFC 编号在 device_tag，信息不丢。

Revision ID: cmc_analytics_chdict_short2
Revises: cmc_analytics_chdict_short
Create Date: 2026-08-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "cmc_analytics_chdict_short2"
down_revision = "cmc_analytics_chdict_short"
branch_labels = None
depends_on = None

# channel_code -> (新显示名, 旧显示名)   旧名用于 downgrade
_NAMES = {
    'm_temp': ('Temp', '温度'),
    'sp_temp': ('Temp SP', '温度设定值'),
    'cs_temp': ('Temp 状态', '温度控制状态'),
    'm_ph': ('pH', 'pH'),
    'sp_ph': ('pH SP', 'pH 设定值'),
    'cs_ph': ('pH 状态', 'pH 控制状态'),
    'm_do': ('DO', '溶氧'),
    'sp_do': ('DO SP', '溶氧设定值'),
    'cs_do': ('DO 状态', '溶氧控制状态'),
    'm_ls_opt_do': ('DO(光学)', '溶氧(光学)'),
    'sp_ls_opt_do': ('DO(光学) SP', '溶氧设定值(光学)'),
    'cs_ls_opt_do': ('DO(光学) 状态', '溶氧控制状态(光学)'),
    'm_redox': ('ORP', '氧化还原电位'),
    'm_stirrer': ('搅拌', '搅拌转速'),
    'sp_stirrer': ('搅拌 SP', '搅拌转速设定值'),
    'cs_stirrer': ('搅拌 状态', '搅拌控制状态'),
    'm_mfc1': ('Air_mfc(表层)', '表层空气流量'),
    'sp_mfc1': ('Air_mfc(表层) SP', '表层空气流量设定值'),
    'dm_mfc1': ('Air_mfc(表层) 累计', '表层空气累计量'),
    'dm_AIR1 OVER': ('Air_mfc(表层) 累计', '表层空气累计量（别名）'),
    'dm_AIR1 MFC': ('Air_mfc(表层) 累计', '表层空气累计量（别名2）'),
    'm_mfc2': ('Air_mfc(深层)', '深层空气流量'),
    'sp_mfc2': ('Air_mfc(深层) SP', '深层空气流量设定值'),
    'dm_mfc2': ('Air_mfc(深层) 累计', '深层空气累计量'),
    'dm_Air mfc': ('Air_mfc(深层) 累计', '深层空气累计量（别名）'),
    'dm_O2_2 MFC': ('Air_mfc(深层) 累计', '深层空气累计量（别名·错标O2_2）'),
    'm_mfc3': ('O2_mfc(0-1000)', '氧气(大量程)流量'),
    'sp_mfc3': ('O2_mfc(0-1000) SP', '氧气(大量程)流量设定值'),
    'dm_mfc3': ('O2_mfc(0-1000) 累计', '氧气(大量程)累计量'),
    'dm_O2 MFC': ('O2_mfc(0-1000) 累计', '氧气(大量程)累计量（别名）'),
    'm_mfc4': ('CO2_mfc', 'CO2 流量'),
    'sp_mfc4': ('CO2_mfc SP', 'CO2 流量设定值'),
    'dm_mfc4': ('CO2_mfc 累计', 'CO2 累计量'),
    'dm_CO2 MFC': ('CO2_mfc 累计', 'CO2 累计量（别名）'),
    'm_mfc5': ('O2_mfc(0-100)', '氧气(小量程)流量'),
    'sp_mfc5': ('O2_mfc(0-100) SP', '氧气(小量程)流量设定值'),
    'dm_mfc5': ('O2_mfc(0-100) 累计', '氧气(小量程)累计量'),
    'dm_O2_2 mfc': ('O2_mfc(0-100) 累计', '氧气(小量程)累计量'),
    'm_air': ('Air_mfc', '空气流量（旧命名）'),
    'm_air2': ('Air_mfc(深层)', '深层空气流量（旧命名·A4）'),
    'm_o2': ('O2_mfc(0-1000)', '氧气(大量程)流量（旧命名）'),
    'm_co2': ('CO2_mfc', 'CO2 流量（旧命名）'),
    'm_o2 2': ('Air_mfc(深层)', '深层空气流量（旧命名·错标N2）'),
    'sp_air': ('Air_mfc(深层) SP', '深层空气流量设定值（旧命名）'),
    'sp_o2': ('O2_mfc(0-1000) SP', '氧气(大量程)流量设定值（旧命名）'),
    'sp_co2': ('CO2_mfc SP', 'CO2 流量设定值（旧命名）'),
    'sp_n2': ('Air_mfc(表层) SP', '表层空气流量设定值（旧命名·错标N2）'),
    'dm_air': ('Air_mfc(深层) 累计', '深层空气累计量（旧命名）'),
    'dm_air2': ('Air_mfc 累计', '空气2累计量（旧命名）'),
    'dm_o2': ('O2_mfc(0-1000) 累计', '氧气(大量程)累计量（旧命名）'),
    'dm_co2': ('CO2_mfc 累计', 'CO2 累计量（旧命名）'),
    'dm_o2 2': ('Air_mfc(深层) 累计', '深层空气累计量（旧命名·错标N2）'),
    'dm_dpump2': ('碱泵 累计', '补碱泵累计量'),
    'dm_alkali': ('碱泵 累计', '补碱泵累计量（旧命名）'),
    'dm_dpump1': ('泵1 累计', '数字泵1累计量'),
    'dm_dpump3': ('泵3 累计', '数字泵3累计量'),
    'dm_acid': ('酸泵 累计', '补酸泵累计量（旧命名）'),
    'dm_acid_co2': ('酸泵/CO2阀 累计', '酸泵/CO2阀累计量（旧命名）'),
    'dm_level': ('液位泵 累计', '液位泵累计量（旧命名）'),
    'sp_spump1': ('步进泵1 SP', '步进泵1设定值'),
    'sp_spump1_perc': ('步进泵1 SP(%)', '步进泵1设定值(%)'),
    'sp_spump2': ('步进泵2 SP', '步进泵2设定值'),
    'sp_spump2_perc': ('步进泵2 SP(%)', '步进泵2设定值(%)'),
    'sp_spump3': ('步进泵3 SP', '步进泵3设定值'),
    'sp_spump3_perc': ('步进泵3 SP(%)', '步进泵3设定值(%)'),
    'sp_spump4': ('步进泵4 SP', '步进泵4设定值'),
    'sp_spump4_perc': ('步进泵4 SP(%)', '步进泵4设定值(%)'),
    'sp_spump5': ('步进泵5 SP', '步进泵5设定值'),
    'sp_spump6': ('步进泵6 SP', '步进泵6设定值'),
    'dm_spump2': ('步进泵2 累计', '步进泵2累计量'),
    'dm_spump3': ('步进泵3 累计', '步进泵3累计量'),
    'dm_spump4': ('步进泵4 累计', '步进泵4累计量'),
    'm_level1': ('液位1', '液位1'),
    'm_level2': ('液位2', '液位2'),
    'cs_level1': ('液位1 状态', '液位1控制状态'),
    'cs_level2': ('液位2 状态', '液位2控制状态'),
    'm_pressure': ('罐压', '罐压'),
    'Phase': ('阶段', '工艺阶段'),
}

_SQL = sa.text(
    "UPDATE dim.channel_dict SET display_name = :name, updated_at = now() "
    "WHERE source_system = 'lucullus' AND channel_code = :code"
)


def upgrade() -> None:
    op.get_bind().execute(_SQL, [{"code": c, "name": new} for c, (new, _old) in _NAMES.items()])


def downgrade() -> None:
    op.get_bind().execute(_SQL, [{"code": c, "name": old} for c, (_new, old) in _NAMES.items()])
