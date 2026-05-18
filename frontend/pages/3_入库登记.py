"""
文件: frontend/pages/3_入库登记.py
用途: 入库登记页 — 物料选择 + 三级联位置(房间/柜号/层)+
      自动判断"新建批次(新位置)"或"追加入库(同三键)"
v1.2:
    - 物料用 material_id;'TT内部物料' 多条共存通过 [#id] 区分
    - 位置必填,UI 拆为 房间→柜号→层 三级联
    - 三键 (material_id, batch_no, location_id) 命中 → 追加
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import streamlit as st

from utils import (
    api_get, api_post, APIError,
    get_categories, get_locations, get_materials, material_label,
    clear_material_cache, fuzzy_match_material,
    locations_grouped,
)
from auth_helper import require_admin, get_user

require_admin()
st.header("📥 入库登记")
_user = get_user()
operator = _user["username"] if _user else ""
st.caption(f"经办人(登录用户):**{operator}**")

# ---- 1) 物料选择 ----
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
       and fuzzy_match_material(m, keyword)
]

if not filtered:
    st.warning("没有匹配的在用物料。请确认主数据已导入或调整筛选条件。")
    st.stop()

opt_map = {material_label(m): m for m in filtered}
sel = st.selectbox("选择物料", list(opt_map.keys()))
mat = opt_map[sel]
mat_id = mat["material_id"]

hz = "、".join(mat.get("hazard_class") or [])
st.info(
    f"**{mat['material_code']} {mat['name_cn']}** | 单位: `{mat['unit']}` | "
    f"规格: {mat.get('spec_model') or '-'} | 生产商: {mat.get('manufacturer') or '-'}"
    + (f" | ⚠️ 危化品: {hz}" if hz else "")
)

# ---- 2) 入库表单 ----
st.markdown("---")
st.subheader("入库信息")

locs = get_locations()
if not locs:
    st.error("位置字典为空,无法入库。请管理员先到 API 或后端建表初始化位置。")
    st.stop()
grouped = locations_grouped(locs)

# 三级联在 form 外:Streamlit form 内 selectbox 不会即时联动
loc_c1, loc_c2, loc_c3 = st.columns(3)
with loc_c1:
    room = st.selectbox("房间编号 *", sorted(grouped.keys()),
                        key="in_room")
with loc_c2:
    cabinets = sorted(grouped.get(room, {}).keys())
    cabinet = st.selectbox("储存柜号 *", cabinets, key="in_cabinet") if cabinets else None
with loc_c3:
    layers = grouped.get(room, {}).get(cabinet, []) if cabinet else []
    layer_opts = {f"L{l['layer_no']}": l for l in layers}
    layer_label = st.selectbox("板层编号 *", list(layer_opts.keys()), key="in_layer") \
        if layer_opts else None
selected_loc = layer_opts.get(layer_label) if layer_label else None
loc_id = selected_loc["location_id"] if selected_loc else None
if selected_loc and selected_loc.get("storage_condition"):
    st.caption(f"该位置储存条件: {selected_loc['storage_condition']}")

with st.form("in_form", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        batch_no = st.text_input("供应商批号 *", max_chars=100)
        received = st.date_input("到货日期 *", value=date.today())
        qty = st.number_input(f"入库数量 ({mat['unit']}) *", min_value=0.01,
                              step=1.0, value=1.0)
    with col2:
        has_expiry = st.checkbox("此批次有效期", value=True)
        expiry = st.date_input("效期", value=date.today()) if has_expiry else None
        remark = st.text_area("备注", max_chars=500, height=80)

    submitted = st.form_submit_button("✅ 提交入库", type="primary")

if submitted:
    if not batch_no or qty <= 0:
        st.error("批号必填,数量必须 > 0")
    elif loc_id is None:
        st.error("请选择储存位置(房间 / 柜号 / 层)")
    else:
        # 三键命中检测:取该物料所有批次,过滤同批号同位置
        existing = None
        try:
            batches = api_get("/api/batches",
                              params={"material_id": mat_id}) or []
            existing = next(
                (b for b in batches
                 if b["batch_no"] == batch_no and b["location_id"] == loc_id),
                None,
            )
        except APIError as e:
            st.error(f"查询批次失败: {e}")
            st.stop()

        if existing:
            # 命中 → 缓存到 session_state,在 form 外渲染确认按钮
            st.session_state["__pending_append__"] = {
                "material_id": mat_id,
                "unit": mat["unit"],
                "batch_id": existing["batch_id"],
                "batch_no": batch_no,
                "location_name": existing.get("location_name") or "?",
                "current_qty": str(existing.get("current_qty") or 0),
                "qty": str(Decimal(str(qty))),
                "txn_date": str(received),
                "remark": remark or None,
            }
        else:
            # 新建批次(可能与同 batch_no 但不同 location 的批次共存)
            try:
                payload = {
                    "material_id": mat_id,
                    "batch_no": batch_no,
                    "expiry_date": str(expiry) if expiry else None,
                    "location_id": loc_id,
                    "received_date": str(received),
                    "initial_qty": str(Decimal(str(qty))),
                    "remark": remark or None,
                }
                created = api_post("/api/batches", json=payload)
                st.success(
                    f"入库成功!批次 ID={created['batch_id']}(位置 "
                    f"{created.get('location_name')}),当前库存 "
                    f"{created.get('current_qty')}{mat['unit']}"
                )
            except APIError as e:
                st.error(f"入库失败: {e}")

# ---- 追加入库的二次确认 ----
pending = st.session_state.get("__pending_append__")
if pending and pending["material_id"] == mat_id:
    st.warning(
        f"批号 `{pending['batch_no']}` 在位置 **{pending['location_name']}** "
        f"已存在(批次 ID={pending['batch_id']},"
        f"当前库存 {pending['current_qty']}{pending['unit']}),"
        f"本次将作为**追加入库**记录(创建新流水,不新建批次)。"
    )
    cc1, cc2 = st.columns([1, 1])
    if cc1.button("✅ 确认追加入库", key="confirm_append_btn", type="primary"):
        try:
            api_post("/api/inventory/in", json={
                "batch_id": pending["batch_id"],
                "qty": pending["qty"],
                "txn_date": pending["txn_date"],
                "remark": pending["remark"],
            })
            st.success(f"追加入库成功!批次 {pending['batch_no']} 当前库存已更新")
            st.session_state.pop("__pending_append__", None)
            st.rerun()
        except APIError as e:
            st.error(f"追加入库失败: {e}")
    if cc2.button("取消", key="cancel_append_btn"):
        st.session_state.pop("__pending_append__", None)
        st.rerun()

# ---- 3) 该物料现有批次列表 ----
st.markdown("---")
st.subheader(f"📋 {mat['name_cn']} 的现有批次")
try:
    cur = api_get("/api/batches", params={"material_id": mat_id}) or []
    if cur:
        import pandas as pd
        df = pd.DataFrame([
            {
                "批次ID": b["batch_id"],
                "批号": b["batch_no"],
                "储存位置": b.get("location_name") or "-",
                "效期": b.get("expiry_date") or "-",
                "到货日期": b.get("received_date"),
                "首入数量": b.get("initial_qty"),
                "当前库存": b.get("current_qty"),
            }
            for b in cur
        ])
        st.dataframe(df, use_container_width=True, height=260)
    else:
        st.caption("该物料暂无批次")
except APIError as e:
    st.error(str(e))
