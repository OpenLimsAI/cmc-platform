"""
文件: frontend/pages/4_出库登记.py
用途: 出库登记 — 仅显示有库存物料,默认按效期升序(FIFO)
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

from utils import (
    api_get, api_post, APIError,
    get_categories, get_materials, material_label, fuzzy_match_material,
)
from auth_helper import require_admin, get_user

st.set_page_config(page_title="出库登记", page_icon="📤", layout="wide")
require_admin()
st.header("📤 出库登记")
_user = get_user()
operator = _user["username"] if _user else ""
st.caption(f"经办人(登录用户):**{operator}**")

# ---- 1) 加载有库存的物料 ----
try:
    stock_rows = api_get("/api/stock/by-material") or []
except APIError as e:
    st.error(f"加载库存失败: {e}")
    stock_rows = []

stock_codes = {s["material_code"]: s for s in stock_rows if float(s.get("total_qty") or 0) > 0}

if not stock_codes:
    st.warning("当前无任何库存可出库。请先到「入库登记」页录入批次。")
    st.stop()

# 与物料字典 join,带分类信息
materials = get_materials(active_only=True)
mat_dict = {m["material_code"]: m for m in materials}
choices = []
for code, s in stock_codes.items():
    m = mat_dict.get(code, {})
    choices.append({
        "material_code": code,
        "name_cn": s["name_cn"],
        "category": s.get("category"),
        "unit": s["unit"],
        "spec_model": m.get("spec_model"),
        "manufacturer": m.get("manufacturer"),
        "total_qty": s["total_qty"],
    })

categories = get_categories()
c1, c2 = st.columns([1, 3])
with c1:
    cat = st.selectbox("分类筛选", ["(全部)"] + categories)
with c2:
    keyword = st.text_input("代码 / 名称 关键字", "")

filtered = [
    m for m in choices
    if (cat == "(全部)" or m.get("category") == cat)
       and fuzzy_match_material(m, keyword)
]
if not filtered:
    st.info("无匹配物料")
    st.stop()

opt_map = {material_label(m) + f" | 总库存 {m['total_qty']}{m['unit']}": m for m in filtered}
sel = st.selectbox("选择物料", list(opt_map.keys()))
mat = opt_map[sel]

# ---- 2) 加载该物料的批次 ----
include_expired = st.checkbox("显示已过期批次", value=False)
try:
    batches = api_get("/api/batches", params={
        "material_code": mat["material_code"],
        "only_with_stock": "true",
        "include_expired": str(include_expired).lower(),
    }) or []
except APIError as e:
    st.error(str(e))
    batches = []

if not batches:
    st.warning("该物料无可用批次(全部过期或库存为 0)。可勾选『显示已过期批次』后重试。")
    st.stop()

# 按效期升序展示(后端已默认排序),给出选项
def _label(b):
    expiry = b.get("expiry_date") or "无效期"
    loc = b.get("location_name") or "未指定"
    return (f"批次{b['batch_id']} | 批号 {b['batch_no']} | 效期 {expiry} | "
            f"位置 {loc} | 当前 {b.get('current_qty')}{mat['unit']}")

batch_map = {_label(b): b for b in batches}
batch_label = st.selectbox("选择批次(默认效期升序 - FIFO 建议)", list(batch_map.keys()))
b = batch_map[batch_label]

st.info(
    f"批次 **{b['batch_no']}**: 当前库存 `{b.get('current_qty')}{mat['unit']}`,"
    f"效期 `{b.get('expiry_date') or '-'}`"
)

# ---- 3) 出库表单 ----
st.markdown("---")
with st.form("out_form"):
    col1, col2 = st.columns(2)
    with col1:
        qty = st.number_input(
            f"出库数量 ({mat['unit']}) *", min_value=0.01, step=1.0, value=1.0,
            max_value=float(b.get("current_qty") or 0),
        )
        txn_date = st.date_input("出库日期 *", value=date.today())
    with col2:
        purpose = st.text_input("用途 / 项目编号", max_chars=200)
        remark = st.text_area("备注", height=80)

    submitted = st.form_submit_button("✅ 确认出库", type="primary")

if submitted:
    if qty <= 0:
        st.error("出库数量必须 > 0")
    elif Decimal(str(qty)) > Decimal(str(b.get("current_qty") or 0)):
        st.error(f"出库数量超过批次现有库存 {b.get('current_qty')}{mat['unit']}")
    else:
        try:
            api_post("/api/inventory/out", json={
                "batch_id": b["batch_id"],
                "qty": str(Decimal(str(qty))),
                "txn_date": str(txn_date),
                "purpose": purpose or None,
                "remark": remark or None,
            })
            st.success(f"出库成功!已扣减 {qty}{mat['unit']}")
            st.rerun()
        except APIError as e:
            st.error(f"出库失败: {e}")

# ---- 4) 该物料近期流水 ----
st.markdown("---")
st.subheader("📜 近期流水(本物料,最近 50 条)")
try:
    txns = api_get("/api/inventory/txns",
                   params={"material_code": mat["material_code"], "limit": 50}) or []
    if txns:
        df = pd.DataFrame([
            {
                "时间": t["created_at"],
                "类型": t["txn_type"],
                "批号": t.get("batch_no"),
                "数量": t["qty"],
                "经办人": t["operator"],
                "用途": t.get("purpose") or "-",
                "备注": t.get("remark") or "-",
            }
            for t in txns
        ])
        st.dataframe(df, use_container_width=True, height=300)
    else:
        st.caption("暂无流水")
except APIError as e:
    st.error(str(e))
