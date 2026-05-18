"""
文件: frontend/views/9_移库.py
用途: 在不变批号的前提下,把某批次的全部 / 部分库存搬到另一位置。
语义:
    - 同物料同批号,源位置出 N → 目的位置入 N(一笔原子操作)
    - 目的位置若已有同批号 batch → 追加流水;否则按源 batch 的
      expiry/received_date 自动建一条新 batch 行
    - 后端审计落一条 inventory.transfer
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import streamlit as st

from utils import (
    api_get, api_post, APIError,
    get_categories, get_locations, get_materials, material_label,
    fuzzy_match_material, locations_grouped, render_hazard_badges,
)
from auth_helper import require_admin, get_user

require_admin()
st.header("🚚 移库")
st.caption("同批号在不同位置间搬运(批号链不断);支持部分移。")
_user = get_user()
operator = _user["username"] if _user else ""
st.caption(f"经办人(登录用户):**{operator}**")

# ---- 1) 物料选择 ----
materials = get_materials(active_only=True)
categories = get_categories()


@st.cache_data(ttl=30, show_spinner=False)
def _batch_index() -> dict:
    """{material_id: [batch_no...]} —— 支持按批号搜物料。"""
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
        help="一个框搜三种;输入批号能定位到对应物料",
    )

bidx = _batch_index()
filtered = [
    m for m in materials
    if (cat == "(全部)" or m.get("category") == cat)
       and fuzzy_match_material(m, keyword, extra_haystack=bidx.get(m["material_id"]))
]
if not filtered:
    st.warning("没有匹配的在用物料。")
    st.stop()

opt_map = {material_label(m): m for m in filtered}
sel = st.selectbox("选择物料", list(opt_map.keys()))
mat = opt_map[sel]
mat_id = mat["material_id"]

st.info(
    f"**{mat['material_code']} {mat['name_cn']}** | 单位: `{mat['unit']}` | "
    f"规格: {mat.get('spec_model') or '-'}"
)
render_hazard_badges(mat.get("hazard_class"))

# ---- 2) 源批次(只列有库存的) ----
st.markdown("---")
st.subheader("源批次(从哪里搬)")
try:
    batches = api_get("/api/batches", params={
        "material_id": mat_id,
        "only_with_stock": "true",
        "include_expired": "true",   # 移库可能就是为了清理过期
    }) or []
except APIError as e:
    st.error(str(e))
    batches = []

if not batches:
    st.warning("该物料没有库存 > 0 的批次,没什么可搬。")
    st.stop()


def _src_label(b):
    expiry = b.get("expiry_date") or "无效期"
    loc = b.get("location_name") or "?"
    return (f"{loc} | 批号 {b['batch_no']} | 效期 {expiry} | "
            f"当前 {b.get('current_qty')}{mat['unit']} | 批次{b['batch_id']}")


src_map = {_src_label(b): b for b in batches}
src_label = st.selectbox("源批次", list(src_map.keys()))
src = src_map[src_label]
src_qty = Decimal(str(src.get("current_qty") or 0))

# ---- 3) 目的位置(三级联,排除源位置)----
st.markdown("---")
st.subheader("目的位置(搬到哪里)")
locs = get_locations()
grouped = locations_grouped(locs)
rooms_sorted = sorted(grouped.keys())

dc1, dc2, dc3 = st.columns(3)
with dc1:
    room = st.selectbox("房间编号 *", rooms_sorted, key="mv_room")
with dc2:
    cabs = sorted(grouped.get(room, {}).keys())
    cab = st.selectbox("储存柜号 *", cabs, key="mv_cab") if cabs else None
with dc3:
    layers = grouped.get(room, {}).get(cab, []) if cab else []
    layer_opts = {f"L{l['layer_no']}": l for l in layers}
    layer_lbl = st.selectbox("板层编号 *", list(layer_opts.keys()), key="mv_layer") \
        if layer_opts else None
dest_loc = layer_opts.get(layer_lbl) if layer_lbl else None
dest_loc_id = dest_loc["location_id"] if dest_loc else None

if dest_loc and dest_loc_id == src["location_id"]:
    st.error("⚠️ 目的位置与源位置相同,无需移库")
elif dest_loc:
    st.caption(
        f"将搬到:**{dest_loc['name']}**" +
        (f"(储存条件: {dest_loc['storage_condition']})" if dest_loc.get("storage_condition") else "")
    )

# ---- 4) 移库表单 ----
with st.form("transfer_form", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        qty = st.number_input(
            f"移库数量 ({mat['unit']}) *",
            min_value=0.01, step=1.0,
            value=float(src_qty),  # 默认全搬
            max_value=float(src_qty),
        )
        txn_date = st.date_input("移库日期 *", value=date.today())
    with col2:
        remark = st.text_area("备注(可填原因,如「冷藏需要 / 整柜清空」)", height=80)

    submitted = st.form_submit_button("🚚 提交移库", type="primary")

if submitted:
    if dest_loc_id is None:
        st.error("请选完整的目的位置")
    elif dest_loc_id == src["location_id"]:
        st.error("目的位置不能与源位置相同")
    elif Decimal(str(qty)) <= 0:
        st.error("数量必须 > 0")
    elif Decimal(str(qty)) > src_qty:
        st.error(f"超过源批次当前库存 {src_qty}{mat['unit']}")
    else:
        try:
            api_post("/api/inventory/transfer", json={
                "source_batch_id": src["batch_id"],
                "dest_location_id": dest_loc_id,
                "qty": str(Decimal(str(qty))),
                "txn_date": str(txn_date),
                "remark": remark or None,
            })
            full = Decimal(str(qty)) == src_qty
            st.success(
                f"✅ 移库成功!{src.get('location_name')} → {dest_loc['name']},"
                f"{qty}{mat['unit']}({'全部移完' if full else '部分移'})"
            )
            st.balloons()
            # 清缓存让后面的下拉刷新
            st.cache_data.clear()
        except APIError as e:
            st.error(f"移库失败: {e}")

# ---- 5) 该物料近期流水 ----
st.markdown("---")
st.subheader(f"📜 {mat['name_cn']} 近期流水(最近 50 条)")
try:
    import pandas as pd
    txns = api_get("/api/inventory/txns",
                   params={"material_id": mat_id, "limit": 50}) or []
    if txns:
        df = pd.DataFrame([
            {
                "时间": t["created_at"],
                "类型": t["txn_type"],
                "批号": t.get("batch_no"),
                "位置": t.get("location_name") or "-",
                "数量": t["qty"],
                "用途/备注": t.get("purpose") or t.get("remark") or "-",
                "经办人": t["operator"],
            }
            for t in txns
        ])
        st.dataframe(df, use_container_width=True, height=300)
    else:
        st.caption("暂无流水")
except APIError as e:
    st.error(str(e))
