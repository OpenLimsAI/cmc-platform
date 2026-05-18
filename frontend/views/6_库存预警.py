"""
文件: frontend/pages/6_库存预警.py
用途: 库存预警 — 三个 Tab(已过期+紧急 / 临近过期 / 低库存),支持导出 Excel
预警规则:
    - EXPIRED: expiry_date < 今天
    - URGENT:  0 ≤ expiry - 今天 ≤ 30
    - WARNING: 30 < expiry - 今天 ≤ 90
    - LOW:     物料总库存 < 安全库存 且 安全库存 > 0
"""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from utils import api_get, APIError, fmt_null
from auth_helper import require_login

require_login()
st.header("⚠️ 库存预警")

tab1, tab2, tab3 = st.tabs(["🔴 已过期 / 紧急(≤30天)", "🟡 临近过期(30-90天)", "🟡 低库存"])


def _to_excel_bytes(df: pd.DataFrame, sheet: str) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name=sheet)
    return buf.getvalue()


# -------- Tab 1: 已过期 + 紧急 --------
with tab1:
    try:
        alerts = api_get("/api/stock/alerts/expiry", params={"days": 30}) or []
    except APIError as e:
        st.error(str(e))
        alerts = []
    # 后端返回时已包含 EXPIRED + URGENT + WARNING(≤days),这里再过滤
    rows = [a for a in alerts if a["severity"] in ("EXPIRED", "URGENT")]
    st.caption(f"共 {len(rows)} 条")
    if rows:
        df = pd.DataFrame([
            {
                "严重度": "已过期" if a["severity"] == "EXPIRED" else "紧急(≤30天)",
                "ID": a["material_id"],
                "代码": a["material_code"],
                "物料": a["name_cn"],
                "批号": a["batch_no"],
                "效期": a["expiry_date"],
                "剩余天数": a["days_to_expiry"],
                "当前库存": a["current_qty"],
                "单位": a["unit"],
                "储存位置": fmt_null(a.get("location_name")),
            }
            for a in rows
        ])
        st.dataframe(df, use_container_width=True, height=400)
        st.download_button("⬇️ 导出 Excel", _to_excel_bytes(df, "已过期+紧急"),
                           file_name="预警_已过期紧急.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.success("无该类预警 ✅")

# -------- Tab 2: 临近过期(30-90 天) --------
with tab2:
    try:
        alerts = api_get("/api/stock/alerts/expiry", params={"days": 90}) or []
    except APIError as e:
        st.error(str(e))
        alerts = []
    rows = [a for a in alerts if a["severity"] == "WARNING"]
    st.caption(f"共 {len(rows)} 条")
    if rows:
        df = pd.DataFrame([
            {
                "ID": a["material_id"],
                "代码": a["material_code"],
                "物料": a["name_cn"],
                "批号": a["batch_no"],
                "效期": a["expiry_date"],
                "剩余天数": a["days_to_expiry"],
                "当前库存": a["current_qty"],
                "单位": a["unit"],
                "储存位置": fmt_null(a.get("location_name")),
            }
            for a in rows
        ])
        st.dataframe(df, use_container_width=True, height=400)
        st.download_button("⬇️ 导出 Excel", _to_excel_bytes(df, "临近过期"),
                           file_name="预警_临近过期.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.success("无该类预警 ✅")

# -------- Tab 3: 低库存 --------
with tab3:
    try:
        alerts = api_get("/api/stock/alerts/low-stock") or []
    except APIError as e:
        st.error(str(e))
        alerts = []
    st.caption(f"共 {len(alerts)} 条")
    if alerts:
        df = pd.DataFrame([
            {
                "ID": a["material_id"],
                "代码": a["material_code"],
                "物料": a["name_cn"],
                "单位": a["unit"],
                "当前库存": a["total_qty"],
                "安全库存": a["safety_stock"],
                "缺口": a["gap"],
            }
            for a in alerts
        ])
        st.dataframe(df, use_container_width=True, height=400)
        st.download_button("⬇️ 导出 Excel", _to_excel_bytes(df, "低库存"),
                           file_name="预警_低库存.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.success("无该类预警 ✅")
