"""
文件: frontend/views/3_入库登记.py
用途: 入库登记页 — 物料选择 + 多位置批量录入(同批号散放多柜)
v1.2:
    - 物料用 material_id;'TT内部物料' 多条共存通过 [#id] 区分
    - 位置必填,UI 拆为 房间→柜号→层 三级联
    - 三键 (material_id, batch_no, location_id) 命中 → 追加流水;否则新建批次
v1.2.x:
    - 位置行支持 ➕ 增加 / ✖ 删除,一次到货可一次性录入多个位置
      (例:批号 A 在 A01-L1 放 20 瓶 + 在 C02-L4 放 15 瓶)
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import streamlit as st

from utils import (
    api_get, api_post, APIError,
    get_categories, get_locations, get_materials, material_label,
    fuzzy_match_material,
    locations_grouped, render_hazard_badges,
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

st.info(
    f"**{mat['material_code']} {mat['name_cn']}** | 单位: `{mat['unit']}` | "
    f"规格: {mat.get('spec_model') or '-'} | 生产商: {mat.get('manufacturer') or '-'}"
)
render_hazard_badges(mat.get("hazard_class"))

# ---- 2) 入库表单 ----
st.markdown("---")
st.subheader("入库信息")

locs = get_locations()
if not locs:
    st.error("位置字典为空,无法入库。请管理员先到 API 或后端建表初始化位置。")
    st.stop()
grouped = locations_grouped(locs)
rooms_sorted = sorted(grouped.keys())

# ── 多位置行(可加可删)─────────────────────────────────────────────
# 用 UUID key 保证删行后不会读到旧 widget state
# 切换物料时重置位置行,避免不同物料间状态串台
if st.session_state.get("__in_for_mat__") != mat_id:
    st.session_state["__in_for_mat__"] = mat_id
    st.session_state["in_loc_rows"] = [{"rid": str(uuid.uuid4())}]

st.markdown("##### 存放位置(可多行 — 同批号在不同位置各自计数)")

remove_idx = None  # 推迟删除,避免在循环中改变列表
for idx, row in enumerate(st.session_state["in_loc_rows"]):
    rid = row["rid"]
    cols = st.columns([2, 2, 2, 2, 1, 1])
    with cols[0]:
        room = st.selectbox(
            "房间编号 *", rooms_sorted, key=f"in_room_{rid}",
            label_visibility="visible" if idx == 0 else "collapsed",
        )
    with cols[1]:
        cabs = sorted(grouped.get(room, {}).keys())
        cab = st.selectbox(
            "储存柜号 *", cabs, key=f"in_cab_{rid}",
            label_visibility="visible" if idx == 0 else "collapsed",
        ) if cabs else None
    with cols[2]:
        layers = grouped.get(room, {}).get(cab, []) if cab else []
        layer_opts = {f"L{l['layer_no']}": l for l in layers}
        layer_lbl = st.selectbox(
            "板层编号 *", list(layer_opts.keys()), key=f"in_layer_{rid}",
            label_visibility="visible" if idx == 0 else "collapsed",
        ) if layer_opts else None
    with cols[3]:
        qty = st.number_input(
            f"数量 ({mat['unit']}) *", min_value=0.01, step=1.0, value=1.0,
            key=f"in_qty_{rid}",
            label_visibility="visible" if idx == 0 else "collapsed",
        )
    sel_loc = layer_opts.get(layer_lbl) if layer_lbl else None
    with cols[4]:
        # 顶部按钮要跟下拉对齐,留点上间距
        if idx == 0:
            st.markdown('<div style="height:27px"></div>', unsafe_allow_html=True)
        if st.button("➕", key=f"in_add_{rid}", help="增加一个位置"):
            st.session_state["in_loc_rows"].append({"rid": str(uuid.uuid4())})
            st.rerun()
    with cols[5]:
        if idx == 0:
            st.markdown('<div style="height:27px"></div>', unsafe_allow_html=True)
        if len(st.session_state["in_loc_rows"]) > 1:
            if st.button("✖", key=f"in_rm_{rid}", help="删除此行"):
                remove_idx = idx

    # 暂存到 row,提交时统一取
    row["loc_id"] = sel_loc["location_id"] if sel_loc else None
    row["loc_name"] = sel_loc["name"] if sel_loc else None
    row["qty"] = Decimal(str(qty))
    if sel_loc and sel_loc.get("storage_condition"):
        cols[0].caption(f"💡 该位置储存条件: {sel_loc['storage_condition']}")

if remove_idx is not None:
    st.session_state["in_loc_rows"].pop(remove_idx)
    st.rerun()

# ── 全局字段(批号 / 到货日期 / 效期 / 备注)──────────────────────────
with st.form("in_form", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        batch_no = st.text_input("供应商批号 *", max_chars=100)
        received = st.date_input("到货日期 *", value=date.today())
    with col2:
        has_expiry = st.checkbox("此批次有效期", value=True)
        expiry = st.date_input("效期", value=date.today()) if has_expiry else None
        remark = st.text_area("备注", max_chars=500, height=80)

    submitted = st.form_submit_button("✅ 提交入库(全部位置)", type="primary")


def _process_one(loc_id: int, loc_name: str, qty: Decimal,
                 batches_cache: list) -> tuple[str, str]:
    """处理一行:返回 (状态 'ok'|'fail', 文案)。"""
    existing = next(
        (b for b in batches_cache
         if b["batch_no"] == batch_no and b["location_id"] == loc_id),
        None,
    )
    try:
        if existing:
            api_post("/api/inventory/in", json={
                "batch_id": existing["batch_id"],
                "qty": str(qty),
                "txn_date": str(received),
                "remark": remark or None,
            })
            return "ok", (f"📥 追加流水:{loc_name} | 批次 {existing['batch_id']} "
                          f"+{qty}{mat['unit']}(原 {existing.get('current_qty')})")
        api_post("/api/batches", json={
            "material_id": mat_id,
            "batch_no": batch_no,
            "expiry_date": str(expiry) if expiry else None,
            "location_id": loc_id,
            "received_date": str(received),
            "initial_qty": str(qty),
            "remark": remark or None,
        })
        return "ok", f"🆕 新建批次:{loc_name} | 批号 {batch_no} | {qty}{mat['unit']}"
    except APIError as e:
        return "fail", f"❌ {loc_name}:{e}"


if submitted:
    # 校验
    rows = st.session_state["in_loc_rows"]
    errors = []
    if not batch_no:
        errors.append("供应商批号必填")
    if any(r["loc_id"] is None for r in rows):
        errors.append("每行都必须选完整的房间 / 柜号 / 板层")
    if any(r["qty"] <= 0 for r in rows):
        errors.append("每行数量必须 > 0")
    # 同表中重复位置
    seen_locs = set()
    for r in rows:
        if r["loc_id"] in seen_locs:
            errors.append(f"位置 {r['loc_name']} 在表中重复出现,请合并或删除")
            break
        seen_locs.add(r["loc_id"])

    if errors:
        for e in errors:
            st.error(e)
    else:
        # 一次性拉本物料的现有批次,本地判断每行是 append 还是 new
        try:
            batches_cache = api_get(
                "/api/batches", params={"material_id": mat_id}
            ) or []
        except APIError as e:
            st.error(f"查询现有批次失败: {e}")
            st.stop()

        results = [_process_one(r["loc_id"], r["loc_name"], r["qty"], batches_cache)
                   for r in rows]
        ok_cnt = sum(1 for s, _ in results if s == "ok")
        fail_cnt = len(results) - ok_cnt

        for status, msg in results:
            (st.success if status == "ok" else st.error)(msg)

        if fail_cnt == 0:
            st.balloons()
            # 清空位置行,准备下一次录入
            st.session_state["in_loc_rows"] = [{"rid": str(uuid.uuid4())}]
        else:
            st.warning(f"完成 {ok_cnt} 行,失败 {fail_cnt} 行;失败行未生效。")

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
