"""cmc_analytics：新建 dim.channel_dict（Lucullus 工艺通道字典 = 原始通道名 → 人话名/分类/单位/物理设备）（2026-08-17）

背景：raw 层 `signal_timeseries.channel_code` 必须原样保留源系统短名（m_mfc5 / dm_o2 2 / dm_O2_2 mfc …），
可读性差、别名多、两站命名不一致。按总纲「字典放 cmc_analytics.dim、下游 join 取业务属性」的路子，
把可读名字统一放本表，看板/报表/导出都从这里取显示名，不在应用代码里硬编码。

关键列：
- display_name        中文人话名（看板直接显示）
- canonical_key       「同一物理量」归并键：同一 MFC/泵在不同站、不同别名下的通道共用一个 key
                      （如 ws01 的 m_o2 与 ws02 的 m_mfc3 都是 mfc3_flow）。看板按 key 选曲线，再按批次实际存在的
                      channel_code 取数，跨站对比就顺了。未经数据验证的对应关系留空。
- is_preferred        同一 canonical_key 内首选的通道（物理 MFC 编号命名的那一路）；别名 = false
- device_tag          物理位号：MFC1~5 / DPUMP1~3 / SPUMP1~6 / PH / DO / TEMP / STIRRER / LEVEL1~2 / PRESSURE / REDOX / PHASE
- unit, range_min/max 展示单位与合理量程（来自控制器导入表 + 负责人确认；可做数据质量校验）

初始 78 行 = rd-lucullus-etl 白名单 TARGET_CHANNELS 全部通道。对应关系依据：
- 控制器导入表 docs/ws0x_Import_sheet_ez_Control_for_Lite_v3.03.xlsx（ACTUATOR II 列给出 dm 别名 ↔ MFC 编号）；
- 2026-08-17 用真数据逐批比对（ws01 全部 49 批、ws02 近期批次），只有逐点一致的才填 canonical_key；
- 负责人确认：MFC3 (O2) = 大量程 0~1000 mL/min，MFC5 (O2_2) = 小量程 0~100 mL/min。

维护：新增通道 → 白名单加一行、本表加一行（缺行时下游回退显示 channel_code，不报错）。改名只改本表数据，无需发版。

Revision ID: cmc_analytics_dim_channel_dict
Revises: cmc_analytics_fact_vicell_dedup
Create Date: 2026-08-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "cmc_analytics_dim_channel_dict"
down_revision = "cmc_analytics_fact_vicell_dedup"
branch_labels = None
depends_on = None

_READERS = "lims_reader, quality_user"

# 分类（category）常量 —— 中文，看板直接当分组标题用
_CULT = "培养参数"
_GAS = "气路"
_PUMP = "加料泵"
_LEVEL = "液位/压力"
_OTHER = "阶段/其它"

# 单位常量
_ML = "mL/min"


def _row(code, name, en, long, cat, kind, tag=None, key=None, pref=True, unit=None,
         rmin=None, rmax=None, order=999, notes=None, active=True):
    return dict(code=code, name=name, en=en, long=long, cat=cat, kind=kind, tag=tag, key=key,
                pref=pref, unit=unit, rmin=rmin, rmax=rmax, order=order, notes=notes, active=active)


# fmt: off
_ROWS = [
    # ── 培养参数：温度 / pH / 溶氧 / 搅拌 ─────────────────────────────────────────
    _row("m_temp",      "温度",            "Temperature",            "Measurement temperature sensor", _CULT, "measure",        "TEMP",    "temp",        True, "°C",  0, 150, 10),
    _row("sp_temp",     "温度设定值",       "Temperature setpoint",   "Setpoint for temperature",       _CULT, "setpoint",       "TEMP",    "temp_sp",     True, "°C",  0, 150, 11),
    _row("cs_temp",     "温度控制状态",     "Temperature loop status", "Control status for temperature", _CULT, "control_status", "TEMP",    "temp_cs",     True, None,  0, 1,   12),
    _row("m_ph",        "pH",              "pH",                     "Measurement pH sensor",          _CULT, "measure",        "PH",      "ph",          True, None,  2, 12,  20),
    _row("sp_ph",       "pH 设定值",        "pH setpoint",            "Setpoint for pH",                _CULT, "setpoint",       "PH",      "ph_sp",       True, None,  2, 12,  21),
    _row("cs_ph",       "pH 控制状态",      "pH loop status",         "Control status for pH",          _CULT, "control_status", "PH",      "ph_cs",       True, None,  0, 1,   22),
    _row("m_do",        "溶氧 (DO)",        "Dissolved oxygen",       "Measurement DO sensor",          _CULT, "measure",        "DO",      "do",          True, "%",   0, 100, 30),
    _row("sp_do",       "溶氧设定值",       "DO setpoint",            "Setpoint for DO",                _CULT, "setpoint",       "DO",      "do_sp",       True, "%",   0, 100, 31),
    _row("cs_do",       "溶氧控制状态",     "DO loop status",         "Control status for DO",          _CULT, "control_status", "DO",      "do_cs",       True, None,  0, 1,   32),
    _row("m_ls_opt_do", "溶氧 (光学探头)",  "DO (optical sensor)",    "Measurement LS Optic DO sensor", _CULT, "measure",        "DO_OPT",  "do_opt",      True, "%",   0, 100, 33,
         "光学法溶氧探头（LumiSens），目前两站均未接、无数据；接上即自动同步"),
    _row("sp_ls_opt_do", "溶氧设定值 (光学回路)", "DO setpoint (optical loop)", "Setpoint loop LS optic DO", _CULT, "setpoint",  "DO_OPT",  "do_opt_sp",   True, "%",   0, 100, 34, "占位，暂无数据"),
    _row("cs_ls_opt_do", "溶氧控制状态 (光学回路)", "DO loop status (optical)", "Control status LS optical DO loop", _CULT, "control_status", "DO_OPT", "do_opt_cs", True, None, 0, 1, 35, "占位，暂无数据"),
    _row("m_redox",     "氧化还原电位 (ORP)", "Redox potential",       "Measurement redox sensor",       _CULT, "measure",        "REDOX",   "redox",       True, "mV", -500, 500, 36, "控制器配为记录，探头未接、暂无数据"),
    _row("m_stirrer",   "搅拌转速",         "Stirrer speed",          "Measurement stirrer speed",      _CULT, "measure",        "STIRRER", "stirrer",     True, "rpm", 0, 2000, 40),
    _row("sp_stirrer",  "搅拌转速设定值",   "Stirrer setpoint",       "Setpoint for stirrer",           _CULT, "setpoint",       "STIRRER", "stirrer_sp",  True, "rpm", 0, 2000, 41),
    _row("cs_stirrer",  "搅拌控制状态",     "Stirrer loop status",    "Control status for stirrer",     _CULT, "control_status", "STIRRER", "stirrer_cs",  True, None,  0, 1,   42),

    # ── 气路：物理 MFC 编号命名（两站通用、首选） ────────────────────────────────
    # MFC1 表层空气(AIR1 overlay) / MFC2 深层空气(Air sparge) / MFC3 氧气·大量程 / MFC4 CO2 / MFC5 氧气·小量程
    _row("m_mfc1",  "表层空气流量计 (MFC1) 实时流量", "MFC1 overlay air flow",       "Value of MFC 1 (mL/min)",    _GAS, "measure",    "MFC1", "mfc1_flow",  True, _ML, 0, None, 100),
    _row("sp_mfc1", "表层空气流量计 (MFC1) 设定值",   "MFC1 setpoint",               "Setpoint for MFC 1 (mL/min)", _GAS, "setpoint",   "MFC1", "mfc1_sp",    True, _ML, 0, None, 101, "设定值来自 Lucullus 控制回路，ws02 未配置（无数据）"),
    _row("dm_mfc1", "表层空气流量计 (MFC1) 累计流量", "MFC1 cumulative volume",      "Dose monitor MFC 1",          _GAS, "dose_total", "MFC1", "mfc1_total", True, "L", 0, None, 102),
    _row("m_mfc2",  "深层空气流量计 (MFC2) 实时流量", "MFC2 sparge air flow",        "Value of MFC 2 (mL/min)",    _GAS, "measure",    "MFC2", "mfc2_flow",  True, _ML, 0, None, 110),
    _row("sp_mfc2", "深层空气流量计 (MFC2) 设定值",   "MFC2 setpoint",               "Setpoint for MFC 2 (mL/min)", _GAS, "setpoint",   "MFC2", "mfc2_sp",    True, _ML, 0, None, 111, "ws02 未配置（无数据）"),
    _row("dm_mfc2", "深层空气流量计 (MFC2) 累计流量", "MFC2 cumulative volume",      "Dose monitor MFC 2",          _GAS, "dose_total", "MFC2", "mfc2_total", True, "L", 0, None, 112),
    _row("m_mfc3",  "氧气流量计·大量程 (MFC3) 实时流量", "MFC3 O2 (0-1000) flow",    "Value of MFC 3 (mL/min)",    _GAS, "measure",    "MFC3", "mfc3_flow",  True, _ML, 0, 1000, 120, "深层氧气，大量程 0~1000 mL/min（负责人 2026-08-17 确认）"),
    _row("sp_mfc3", "氧气流量计·大量程 (MFC3) 设定值",  "MFC3 setpoint",              "Setpoint for MFC 3 (mL/min)", _GAS, "setpoint",   "MFC3", "mfc3_sp",    True, _ML, 0, 1000, 121, "ws02 未配置（无数据）"),
    _row("dm_mfc3", "氧气流量计·大量程 (MFC3) 累计流量", "MFC3 cumulative volume",    "Dose monitor MFC 3",          _GAS, "dose_total", "MFC3", "mfc3_total", True, "L", 0, None, 122),
    _row("m_mfc4",  "CO2 流量计 (MFC4) 实时流量",     "MFC4 CO2 flow",               "Value of MFC 4 (mL/min)",    _GAS, "measure",    "MFC4", "mfc4_flow",  True, _ML, 0, None, 130),
    _row("sp_mfc4", "CO2 流量计 (MFC4) 设定值",       "MFC4 setpoint",               "Setpoint for MFC 4 (mL/min)", _GAS, "setpoint",   "MFC4", "mfc4_sp",    True, _ML, 0, None, 131, "ws02 未配置（无数据）"),
    _row("dm_mfc4", "CO2 流量计 (MFC4) 累计流量",     "MFC4 cumulative volume",      "Dose monitor MFC 4",          _GAS, "dose_total", "MFC4", "mfc4_total", True, "L", 0, None, 132),
    _row("m_mfc5",  "氧气流量计·小量程 (MFC5) 实时流量", "MFC5 O2 (0-100) flow",     "Value of MFC 5 (mL/min)",    _GAS, "measure",    "MFC5", "mfc5_flow",  True, _ML, 0, 100, 140, "深层氧气，小量程 0~100 mL/min（O2_2）。2026-07-23 起两站开始记录"),
    _row("sp_mfc5", "氧气流量计·小量程 (MFC5) 设定值",  "MFC5 setpoint",              "Setpoint for MFC 5 (mL/min)", _GAS, "setpoint",   "MFC5", "mfc5_sp",    True, _ML, 0, 100, 141, "控制器导入表未配置，预计一直无数据（占位）", active=False),
    _row("dm_mfc5", "氧气流量计·小量程 (MFC5) 累计流量", "MFC5 cumulative volume",    "Dose monitor MFC 5",          _GAS, "dose_total", "MFC5", "mfc5_total", False, "L", 0, None, 142, "控制器导入表未配置，预计一直无数据；MFC5 累计量的正主是 dm_O2_2 mfc", active=False),

    # ── 气路：控制器侧别名（工作站人工配的累计量名，两站都有；数据与 dm_mfcN 逐点一致） ──
    _row("dm_AIR1 OVER", "表层空气流量计 (MFC1) 累计流量（别名）", "MFC1 cumulative (alias)", "Dose monitor MFC 1", _GAS, "dose_total", "MFC1", "mfc1_total", False, "L", 0, None, 103, "控制器导入表 ACTUATOR=MFC 1；数据=dm_mfc1"),
    _row("dm_AIR1 MFC",  "表层空气流量计 (MFC1) 累计流量（别名2）", "MFC1 cumulative (alias 2)", "Dose monitor MFC 1", _GAS, "dose_total", "MFC1", "mfc1_total", False, "L", 0, None, 104, "仅 ws02 少数批次；数据=dm_mfc1"),
    _row("dm_Air mfc",   "深层空气流量计 (MFC2) 累计流量（别名）", "MFC2 cumulative (alias)", "Dose monitor MFC 2", _GAS, "dose_total", "MFC2", "mfc2_total", False, "L", 0, None, 113, "控制器导入表 ACTUATOR=MFC 2；数据=dm_mfc2"),
    _row("dm_O2_2 MFC",  "深层空气流量计 (MFC2) 累计流量（别名，标签错写 O2_2）", "MFC2 cumulative (mislabelled O2_2)", "Dose monitor MFC 2", _GAS, "dose_total", "MFC2", "mfc2_total", False, "L", 0, None, 114, "大写 MFC；标签写 O2_2 但长名/数据均为 MFC2；仅 ws02 少数批次"),
    _row("dm_O2 MFC",    "氧气流量计·大量程 (MFC3) 累计流量（别名）", "MFC3 cumulative (alias)", "Dose monitor MFC 3", _GAS, "dose_total", "MFC3", "mfc3_total", False, "L", 0, None, 123, "数据=dm_mfc3"),
    _row("dm_CO2 MFC",   "CO2 流量计 (MFC4) 累计流量（别名）",   "MFC4 cumulative (alias)", "Dose monitor MFC 4", _GAS, "dose_total", "MFC4", "mfc4_total", False, "L", 0, None, 133, "数据=dm_mfc4"),
    _row("dm_O2_2 mfc",  "氧气流量计·小量程 (MFC5) 累计流量",    "MFC5 cumulative volume",  "Dose monitor MFC 5", _GAS, "dose_total", "MFC5", "mfc5_total", True,  "L", 0, None, 143, "小写 mfc。控制器导入表 ACTUATOR=MFC 5，是 MFC5 累计量的正主（dm_mfc5 未配置）"),

    # ── 气路：ws01 按气体命名的旧通道（Lucullus 端按罐配置；A1/A3 2026-07 前只有这一套） ──
    # 与物理 MFC 的对应关系 2026-08-17 用 ws01 全部批次逐点比对：除 m_air 外均稳定。
    _row("m_air",   "空气流量·实时（ws01 旧命名）",  "Air flow (ws01 legacy)",  "Value of Air MFC (mL/min)",   _GAS, "measure",    None,   None,        False, _ML, 0, None, 150,
         "对应 MFC 随罐不同：A4=MFC1 表层空气，A1/A3=MFC2 深层空气 → 不归并。A1/A3 2026-07 前只有此通道"),
    _row("m_air2",  "深层空气流量计 (MFC2) 实时流量（ws01 A4 旧命名）", "Air2 flow (ws01 A4)", "Value of Air MFC (mL/min)", _GAS, "measure", "MFC2", "mfc2_flow", False, _ML, 0, None, 151, "仅 A4 罐有；数据=m_mfc2"),
    _row("m_o2",    "氧气流量计·大量程 (MFC3) 实时流量（ws01 旧命名）", "O2 flow (ws01 legacy)", "Value of O2 MFC (mL/min)", _GAS, "measure", "MFC3", "mfc3_flow", False, _ML, 0, 1000, 152, "数据=m_mfc3（全部批次一致）"),
    _row("m_co2",   "CO2 流量计 (MFC4) 实时流量（ws01 旧命名）", "CO2 flow (ws01 legacy)", "Value of CO2 MFC (mL/min)", _GAS, "measure", "MFC4", "mfc4_flow", False, _ML, 0, None, 153, "数据=m_mfc4（全部批次一致）"),
    _row("m_o2 2",  "深层空气流量计 (MFC2) 实时流量（ws01 旧命名，标签 N2/o2_2）", "MFC2 flow (ws01, labelled N2)", "Value of N2 MFC (mL/min)", _GAS, "measure", "MFC2", "mfc2_flow", False, _ML, 0, None, 154,
         "长名写 N2 MFC，但数据与 m_mfc2 逐点一致（全部批次）。ws01 是否真有氮气待现场确认；确认后改名"),
    _row("sp_air",  "深层空气流量计 (MFC2) 设定值（ws01 旧命名）", "Air setpoint (ws01)", "Setpoint for Air MFC (mL/min)", _GAS, "setpoint", "MFC2", "mfc2_sp", False, _ML, 0, None, 155, "数据=sp_mfc2"),
    _row("sp_o2",   "氧气流量计·大量程 (MFC3) 设定值（ws01 旧命名）", "O2 setpoint (ws01)", "Setpoint for O2 MFC (mL/min)", _GAS, "setpoint", "MFC3", "mfc3_sp", False, _ML, 0, 1000, 156, "数据=sp_mfc3"),
    _row("sp_co2",  "CO2 流量计 (MFC4) 设定值（ws01 旧命名）", "CO2 setpoint (ws01)", "Setpoint for CO2 MFC (mL/min)", _GAS, "setpoint", "MFC4", "mfc4_sp", False, _ML, 0, None, 157, "数据=sp_mfc4"),
    _row("sp_n2",   "表层空气流量计 (MFC1) 设定值（ws01 旧命名，标签 N2）", "MFC1 setpoint (ws01, labelled N2)", "Setpoint for N2 MFC (mL/min)", _GAS, "setpoint", "MFC1", "mfc1_sp", False, _ML, 0, None, 158,
         "长名写 N2，但数据与 sp_mfc1 逐点一致（全部批次）。待现场确认 MFC1 气体"),
    _row("dm_air",  "深层空气流量计 (MFC2) 累计流量（ws01 旧命名）", "Air cumulative (ws01)", "Dose monitor Air MFC", _GAS, "dose_total", "MFC2", "mfc2_total", False, "L", 0, None, 159, "数据=dm_mfc2（注意：m_air 却对应 MFC1/2 不定）"),
    _row("dm_air2", "空气2累计流量（ws01 旧命名）", "Air2 cumulative (ws01)", "Dose monitor Air MFC", _GAS, "dose_total", None, None, False, "L", 0, None, 160, "无数据，对应关系无法验证", active=False),
    _row("dm_o2",   "氧气流量计·大量程 (MFC3) 累计流量（ws01 旧命名）", "O2 cumulative (ws01)", "Dose monitor O2 MFC", _GAS, "dose_total", "MFC3", "mfc3_total", False, "L", 0, None, 161, "数据=dm_mfc3"),
    _row("dm_co2",  "CO2 流量计 (MFC4) 累计流量（ws01 旧命名）", "CO2 cumulative (ws01)", "Dose monitor CO2 MFC", _GAS, "dose_total", "MFC4", "mfc4_total", False, "L", 0, None, 162, "数据=dm_mfc4"),
    _row("dm_o2 2", "深层空气流量计 (MFC2) 累计流量（ws01 旧命名，标签 N2/o2_2）", "MFC2 cumulative (ws01, labelled N2)", "Dose monitor N2 MFC", _GAS, "dose_total", "MFC2", "mfc2_total", False, "L", 0, None, 163, "长名写 N2，数据与 dm_mfc2 逐点一致"),

    # ── 加料泵 ─────────────────────────────────────────────────────────────────
    _row("dm_dpump2",  "补碱泵 (数字泵2) 累计加入量", "Base pump (digital pump 2) cumulative", "Dose monitor digital pump 2", _PUMP, "dose_total", "DPUMP2", "dpump2_total", True, "mL", 0, None, 200, "两站验证：ws01 dm_alkali 与之逐点一致；ws02 经 pH 相关性确认为补碱泵"),
    _row("dm_alkali",  "补碱泵累计加入量（ws01 旧命名）", "Base pump cumulative (ws01)", "Dose monitor alkali pump", _PUMP, "dose_total", "DPUMP2", "dpump2_total", False, "mL", 0, None, 201, "数据=dm_dpump2；ws01 A1/A3 2026-07 前只有此通道"),
    _row("dm_dpump1",  "数字泵1 累计加入量", "Digital pump 1 cumulative", "Dose monitor digital pump 1", _PUMP, "dose_total", "DPUMP1", "dpump1_total", True, "mL", 0, None, 210, "酸泵或液位泵之一，用得少，功能待定"),
    _row("dm_dpump3",  "数字泵3 累计加入量", "Digital pump 3 cumulative", "Dose monitor digital pump 3", _PUMP, "dose_total", "DPUMP3", "dpump3_total", True, "mL", 0, None, 211, "酸泵或液位泵之一，用得少，功能待定"),
    _row("dm_acid",    "补酸泵累计加入量（ws01 旧命名）", "Acid pump cumulative (ws01)", "Dose monitor acid pump", _PUMP, "dose_total", None, None, False, "mL", 0, None, 212, "与 dm_dpump1/3 的对应关系无法用数据验证（多为 0）"),
    _row("dm_acid_co2", "酸泵/CO2阀 累计（ws01 旧命名）", "Acid pump / CO2 valve cumulative (ws01)", "Dose monitor acid pump / co2 valve", _PUMP, "dose_total", None, None, False, "mL", 0, None, 213, "名义上是 pH 下调(酸泵/CO2阀)累计，但 ws01 数据与 dm_alkali / dm_dpump2 逐点相同（同一泵输出），含义待现场确认"),
    _row("dm_level",   "液位泵累计加入量（ws01 旧命名）", "Level pump cumulative (ws01)", "Dose monitor level pump", _PUMP, "dose_total", None, None, False, "mL", 0, None, 214, "多为 0，对应关系待验证"),
    _row("sp_spump1",      "步进泵1 设定值",     "Stepper pump 1 setpoint",   "Setpoint for Stepper pump 1",     _PUMP, "setpoint", "SPUMP1", "spump1_sp",      True, None, None, None, 220, "暂无数据", active=False),
    _row("sp_spump1_perc", "步进泵1 设定值(%)",  "Stepper pump 1 setpoint %", "Setpoint for Stepper pump 1 (%)", _PUMP, "setpoint", "SPUMP1", "spump1_sp_perc", True, "%",  0, 100,  221, "暂无数据", active=False),
    _row("sp_spump2",      "步进泵2 设定值",     "Stepper pump 2 setpoint",   "Setpoint for Stepper pump 2",     _PUMP, "setpoint", "SPUMP2", "spump2_sp",      True, None, None, None, 222, "暂无数据", active=False),
    _row("sp_spump2_perc", "步进泵2 设定值(%)",  "Stepper pump 2 setpoint %", "Setpoint for Stepper pump 2 (%)", _PUMP, "setpoint", "SPUMP2", "spump2_sp_perc", True, "%",  0, 100,  223, "暂无数据", active=False),
    _row("sp_spump3",      "步进泵3 设定值",     "Stepper pump 3 setpoint",   "Setpoint for Stepper pump 3",     _PUMP, "setpoint", "SPUMP3", "spump3_sp",      True, None, None, None, 224, "暂无数据", active=False),
    _row("sp_spump3_perc", "步进泵3 设定值(%)",  "Stepper pump 3 setpoint %", "Setpoint for Stepper pump 3 (%)", _PUMP, "setpoint", "SPUMP3", "spump3_sp_perc", True, "%",  0, 100,  225, "暂无数据", active=False),
    _row("sp_spump4",      "步进泵4 设定值",     "Stepper pump 4 setpoint",   "Setpoint for Stepper pump 4",     _PUMP, "setpoint", "SPUMP4", "spump4_sp",      True, None, None, None, 226, "暂无数据", active=False),
    _row("sp_spump4_perc", "步进泵4 设定值(%)",  "Stepper pump 4 setpoint %", "Setpoint for Stepper pump 4 (%)", _PUMP, "setpoint", "SPUMP4", "spump4_sp_perc", True, "%",  0, 100,  227, "暂无数据", active=False),
    _row("sp_spump5",      "步进泵5 设定值",     "Stepper pump 5 setpoint",   "Setpoint for Stepper pump 5",     _PUMP, "setpoint", "SPUMP5", "spump5_sp",      True, None, None, None, 228, "暂无数据", active=False),
    _row("sp_spump6",      "步进泵6 设定值",     "Stepper pump 6 setpoint",   "Setpoint for Stepper pump 6",     _PUMP, "setpoint", "SPUMP6", "spump6_sp",      True, None, None, None, 229, "暂无数据", active=False),
    _row("dm_spump2",      "步进泵2 累计加入量", "Stepper pump 2 cumulative", "Dose monitor stepper pump 2",     _PUMP, "dose_total", "SPUMP2", "spump2_total", True, "mL", 0, None, 230, "暂无数据", active=False),
    _row("dm_spump3",      "步进泵3 累计加入量", "Stepper pump 3 cumulative", "Dose monitor stepper pump 3",     _PUMP, "dose_total", "SPUMP3", "spump3_total", True, "mL", 0, None, 231, "暂无数据", active=False),
    _row("dm_spump4",      "步进泵4 累计加入量", "Stepper pump 4 cumulative", "Dose monitor stepper pump 4",     _PUMP, "dose_total", "SPUMP4", "spump4_total", True, "mL", 0, None, 232, "暂无数据", active=False),

    # ── 液位 / 压力 ────────────────────────────────────────────────────────────
    _row("m_level1",   "液位1",          "Level 1",             "Measurement Level 1 sensor",     _LEVEL, "measure",        "LEVEL1",   "level1",     True, None, 0, 1, 300, "0/1 状态量（液位开关）；ws01 有数据"),
    _row("m_level2",   "液位2",          "Level 2",             "Measurement Level 2 sensor",     _LEVEL, "measure",        "LEVEL2",   "level2",     True, None, 0, 1, 301, "暂无数据", active=False),
    _row("cs_level1",  "液位1 控制状态",  "Level 1 loop status", "Control status for Level 1 loop", _LEVEL, "control_status", "LEVEL1",   "level1_cs",  True, None, 0, 1, 302, "暂无数据"),
    _row("cs_level2",  "液位2 控制状态",  "Level 2 loop status", "Control status for Level 2 loop", _LEVEL, "control_status", "LEVEL2",   "level2_cs",  True, None, 0, 1, 303, "暂无数据", active=False),
    _row("m_pressure", "罐压",           "Vessel pressure",     "Measurement pressure sensor (PT-9.11)", _LEVEL, "measure",  "PRESSURE", "pressure",   True, None, None, None, 310, "暂无数据；将来接压力传感器即自动同步"),

    # ── 阶段 / 其它 ────────────────────────────────────────────────────────────
    _row("Phase",      "工艺阶段",        "Process phase",       "Phase",                          _OTHER, "other",         "PHASE",    "phase",      True, None, None, None, 400, "阶段编号（数值型），暂无数据"),
]
# fmt: on


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE dim.channel_dict (
            source_system     text NOT NULL DEFAULT 'lucullus',
            channel_code      text NOT NULL,                 -- 原始短名，与 raw.signal_timeseries.channel_code 逐字符一致（大小写/空格敏感）
            display_name      text NOT NULL,                 -- 中文人话名（看板显示）
            display_name_en   text,                          -- 英文名（可选）
            source_long_name  text,                          -- 源系统长名（Lucullus logiportname / 控制器 PORT NAME）
            category          text NOT NULL,                 -- 分组：培养参数 / 气路 / 加料泵 / 液位/压力 / 阶段/其它
            measure_kind      text NOT NULL,                 -- measure / setpoint / control_status / dose_total / other
            device_tag        text,                          -- 物理位号：MFC1~5 / DPUMP1~3 / SPUMP1~6 / PH / DO / TEMP / STIRRER / LEVEL1~2 / PRESSURE / REDOX / PHASE
            canonical_key     text,                          -- 同一物理量归并键（跨站/别名共用），未经验证留空
            is_preferred      boolean NOT NULL DEFAULT true, -- 同 canonical_key 内首选通道；别名=false
            unit              text,                          -- 展示单位
            range_min         double precision,              -- 合理量程下限（控制器导入表 / 负责人）
            range_max         double precision,              -- 合理量程上限
            is_active         boolean NOT NULL DEFAULT true, -- false=占位/预计无数据，看板默认不列
            sort_order        integer NOT NULL DEFAULT 999,
            notes             text,
            updated_at        timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (source_system, channel_code),
            CHECK (measure_kind IN ('measure','setpoint','control_status','dose_total','other'))
        );
        CREATE INDEX idx_channel_dict_canonical ON dim.channel_dict (canonical_key) WHERE canonical_key IS NOT NULL;

        COMMENT ON TABLE dim.channel_dict IS
            'Lucullus 工艺通道字典：原始 channel_code → 人话名/分类/单位/物理位号/归并键。'
            '看板与报表从此表取显示名，不在代码里硬编码；缺行时回退显示 channel_code。'
            '同一 canonical_key 下按批次实际存在的通道取数（is_preferred 优先），实现跨站/跨别名对比。';
        COMMENT ON COLUMN dim.channel_dict.channel_code IS '原始短名，与 cmc_rd.raw_rd_usp_lucullus.signal_timeseries.channel_code 逐字符一致（区分大小写与空格）。';
        COMMENT ON COLUMN dim.channel_dict.canonical_key IS '同一物理量归并键：如 ws01 的 m_o2 与 ws02 的 m_mfc3 都是 mfc3_flow。只填经真数据逐点验证的对应关系。';
        COMMENT ON COLUMN dim.channel_dict.is_preferred IS '同 canonical_key 内首选展示/分析的通道（物理 MFC/泵编号命名那一路）；别名与 ws01 旧命名为 false。';
        COMMENT ON COLUMN dim.channel_dict.is_active IS 'false = 占位/预计长期无数据（如 sp_mfc5、dm_mfc5、步进泵）；看板默认不列，但仍可 join。';
        """
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO dim.channel_dict
                (channel_code, display_name, display_name_en, source_long_name, category, measure_kind,
                 device_tag, canonical_key, is_preferred, unit, range_min, range_max, is_active, sort_order, notes)
            VALUES
                (:code, :name, :en, :long, :cat, :kind,
                 :tag, :key, :pref, :unit, :rmin, :rmax, :active, :order, :notes)
            ON CONFLICT (source_system, channel_code) DO NOTHING
            """
        ),
        _ROWS,
    )

    op.execute(f"GRANT USAGE ON SCHEMA dim TO {_READERS}, lucullus_etl")
    op.execute(f"GRANT SELECT ON dim.channel_dict TO {_READERS}, lucullus_etl")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS dim.channel_dict")
