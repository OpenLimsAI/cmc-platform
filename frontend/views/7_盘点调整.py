"""
文件: frontend/views/7_盘点调整.py
用途: 盘点调整页 — 把账面库存修正为实际盘点数(可正可负)
关键点:
    - 选物料 → 选批次 → 显示账面库存
    - 用户输入「实际盘点数」,前端自动算出 delta(qty);也允许直接输入正负调整量
    - 后端校验:调整后批次库存不得 < 0
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
from auth_helper import require_inventory_access, get_user

require_inventory_access()
st.header("🧮 盘点调整")
st.caption("把账面库存修正为实际盘点数;调整后批次库存不得 < 0。")
_user = get_user()
operator = _user["username"] if _user else ""
st.caption(f"经办人(登录用户):**{operator}**")

# ---- 1) 物料选择(只显示在用) ----
materials = get_materials(active_only=True)
categories = get_categories()


@st.cache_data(ttl=30, show_spinner=False)
def _batch_index() -> dict:
    """{material_id: [batch_no...]} —— 给"按批号搜物料"用。
    缓存 30 秒,本页/其他页入库后顶多 30s 后看到搜索命中。"""
    try:
        bs = api_get("/api/batches") or []
    except APIError:
        return {}
    idx: dict = {}
    for b in bs:
        idx.setdefault(b["material_id"], []).append(b["batch_no"])
    return idx


c1, c2 = st.columns([1, 3])
with c1:
    cat = st.selectbox("分类筛选", ["(全部)"] + categories)
with c2:
    keyword = st.text_input(
        "代码 / 名称 / 批号", "",
        help="一个框搜三种:物料代码、物料名称、批号",
    )

bidx = _batch_index()
filtered = [
    m for m in materials
    if (cat == "(全部)" or m.get("category") == cat)
       and fuzzy_match_material(m, keyword,
                                extra_haystack=bidx.get(m["material_id"]))
]
if not filtered:
    st.warning("没有匹配的在用物料。")
    st.stop()

opt_map = {material_label(m): m for m in filtered}
sel = st.selectbox("选择物料", list(opt_map.keys()))
mat = opt_map[sel]

# ---- 2) 批次选择(含已过期,盘点经常需要清理过期) ----
include_expired = st.checkbox("包含已过期批次", value=True)
try:
    batches = api_get("/api/batches", params={
        "material_id": mat["material_id"],
        "include_expired": str(include_expired).lower(),
    }) or []
except APIError as e:
    st.error(str(e))
    batches = []

if not batches:
    st.warning("该物料无任何批次,无法调整。请先在「入库登记」录入。")
    st.stop()


def _label(b):
    expiry = b.get("expiry_date") or "无效期"
    loc = b.get("location_name") or "未指定"
    return (f"位置 {loc} | 批号 {b['batch_no']} | 效期 {expiry} | "
            f"账面 {b.get('current_qty')}{mat['unit']} | 批次{b['batch_id']}")


batch_map = {_label(b): b for b in batches}
batch_label = st.selectbox("选择批次", list(batch_map.keys()))
b = batch_map[batch_label]

book_qty = Decimal(str(b.get("current_qty") or 0))
st.info(f"批次 **{b['batch_no']}** 账面库存: `{book_qty}{mat['unit']}`")

# ---- 3) 调整方式:按盘点数 或 按调整量 ----
st.markdown("---")
mode = st.radio("调整方式", ["按实际盘点数(自动算差额)", "按调整量(可正可负)"], horizontal=True)

with st.form("adjust_form"):
    col1, col2 = st.columns(2)
    with col1:
        if mode.startswith("按实际盘点数"):
            actual = st.number_input(
                f"实际盘点数 ({mat['unit']}) *", min_value=0.0, step=1.0,
                value=float(book_qty),
            )
            delta = Decimal(str(actual)) - book_qty
            st.caption(f"将写入调整流水:`{delta}{mat['unit']}` "
                       f"({'增加' if delta > 0 else '减少' if delta < 0 else '无变化'})")
        else:
            delta_in = st.number_input(
                f"调整量 ({mat['unit']},可正可负) *", step=1.0, value=0.0,
            )
            delta = Decimal(str(delta_in))
            new_qty = book_qty + delta
            st.caption(f"调整后账面: `{new_qty}{mat['unit']}`")

        txn_date = st.date_input("调整日期 *", value=date.today())
    with col2:
        remark = st.text_area("备注(建议写盘点单号或原因)", height=120)

    submitted = st.form_submit_button("✅ 提交调整", type="primary")

if submitted:
    if delta == 0:
        st.warning("调整量为 0,无需提交")
    elif book_qty + delta < 0:
        st.error(f"调整后库存为负({book_qty} + {delta} < 0),已拒绝")
    else:
        try:
            api_post("/api/inventory/adjust", json={
                "batch_id": b["batch_id"],
                "qty": str(delta),
                "txn_date": str(txn_date),
                "remark": remark or None,
            })
            st.success(f"调整成功!批次 {b['batch_no']} 已写入调整流水 {delta}{mat['unit']}")
            st.rerun()
        except APIError as e:
            st.error(f"调整失败: {e}")

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
                "备注": t.get("remark") or "-",
            }
            for t in txns
        ])
        st.dataframe(df, use_container_width=True, height=300)
    else:
        st.caption("暂无流水")
except APIError as e:
    st.error(str(e))
