"""
文件: frontend/views/3_入库登记.py
用途: 入库登记 — 4 个 tab(试剂/耗材/标准物质/色谱柱), 每个 tab 独立工作
设计:
    - 顶部 4 个 tab; tab 只决定"右侧显示和表单字段", 不参与物料筛选
    - 每个 tab 下: 一个搜索框(代码/名称/厂家/货号模糊) + 一个下拉选物料
    - 搜索范围 = 全部在用物料, 与当前 tab 无关
    - tab 决定的展示:
        试剂 / 耗材 → 绿色横条显示当前总库存(参考)
        标准物质   → 表单加"浓度"
        色谱柱     → 表单加"序列号 / 内部编号 / 负责人"
    - 提交时按当前 tab 的字段写入 batch, 与物料自身的 material_type 无关
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
# 这里的 tab_type 只决定右侧显示和表单字段, 不参与物料筛选
TAB_TYPES = ["reagent", "consumable", "standard", "column"]


def _render_intake_tab(tab_type: str) -> None:
    """渲染单个 tab 的入库内容。所有 widget / session_state key 按 tab_type 命名,
    避免 4 个 tab 之间状态串台。
    搜索范围 = 全部在用物料(不按 tab_type 过滤)。"""

    # 物料 = 全部在用物料, 不按 tab 类型过滤
    materials = get_materials(active_only=True)
    if not materials:
        st.warning("还没有任何在用物料。请先到「物料管理」或「物料导入」录入物料。")
        return

    keyword = st.text_input(
        "搜索物料(代码 / 名称 / 厂家 / 货号, 支持模糊)", "",
        key=f"kw_{tab_type}",
        placeholder="留空显示全部",
    )
    filtered = [m for m in materials if fuzzy_match_material(m, keyword)]

    if not filtered:
        st.warning("没有匹配的物料,换个关键字试试。")
        return

    opt_map = {material_label(m): m for m in filtered}
    sel = st.selectbox(
        f"选择物料(共 {len(filtered)} 条)", list(opt_map.keys()),
        key=f"sel_mat_{tab_type}",
    )
    mat = opt_map[sel]
    mat_id = mat["material_id"]

    render_hazard_badges(mat.get("hazard_class"))

    # 当前总库存(参考); 4 个 tab 都显示
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

    # 物料信息卡(选完物料展示在 入库信息 区域顶部)
    with st.container(border=True):
        st.markdown(
            f"**📦 {mat['material_code']} · {mat['name_cn']}**  "
            f"&nbsp;&nbsp;·&nbsp;&nbsp; 单位 `{mat['unit']}`"
        )
        info_cols = st.columns(4)
        info_cols[0].markdown(f"**厂家**\n\n{mat.get('manufacturer') or '-'}")
        info_cols[1].markdown(f"**货号**\n\n{mat.get('catalog_no') or '-'}")
        info_cols[2].markdown(f"**级别**\n\n{mat.get('grade') or '-'}")
        info_cols[3].markdown(f"**规格**\n\n{mat.get('spec_model') or '-'}")

    locs = get_locations()
    if not locs:
        st.error("位置字典为空,请管理员先初始化。")
        return
    grouped = locations_grouped(locs)
    rooms_sorted = sorted(grouped.keys())

    # 多位置行: 切换物料(或切换 tab)时重置
    mat_key = f"__in_for_mat_{tab_type}__"
    rows_key = f"in_loc_rows_{tab_type}"
    if st.session_state.get(mat_key) != mat_id:
        st.session_state[mat_key] = mat_id
        st.session_state[rows_key] = [{"rid": str(uuid.uuid4())}]

    st.markdown("##### 存放位置(可多行 — 同批号在不同位置各自计数)")

    remove_idx = None  # 推迟删除, 避免循环中改变列表
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

    # ── 全局字段(批号/日期/效期/备注 + 按 tab_type 的专属) ─────────────
    with st.form(f"in_form_{tab_type}", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            batch_no = st.text_input(
                "供应商批号 *", max_chars=100, key=f"in_bno_{tab_type}",
            )
            received = st.date_input(
                "到货日期 *", value=date.today(), key=f"in_rec_{tab_type}",
            )
        with col2:
            has_expiry = st.checkbox(
                "此批次有效期", value=True, key=f"in_he_{tab_type}",
            )
            expiry = st.date_input(
                "效期", value=date.today(), key=f"in_exp_{tab_type}",
            ) if has_expiry else None
            remark = st.text_area(
                "备注", max_chars=500, height=80, key=f"in_rmk_{tab_type}",
            )

        # 按 tab 决定专属字段
        type_extras = {
            "concentration": None,
            "extinction_coefficient": None,
            "serial_no": None,
            "asset_no": None,
            "responsible_person": None,
        }
        if tab_type == "standard":
            st.markdown("##### 标准物质专属字段")
            scol1, scol2 = st.columns(2)
            with scol1:
                _v = st.text_input(
                    "浓度", max_chars=50, help="例如 10 mg/mL",
                    key=f"in_conc_{tab_type}",
                )
                type_extras["concentration"] = (_v or "").strip() or None
            with scol2:
                _ec = st.text_input(
                    "消光系数", max_chars=50,
                    help="ε, 例如 18400 M⁻¹cm⁻¹",
                    key=f"in_ec_{tab_type}",
                )
                type_extras["extinction_coefficient"] = (_ec or "").strip() or None
        elif tab_type == "column":
            st.markdown("##### 色谱柱专属字段")
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                type_extras["serial_no"] = (
                    st.text_input(
                        "序列号", max_chars=100, help="厂家出厂序列号",
                        key=f"in_sn_{tab_type}",
                    ) or ""
                ).strip() or None
            with cc2:
                type_extras["asset_no"] = (
                    st.text_input(
                        "内部编号", max_chars=100, help="本实验室资产编号",
                        key=f"in_an_{tab_type}",
                    ) or ""
                ).strip() or None
            with cc3:
                type_extras["responsible_person"] = (
                    st.text_input(
                        "负责人", max_chars=50,
                        key=f"in_rp_{tab_type}",
                    ) or ""
                ).strip() or None

        submitted = st.form_submit_button("✅ 提交入库(全部位置)", type="primary")

    if submitted:
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
                errors.append(f"位置 {r['loc_name']} 在表中重复出现, 请合并或删除")
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
                st.session_state[rows_key] = [{"rid": str(uuid.uuid4())}]
            else:
                st.warning(f"完成 {ok_cnt} 行, 失败 {fail_cnt} 行;失败行未生效。")

    # ── 该物料现有批次列表 ──────────────────────────────────────────
    st.markdown("---")
    st.subheader(f"📋 {mat['name_cn']} 的现有批次")
    try:
        cur = api_get("/api/batches", params={"material_id": mat_id}) or []
        if cur:
            rows_table = [
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
            st.dataframe(pd.DataFrame(rows_table),
                         use_container_width=True, height=240)
        else:
            st.caption("该物料暂无批次")
    except APIError as e:
        st.error(str(e))

    # ── 该物料出入库条目(交易流水) ─────────────────────────────────
    st.markdown("---")
    st.subheader(f"📜 {mat['name_cn']} 的出入库条目")
    try:
        txns = api_get(
            "/api/inventory/txns",
            params={"material_id": mat_id, "limit": 200},
        ) or []
        if txns:
            _TXN_TYPE_LABEL = {
                "IN": "📥 入库",
                "OUT": "📤 出库",
                "ADJUST": "🧮 盘点调整",
                "TRANSFER_IN": "🚚 移入",
                "TRANSFER_OUT": "🚚 移出",
            }
            txn_rows = [
                {
                    "时间": t.get("txn_date"),
                    "类型": _TXN_TYPE_LABEL.get(t.get("txn_type"), t.get("txn_type")),
                    "数量": t.get("qty"),
                    "批号": t.get("batch_no") or "-",
                    "位置": t.get("location_name") or "-",
                    "经办人": t.get("operator") or "-",
                    "备注": t.get("remark") or "-",
                }
                for t in txns
            ]
            # 当前 tab 专属列追加显示
            if tab_type == "standard":
                for row, t in zip(txn_rows, txns):
                    row["浓度"] = t.get("concentration") or "-"
                    row["消光系数"] = t.get("extinction_coefficient") or "-"
            elif tab_type == "column":
                for row, t in zip(txn_rows, txns):
                    row["序列号"] = t.get("serial_no") or "-"
                    row["内部编号"] = t.get("asset_no") or "-"
                    row["负责人"] = t.get("responsible_person") or "-"
            st.dataframe(pd.DataFrame(txn_rows),
                         use_container_width=True, height=300)
            st.caption(f"显示最近 {len(txns)} 条;按时间倒序")
        else:
            st.caption("该物料暂无出入库记录")
    except APIError as e:
        st.error(str(e))


# 渲染 4 个 tab
tabs = st.tabs([MATERIAL_TYPE_LABELS[t] for t in TAB_TYPES])
for tab_type, tab in zip(TAB_TYPES, tabs):
    with tab:
        _render_intake_tab(tab_type)
