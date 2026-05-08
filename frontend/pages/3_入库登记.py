"""
文件: frontend/pages/3_入库登记.py
用途: 入库登记页 — 三级联(分类→搜索→选物料),自动判断"新建批次"或"追加入库"
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import streamlit as st

from utils import (
    api_get, api_post, APIError,
    get_categories, get_locations, get_materials, material_label,
    clear_material_cache,
)

st.set_page_config(page_title="入库登记", page_icon="📥", layout="wide")
st.header("📥 入库登记")

# ---- 1) 物料选择(三级联) ----
materials = get_materials(active_only=True)
categories = get_categories()

c1, c2 = st.columns([1, 3])
with c1:
    cat = st.selectbox("分类筛选", ["(全部)"] + categories)
with c2:
    keyword = st.text_input("代码 / 名称 关键字", "")

filtered = [
    m for m in materials
    if (cat == "(全部)" or m.get("category") == cat)
       and (
           not keyword
           or keyword.lower() in m["material_code"].lower()
           or keyword.lower() in m["name_cn"].lower()
       )
]

if not filtered:
    st.warning("没有匹配的在用物料。请确认主数据已导入或调整筛选条件。")
    st.stop()

opt_map = {material_label(m): m for m in filtered}
sel = st.selectbox("选择物料", list(opt_map.keys()))
mat = opt_map[sel]

st.info(
    f"**{mat['material_code']} {mat['name_cn']}** | 单位: `{mat['unit']}` | "
    f"规格: {mat.get('spec_model') or '-'} | 生产商: {mat.get('manufacturer') or '-'}"
)

# ---- 2) 入库表单 ----
st.markdown("---")
st.subheader("入库信息")

with st.form("in_form", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        batch_no = st.text_input("供应商批号 *", max_chars=100)
        received = st.date_input("到货日期 *", value=date.today())
        qty = st.number_input(f"入库数量 ({mat['unit']}) *", min_value=0.01, step=1.0, value=1.0)
        operator = st.text_input("经办人 *", max_chars=50)
    with col2:
        # 效期
        has_expiry = st.checkbox("此批次有效期", value=True)
        expiry = st.date_input("效期", value=date.today()) if has_expiry else None

        # 储存位置
        locs = get_locations()
        loc_map = {l["name"]: l["location_id"] for l in locs}
        loc_name = st.selectbox("储存位置", ["(暂不指定)"] + list(loc_map.keys()))
        loc_id = loc_map.get(loc_name) if loc_name != "(暂不指定)" else None

        remark = st.text_area("备注", max_chars=500, height=80)

    submitted = st.form_submit_button("✅ 提交入库", type="primary")

if submitted:
    if not batch_no or not operator or qty <= 0:
        st.error("批号 / 经办人 / 数量为必填且数量必须 > 0")
    else:
        # 先查同物料同批号是否已存在
        existing = None
        try:
            batches = api_get("/api/batches", params={"material_code": mat["material_code"]}) or []
            existing = next((b for b in batches if b["batch_no"] == batch_no), None)
        except APIError as e:
            st.error(f"查询批次失败: {e}")
            st.stop()

        if existing:
            # 追加入库
            st.warning(
                f"批号 `{batch_no}` 已存在(批次 ID={existing['batch_id']},"
                f"当前库存 {existing.get('current_qty')}{mat['unit']}),"
                f"将作为**追加入库**记录。"
            )
            if st.session_state.get("__confirm_append__") != batch_no:
                st.session_state["__confirm_append__"] = batch_no
                st.button("👉 确认追加入库", key="confirm_append_btn")
            else:
                try:
                    api_post("/api/inventory/in", json={
                        "batch_id": existing["batch_id"],
                        "qty": str(Decimal(str(qty))),
                        "txn_date": str(received),
                        "operator": operator,
                        "remark": remark or None,
                    })
                    st.success(f"追加入库成功!批次 {batch_no} 当前库存已更新")
                    st.session_state.pop("__confirm_append__", None)
                except APIError as e:
                    st.error(f"追加入库失败: {e}")
        else:
            # 新建批次
            try:
                payload = {
                    "material_code": mat["material_code"],
                    "batch_no": batch_no,
                    "expiry_date": str(expiry) if expiry else None,
                    "location_id": loc_id,
                    "received_date": str(received),
                    "initial_qty": str(Decimal(str(qty))),
                    "operator": operator,
                    "remark": remark or None,
                }
                created = api_post("/api/batches", json=payload)
                st.success(
                    f"入库成功!批次 ID={created['batch_id']},"
                    f"当前库存 {created.get('current_qty')}{mat['unit']}"
                )
            except APIError as e:
                st.error(f"入库失败: {e}")

# ---- 3) 该物料现有批次列表 ----
st.markdown("---")
st.subheader(f"📋 {mat['name_cn']} 的现有批次")
try:
    cur = api_get("/api/batches", params={"material_code": mat["material_code"]}) or []
    if cur:
        import pandas as pd
        df = pd.DataFrame([
            {
                "批次ID": b["batch_id"],
                "批号": b["batch_no"],
                "效期": b.get("expiry_date") or "-",
                "到货日期": b.get("received_date"),
                "首入数量": b.get("initial_qty"),
                "当前库存": b.get("current_qty"),
                "储存位置": b.get("location_name") or "-",
            }
            for b in cur
        ])
        st.dataframe(df, use_container_width=True, height=260)
    else:
        st.caption("该物料暂无批次")
except APIError as e:
    st.error(str(e))
