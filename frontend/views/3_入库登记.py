"""
文件: frontend/views/3_入库登记.py
用途: 入库登记 — 按"入库类型"分 4 个 tab(试剂/耗材/标准物质/色谱柱),
       每个 tab 只显示该类型的物料 + 该类型对应的字段。
v1.3:
    - 顶部 st.tabs 切换 4 个类型; 每个 tab 物料下拉只含本类型
    - 试剂 / 耗材: 显示当前总库存(参考)
    - 标准物质: 加"浓度"字段
    - 色谱柱: 加"序列号 / 内部编号 / 负责人"字段
未分类(material_type IS NULL) 的物料不会出现在任何 tab; 需到物料管理设置类型。
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

from utils import (
    api_get, api_post, APIError,
    get_locations, get_materials, material_label,
    fuzzy_match_material,
    locations_grouped, render_hazard_badges,
    MATERIAL_TYPE_LABELS,
)
from auth_helper import require_inventory_access, get_user

require_inventory_access()
st.header("📥 入库登记")
_user = get_user()
operator = _user["username"] if _user else ""
st.caption(f"经办人(登录用户):**{operator}**")

# 4 个 tab; 顺序: 试剂 → 耗材 → 标准物质 → 色谱柱
TYPE_ORDER = ["reagent", "consumable", "standard", "column"]


def _render_intake(mtype: str) -> None:
    """渲染单个类型的入库登记区。所有 widget 和 session_state key 都按 mtype 命名,
    避免 4 个 tab 之间状态串台。"""
    type_label = MATERIAL_TYPE_LABELS[mtype]

    # 物料筛选: 只显示当前类型
    all_materials = get_materials(active_only=True)
    materials = [m for m in all_materials if m.get("material_type") == mtype]

    if not materials:
        st.warning(
            f"还没有任何「{type_label}」类型的物料。\n\n"
            f"请先到「物料管理」把目标物料的入库类型设为「{type_label}」。"
        )
        return

    # 此类型物料下实际出现的 category, 作为二级筛选
    type_cats = sorted({m.get("category") for m in materials if m.get("category")})

    c1, c2 = st.columns([1, 3])
    with c1:
        cat = st.selectbox(
            "分类筛选", ["(全部)"] + list(type_cats),
            key=f"cat_{mtype}",
        )
    with c2:
        keyword = st.text_input(
            "代码 / 名称 关键字", "",
            key=f"kw_{mtype}",
        )

    filtered = [
        m for m in materials
        if (cat == "(全部)" or m.get("category") == cat)
           and fuzzy_match_material(m, keyword)
    ]

    if not filtered:
        st.warning("当前筛选条件下没有匹配的物料,调整筛选试试。")
        return

    opt_map = {material_label(m): m for m in filtered}
    sel = st.selectbox("选择物料", list(opt_map.keys()), key=f"sel_mat_{mtype}")
    mat = opt_map[sel]
    mat_id = mat["material_id"]

    st.info(
        f"**{mat['material_code']} {mat['name_cn']}** | 单位: `{mat['unit']}` | "
        f"规格: {mat.get('spec_model') or '-'} | 厂家: {mat.get('manufacturer') or '-'} | "
        f"货号: {mat.get('catalog_no') or '-'} | 级别: {mat.get('grade') or '-'}"
    )
    render_hazard_badges(mat.get("hazard_class"))

    # 试剂 / 耗材: 显示当前总库存
    if mtype in ("reagent", "consumable"):
        try:
            stock_rows = api_get(
                "/api/stock/by-material",
                params={
                    "keyword": mat["material_code"],
                    "only_positive": "false",
                    "include_inactive": "true",
                },
            ) or []
            cur_total = next(
                (Decimal(str(r["total_qty"])) for r in stock_rows
                 if r.get("material_id") == mat_id),
                Decimal("0"),
            )
            st.success(
                f"📊 当前总库存: **{cur_total} {mat['unit']}** "
                f"(全部位置合计, 排除已过期批次)"
            )
        except APIError:
            pass

    # ── 入库表单 ──────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("入库信息")

    locs = get_locations()
    if not locs:
        st.error("位置字典为空,请管理员先初始化。")
        return
    grouped = locations_grouped(locs)
    rooms_sorted = sorted(grouped.keys())

    # 多位置行: 切换物料时重置
    mat_key = f"__in_for_mat_{mtype}__"
    rows_key = f"in_loc_rows_{mtype}"
    if st.session_state.get(mat_key) != mat_id:
        st.session_state[mat_key] = mat_id
        st.session_state[rows_key] = [{"rid": str(uuid.uuid4())}]

    st.markdown("##### 存放位置(可多行 — 同批号在不同位置各自计数)")

    remove_idx = None  # 推迟删除,避免循环中改变列表
    for idx, row in enumerate(st.session_state[rows_key]):
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
            if idx == 0:
                st.markdown('<div style="height:27px"></div>', unsafe_allow_html=True)
            if st.button("➕", key=f"in_add_{rid}", help="增加一个位置"):
                st.session_state[rows_key].append({"rid": str(uuid.uuid4())})
                st.rerun()
        with cols[5]:
            if idx == 0:
                st.markdown('<div style="height:27px"></div>', unsafe_allow_html=True)
            if len(st.session_state[rows_key]) > 1:
                if st.button("✖", key=f"in_rm_{rid}", help="删除此行"):
                    remove_idx = idx

        row["loc_id"] = sel_loc["location_id"] if sel_loc else None
        row["loc_name"] = sel_loc["name"] if sel_loc else None
        row["qty"] = Decimal(str(qty))
        if sel_loc and sel_loc.get("storage_condition"):
            cols[0].caption(f"💡 该位置储存条件: {sel_loc['storage_condition']}")

    if remove_idx is not None:
        st.session_state[rows_key].pop(remove_idx)
        st.rerun()

    # ── 全局字段(批号/日期/效期/备注 + 类型特定) ─────────────────────
    with st.form(f"in_form_{mtype}", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            batch_no = st.text_input(
                "供应商批号 *", max_chars=100, key=f"in_bno_{mtype}",
            )
            received = st.date_input(
                "到货日期 *", value=date.today(), key=f"in_rec_{mtype}",
            )
        with col2:
            has_expiry = st.checkbox(
                "此批次有效期", value=True, key=f"in_he_{mtype}",
            )
            expiry = st.date_input(
                "效期", value=date.today(), key=f"in_exp_{mtype}",
            ) if has_expiry else None
            remark = st.text_area(
                "备注", max_chars=500, height=80, key=f"in_rmk_{mtype}",
            )

        # 类型特定字段
        type_extras = {
            "concentration": None,
            "serial_no": None,
            "asset_no": None,
            "responsible_person": None,
        }
        if mtype == "standard":
            st.markdown("##### 标准物质专属字段")
            _v = st.text_input(
                "浓度", max_chars=50, help="例如 10 mg/mL",
                key=f"in_conc_{mtype}",
            )
            type_extras["concentration"] = (_v or "").strip() or None
        elif mtype == "column":
            st.markdown("##### 色谱柱专属字段")
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                type_extras["serial_no"] = (
                    st.text_input(
                        "序列号", max_chars=100, help="厂家出厂序列号",
                        key=f"in_sn_{mtype}",
                    ) or ""
                ).strip() or None
            with cc2:
                type_extras["asset_no"] = (
                    st.text_input(
                        "内部编号", max_chars=100, help="本实验室资产编号",
                        key=f"in_an_{mtype}",
                    ) or ""
                ).strip() or None
            with cc3:
                type_extras["responsible_person"] = (
                    st.text_input(
                        "负责人", max_chars=50,
                        key=f"in_rp_{mtype}",
                    ) or ""
                ).strip() or None

        submitted = st.form_submit_button("✅ 提交入库(全部位置)", type="primary")

    if submitted:
        # 校验
        rows = st.session_state[rows_key]
        errors = []
        if not batch_no:
            errors.append("供应商批号必填")
        if any(r["loc_id"] is None for r in rows):
            errors.append("每行都必须选完整的房间 / 柜号 / 板层")
        if any(r["qty"] <= 0 for r in rows):
            errors.append("每行数量必须 > 0")
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
            try:
                batches_cache = api_get(
                    "/api/batches", params={"material_id": mat_id}
                ) or []
            except APIError as e:
                st.error(f"查询现有批次失败: {e}")
                return

            ok_cnt = 0
            fail_cnt = 0
            for r in rows:
                existing = next(
                    (b for b in batches_cache
                     if b["batch_no"] == batch_no and b["location_id"] == r["loc_id"]),
                    None,
                )
                try:
                    if existing:
                        api_post("/api/inventory/in", json={
                            "batch_id": existing["batch_id"],
                            "qty": str(r["qty"]),
                            "txn_date": str(received),
                            "remark": remark or None,
                        })
                        st.success(
                            f"📥 追加流水:{r['loc_name']} | 批次 {existing['batch_id']} "
                            f"+{r['qty']}{mat['unit']}(原 {existing.get('current_qty')})"
                        )
                    else:
                        api_post("/api/batches", json={
                            "material_id": mat_id,
                            "batch_no": batch_no,
                            "expiry_date": str(expiry) if expiry else None,
                            "location_id": r["loc_id"],
                            "received_date": str(received),
                            "initial_qty": str(r["qty"]),
                            "remark": remark or None,
                            **type_extras,
                        })
                        st.success(
                            f"🆕 新建批次:{r['loc_name']} | 批号 {batch_no} | "
                            f"{r['qty']}{mat['unit']}"
                        )
                    ok_cnt += 1
                except APIError as e:
                    st.error(f"❌ {r['loc_name']}:{e}")
                    fail_cnt += 1

            if fail_cnt == 0:
                st.balloons()
                # 清空位置行,准备下一次录入
                st.session_state[rows_key] = [{"rid": str(uuid.uuid4())}]
            else:
                st.warning(f"完成 {ok_cnt} 行,失败 {fail_cnt} 行;失败行未生效。")

    # ── 该物料现有批次列表 ──────────────────────────────────────────
    st.markdown("---")
    st.subheader(f"📋 {mat['name_cn']} 的现有批次")
    try:
        cur = api_get("/api/batches", params={"material_id": mat_id}) or []
        if cur:
            cols_for_type = [
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
            ]
            # 类型特定列追加显示
            if mtype == "standard":
                for col, b in zip(cols_for_type, cur):
                    col["浓度"] = b.get("concentration") or "-"
            elif mtype == "column":
                for col, b in zip(cols_for_type, cur):
                    col["序列号"] = b.get("serial_no") or "-"
                    col["内部编号"] = b.get("asset_no") or "-"
                    col["负责人"] = b.get("responsible_person") or "-"
            st.dataframe(pd.DataFrame(cols_for_type),
                         use_container_width=True, height=260)
        else:
            st.caption("该物料暂无批次")
    except APIError as e:
        st.error(str(e))


# 渲染 4 个 tab
tabs = st.tabs([MATERIAL_TYPE_LABELS[t] for t in TYPE_ORDER])
for mtype, tab in zip(TYPE_ORDER, tabs):
    with tab:
        _render_intake(mtype)
