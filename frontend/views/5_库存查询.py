"""
文件: frontend/views/5_库存查询.py
用途: 库存查询(物料汇总 / 批次明细),支持导出 Excel
"""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from utils import (
    api_get, APIError, get_categories, get_locations, fmt_null,
    locations_grouped, MATERIAL_TYPE_LABELS, material_type_label,
)
from auth_helper import require_login

require_login()
st.header("📊 库存查询")

view = st.radio("查看维度", ["按物料汇总", "按批次明细"], horizontal=True)

categories = get_categories()
locations = get_locations()
grouped = locations_grouped(locations)

# TT分类筛选: 4 个入库大类(material_type)
_TYPE_OPTIONS = ["(全部TT分类)"] + list(MATERIAL_TYPE_LABELS.values())  # 试剂/耗材/标准物质/色谱柱
_TYPE_REVERSE = {v: k for k, v in MATERIAL_TYPE_LABELS.items()}

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    mt_label = st.selectbox("TT分类", _TYPE_OPTIONS)
    mt_code = _TYPE_REVERSE.get(mt_label)  # None = 全部
with c2:
    cat = st.selectbox("分类", ["(全部分类)"] + categories)
with c3:
    keyword = st.text_input("代码 / 名称 / 批号",
                            help="一个框搜三种:物料代码、物料名称、批号(三个命中其一即出)")
with c4:
    inc_inactive = st.checkbox("含已停用", value=False)
with c5:
    inc_expired = st.checkbox("含已过期(批次)", value=False)
with c6:
    # 默认排除零库存:用户日常视图。勾选后包含 0 库存物料/批次,看完整目录
    inc_zero = st.checkbox("含零库存", value=False)

# 位置三级联(批次明细才用,物料汇总忽略)
loc_id = None
if view == "按批次明细":
    lc1, lc2, lc3 = st.columns(3)
    with lc1:
        room = st.selectbox("房间", ["(全部)"] + sorted(grouped.keys()), key="q_room")
    with lc2:
        if room != "(全部)":
            cabs = ["(全部)"] + sorted(grouped.get(room, {}).keys())
            cabinet = st.selectbox("柜号", cabs, key="q_cab")
        else:
            cabinet = "(全部)"
            st.selectbox("柜号", ["(全部)"], disabled=True, key="q_cab_dis")
    with lc3:
        if room != "(全部)" and cabinet != "(全部)":
            layer_rows = grouped.get(room, {}).get(cabinet, [])
            layer_opts = {"(全部)": None,
                          **{f"L{l['layer_no']}": l["location_id"] for l in layer_rows}}
            layer_lbl = st.selectbox("板层", list(layer_opts.keys()), key="q_layer")
            loc_id = layer_opts.get(layer_lbl)
            if cabinet != "(全部)" and layer_lbl == "(全部)":
                # 想要查整柜,后端目前只支持单 location_id;提示用户
                st.caption("ℹ️ 暂只支持按单个具体板层精确过滤")
        else:
            st.selectbox("板层", ["(全部)"], disabled=True, key="q_layer_dis")

params = {}
if mt_code:
    params["material_type"] = mt_code
if cat != "(全部分类)":
    params["category"] = cat
if keyword:
    params["keyword"] = keyword
if inc_inactive:
    params["include_inactive"] = "true"

if view == "按物料汇总":
    bp = dict(params)
    # only_positive=True 是后端默认。勾"含零库存" → 显式传 false
    if inc_zero:
        bp["only_positive"] = "false"
    try:
        rows = api_get("/api/stock/by-material", params=bp) or []
    except APIError as e:
        st.error(str(e))
        rows = []

    if rows:
        df = pd.DataFrame([
            {
                "ID": r["material_id"],
                "代码": r["material_code"],
                "物料名称": r["name_cn"],
                "TT分类": material_type_label(r.get("material_type")),
                "分类": fmt_null(r.get("category")),
                "生产商": fmt_null(r.get("manufacturer")),
                "规格/型号": fmt_null(r.get("spec_model")),
                "货号": fmt_null(r.get("catalog_no")),
                "单位": r["unit"],
                "总库存": r["total_qty"],
                "安全库存": r["safety_stock"],
                "低库存": "⚠️" if r["low_stock"] else "",
                "状态": "在用" if r["is_active"] else "已停用",
            }
            for r in rows
        ])
        st.dataframe(df, use_container_width=True, height=520)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="库存-物料")
        st.download_button("⬇️ 导出 Excel", data=buf.getvalue(),
                           file_name="库存_按物料汇总.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("无数据")

else:  # 按批次明细
    bp = dict(params)
    bp["include_expired"] = str(inc_expired).lower()
    # only_positive 在 by-batch 后端默认就是 True;勾"含零库存"传 false
    if inc_zero:
        bp["only_positive"] = "false"
    if loc_id is not None:
        bp["location_id"] = loc_id

    try:
        rows = api_get("/api/stock/by-batch", params=bp) or []
    except APIError as e:
        st.error(str(e))
        rows = []

    if rows:
        df = pd.DataFrame([
            {
                "ID": r["material_id"],
                "代码": r["material_code"],
                "物料名称": r["name_cn"],
                "TT分类": material_type_label(r.get("material_type")),
                "入库类型": material_type_label(r.get("intake_type")),
                "生产商": fmt_null(r.get("manufacturer")),
                "规格/型号": fmt_null(r.get("spec_model")),
                "货号": fmt_null(r.get("catalog_no")),
                "单位": r["unit"],
                "批号": r["batch_no"],
                "储存位置": fmt_null(r.get("location_name")),
                "效期": fmt_null(r.get("expiry_date")),
                "剩余天数": r.get("days_to_expiry") if r.get("days_to_expiry") is not None else "-",
                "到货日期": r["received_date"],
                "当前库存": r["current_qty"],
                "状态": "在用" if r["is_active"] else "已停用",
            }
            for r in rows
        ])
        st.dataframe(df, use_container_width=True, height=520)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="库存-批次")
        st.download_button("⬇️ 导出 Excel", data=buf.getvalue(),
                           file_name="库存_按批次明细.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("无数据")
