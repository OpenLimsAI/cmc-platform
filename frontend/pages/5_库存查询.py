"""
文件: frontend/pages/5_库存查询.py
用途: 库存查询(物料汇总 / 批次明细),支持导出 Excel
"""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from utils import api_get, APIError, get_categories, get_locations, fmt_null
from auth_helper import require_login

require_login()
st.header("📊 库存查询")

view = st.radio("查看维度", ["按物料汇总", "按批次明细"], horizontal=True)

categories = get_categories()
locations = get_locations()
loc_map = {"(全部位置)": None, **{l["name"]: l["location_id"] for l in locations}}

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    cat = st.selectbox("分类", ["(全部分类)"] + categories)
with c2:
    keyword = st.text_input("代码 / 名称")
with c3:
    inc_inactive = st.checkbox("含已停用", value=False)
with c4:
    inc_expired = st.checkbox("含已过期(批次)", value=False)
with c5:
    # 默认排除零库存:用户日常视图。勾选后包含 0 库存物料/批次,看完整目录
    inc_zero = st.checkbox("含零库存", value=False)
with c6:
    loc_name = st.selectbox("储存位置(批次)", list(loc_map.keys()))

params = {}
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
                "代码": r["material_code"],
                "物料名称": r["name_cn"],
                "分类": fmt_null(r.get("category")),
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
    if loc_map.get(loc_name) is not None:
        bp["location_id"] = loc_map[loc_name]

    try:
        rows = api_get("/api/stock/by-batch", params=bp) or []
    except APIError as e:
        st.error(str(e))
        rows = []

    if rows:
        df = pd.DataFrame([
            {
                "代码": r["material_code"],
                "物料名称": r["name_cn"],
                "单位": r["unit"],
                "批号": r["batch_no"],
                "效期": fmt_null(r.get("expiry_date")),
                "剩余天数": r.get("days_to_expiry") if r.get("days_to_expiry") is not None else "-",
                "到货日期": r["received_date"],
                "当前库存": r["current_qty"],
                "储存位置": fmt_null(r.get("location_name")),
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
