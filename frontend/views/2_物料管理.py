"""
文件: frontend/views/2_物料管理.py
用途: 物料检索 + 新增 + 编辑 + 安全库存维护 + 停用/启用
v1.2:
    - 主键改用 material_id;'TT内部物料' 这个保留 code 允许重复出现
      (部门内无编码物料的占位 code),下拉以 [#id] 区分
    - 新增 / 编辑表单加 hazard_class(危化品分类)多选
    - 所有 mutate API 走 /api/materials/{material_id}
"""
from __future__ import annotations

from decimal import Decimal

import pandas as pd
import streamlit as st

from utils import (
    api_get, api_patch, api_post, APIError,
    get_categories, get_units, fmt_null, clear_material_cache,
    HAZARD_CLASS_OPTIONS, TT_INTERNAL_CODE,
)
from auth_helper import require_login, can_manage_inventory

require_login()
st.header("🗂️ 物料管理")

units = get_units()
cats_existing = get_categories()
_admin = can_manage_inventory()

# ============================================================================
# ➕ 新增物料 — 仅 admin / warehouse_admin
# ============================================================================
if not _admin:
    st.caption("ℹ️ 你是普通用户(只读),新增 / 编辑 / 停用 / 启用 操作仅管理员或库管理员可见。")


def _render_new_material_form():
    with st.expander("➕ 新增物料(单条录入)", expanded=False):
        st.caption(
            f"代码列保留前导 0;新分类会自动加入字典。"
            f"批量录入请走「物料导入」页。"
            f"\n\n💡 部门内无物料代码的临时物料可填 `{TT_INTERNAL_CODE}`,"
            f"该 code 允许多条共存,系统会自动用内部 id 区分。"
        )
        if not units:
            st.warning("单位字典为空,无法新增。请先初始化 unit_dict 表。")
            return
        with st.form("new_material_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                n_code = st.text_input("代码 *", max_chars=20,
                                        placeholder=f"如 42001 / 04321 / {TT_INTERNAL_CODE}")
                n_name = st.text_input("物料名称 *", max_chars=200)
                n_unit = st.selectbox("单位 *", units, index=0)
                n_safety = st.number_input("安全库存", min_value=0.0, step=1.0, value=0.0)
            with col2:
                cats_hint = f"已有: {', '.join(cats_existing[:10])}" + (
                    " ..." if len(cats_existing) > 10 else ""
                ) if cats_existing else "首次新增请直接填,会自动加入字典"
                n_cat = st.text_input("分类", help=cats_hint)
                n_grade = st.text_input("级别")
                n_mfr = st.text_input("生产商")
                n_spec = st.text_input("规格/型号")

            col3, col4 = st.columns(2)
            with col3:
                n_catalog = st.text_input("货号")
            with col4:
                n_pkg = st.text_input("包装规格")

            n_hazard = st.multiselect(
                "危化品分类(可多选)", HAZARD_CLASS_OPTIONS,
                help="不属于危化品的留空即可",
            )
            n_remark = st.text_area("备注", height=80)

            submit_new = st.form_submit_button("✅ 创建物料", type="primary")

        if submit_new:
            code = (n_code or "").strip()
            name = (n_name or "").strip()
            if not code or not name or not n_unit:
                st.error("代码 / 物料名称 / 单位 为必填")
                return
            try:
                api_post("/api/materials", json={
                    "material_code": code,
                    "category": (n_cat or "").strip() or None,
                    "name_cn": name,
                    "grade": (n_grade or "").strip() or None,
                    "manufacturer": (n_mfr or "").strip() or None,
                    "spec_model": (n_spec or "").strip() or None,
                    "catalog_no": (n_catalog or "").strip() or None,
                    "unit": n_unit,
                    "package_spec": (n_pkg or "").strip() or None,
                    "hazard_class": n_hazard or None,
                    "remark": (n_remark or "").strip() or None,
                    "safety_stock": str(Decimal(str(n_safety))),
                })
                st.success(f"物料 `{code}` 创建成功!")
                clear_material_cache()
                st.rerun()
            except APIError as e:
                st.error(f"创建失败: {e}")


if _admin:
    _render_new_material_form()

st.markdown("---")

# ============================================================================
# 检索 + 列表
# ============================================================================
c1, c2, c3, c4 = st.columns([2, 3, 2, 1])
with c1:
    cats = ["(全部分类)"] + cats_existing
    cat = st.selectbox("分类", cats, index=0)
with c2:
    keyword = st.text_input("代码 / 名称 模糊搜索", "")
with c3:
    show_inactive = st.checkbox("查看已停用", value=False)
with c4:
    if st.button("🔄 刷新"):
        clear_material_cache()
        st.rerun()

params = {}
if cat != "(全部分类)":
    params["category"] = cat
if keyword:
    params["keyword"] = keyword
if show_inactive:
    params["include_inactive"] = "true"

try:
    materials = api_get("/api/materials", params=params) or []
except APIError as e:
    st.error(f"加载失败: {e}")
    materials = []

st.caption(f"共 {len(materials)} 条")

if not materials:
    st.info("无数据。可前往「物料导入」页批量导入,或在上方「➕ 新增物料」单条录入。")
else:
    # 表格(只读概览)
    df = pd.DataFrame([
        {
            "ID": m["material_id"],
            "代码": m["material_code"],
            "分类": fmt_null(m.get("category")),
            "物料名称": m["name_cn"],
            "级别": fmt_null(m.get("grade")),
            "生产商": fmt_null(m.get("manufacturer")),
            "规格/型号": fmt_null(m.get("spec_model")),
            "货号": fmt_null(m.get("catalog_no")),
            "单位": m["unit"],
            "包装规格": fmt_null(m.get("package_spec")),
            "危化品分类": "、".join(m.get("hazard_class") or []) or "-",
            "安全库存": m.get("safety_stock") or 0,
            "状态": "在用" if m["is_active"] else "已停用",
        }
        for m in materials
    ])
    st.dataframe(df, use_container_width=True, height=420)

    if not _admin:
        st.caption("ℹ️ 行内操作(编辑 / 安全库存 / 停用 / 启用)仅管理员可用。")

if materials and _admin:
    st.markdown("---")
    st.subheader("✏️ 行内操作")

    # 选择一条进行操作 — key 用 material_id(TT 例外下 code 不唯一)
    def _row_label(m):
        base = f"{m['material_code']} - {m['name_cn']}"
        if m.get("material_code") == TT_INTERNAL_CODE:
            base = f"{base} [#{m['material_id']}]"
        return base

    options = {_row_label(m): m for m in materials}
    sel = st.selectbox("选择物料", list(options.keys()))
    if sel:
        m = options[sel]
        mat_id = m["material_id"]
        is_active = m["is_active"]
        st.write(
            f"**当前**: 状态 = {'在用 ✅' if is_active else '已停用 ⛔'},"
            f"安全库存 = `{m.get('safety_stock') or 0}`,"
            f"危化品分类 = `{'、'.join(m.get('hazard_class') or []) or '无'}`"
        )

        tab_edit, tab_safety, tab_deact, tab_act = st.tabs(
            ["编辑物料", "设置安全库存", "停用", "启用"]
        )

        # ---- 编辑物料 ----
        with tab_edit:
            if not is_active:
                st.warning("物料已停用,如需修改请先在「启用」tab 中恢复。")
            elif not units:
                st.warning("单位字典为空,无法编辑单位。")
            else:
                k = f"mid{mat_id}"  # widget key 用 material_id,避免不同物料窗体串台
                cur_unit_idx = units.index(m["unit"]) if m.get("unit") in units else 0
                cur_hazard = list(m.get("hazard_class") or [])
                with st.form(f"edit_form_{k}", clear_on_submit=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        ed_name = st.text_input(
                            "物料名称 *", value=m.get("name_cn") or "", max_chars=200,
                            key=f"ed_name_{k}",
                        )
                        ed_unit = st.selectbox(
                            "单位 *", units, index=cur_unit_idx,
                            key=f"ed_unit_{k}",
                        )
                        ed_grade = st.text_input(
                            "级别", value=m.get("grade") or "",
                            key=f"ed_grade_{k}",
                        )
                        ed_mfr = st.text_input(
                            "生产商", value=m.get("manufacturer") or "",
                            key=f"ed_mfr_{k}",
                        )
                    with col2:
                        ed_cat = st.text_input(
                            "分类", value=m.get("category") or "",
                            help="改成新值会自动加入分类字典",
                            key=f"ed_cat_{k}",
                        )
                        ed_spec = st.text_input(
                            "规格/型号", value=m.get("spec_model") or "",
                            key=f"ed_spec_{k}",
                        )
                        ed_catalog = st.text_input(
                            "货号", value=m.get("catalog_no") or "",
                            key=f"ed_cat_no_{k}",
                        )
                        ed_pkg = st.text_input(
                            "包装规格", value=m.get("package_spec") or "",
                            key=f"ed_pkg_{k}",
                        )
                    ed_hazard = st.multiselect(
                        "危化品分类(可多选)", HAZARD_CLASS_OPTIONS,
                        default=cur_hazard, key=f"ed_hazard_{k}",
                    )
                    ed_remark = st.text_area(
                        "备注", value=m.get("remark") or "", height=80,
                        key=f"ed_remark_{k}",
                    )
                    submit_edit = st.form_submit_button("💾 保存修改", type="primary")

                if submit_edit:
                    ed_name_clean = (ed_name or "").strip()
                    if not ed_name_clean or not ed_unit:
                        st.error("物料名称 / 单位 为必填")
                    else:
                        try:
                            api_patch(f"/api/materials/{mat_id}", json={
                                "category": (ed_cat or "").strip() or None,
                                "name_cn": ed_name_clean,
                                "grade": (ed_grade or "").strip() or None,
                                "manufacturer": (ed_mfr or "").strip() or None,
                                "spec_model": (ed_spec or "").strip() or None,
                                "catalog_no": (ed_catalog or "").strip() or None,
                                "unit": ed_unit,
                                "package_spec": (ed_pkg or "").strip() or None,
                                "hazard_class": ed_hazard or None,
                                "remark": (ed_remark or "").strip() or None,
                            })
                            st.success("已保存")
                            clear_material_cache()
                            st.rerun()
                        except APIError as e:
                            st.error(str(e))

        with tab_safety:
            new_val = st.number_input(
                "安全库存(同物料单位)", min_value=0.0, step=1.0,
                value=float(m.get("safety_stock") or 0),
            )
            if st.button("保存安全库存"):
                try:
                    api_patch(f"/api/materials/{mat_id}",
                              json={"safety_stock": str(Decimal(str(new_val)))})
                    st.success("已保存")
                    clear_material_cache()
                    st.rerun()
                except APIError as e:
                    st.error(str(e))

        with tab_deact:
            if not is_active:
                st.info("该物料已是停用状态")
            else:
                # 查询当前总库存,>0 时要求二次确认
                current_qty = None
                try:
                    # 用 material_id 唯一指定;keyword 仍按 code 过滤是个近似
                    rows = api_get(
                        "/api/stock/by-material",
                        params={"keyword": m["material_code"], "include_inactive": "true",
                                "only_positive": "false"},
                    ) or []
                    hit = next((r for r in rows if r["material_id"] == mat_id), None)
                    if hit:
                        current_qty = float(hit.get("total_qty") or 0)
                except APIError:
                    current_qty = None

                if current_qty and current_qty > 0:
                    st.warning(
                        f"⚠️ 该物料仍有库存 **{current_qty} {m['unit']}**。"
                        f"停用后将不能继续入库/出库,但已有批次和历史记录会保留。"
                    )
                    confirm = st.checkbox(
                        "我已了解,仍要停用",
                        key=f"deact_confirm_{mat_id}",
                    )
                else:
                    confirm = True  # 库存为 0 / 查询失败 → 不强制额外确认

                # operator 自动取登录用户(后端记 audit_log + deactivated_by)
                reason = st.text_input("停用原因", key=f"deact_reason_{mat_id}")
                if st.button("⛔ 停用此物料", type="primary", disabled=not confirm):
                    try:
                        api_post(
                            f"/api/materials/{mat_id}/deactivate",
                            json={"reason": reason or None},
                        )
                        st.success("已停用")
                        clear_material_cache()
                        st.rerun()
                    except APIError as e:
                        st.error(str(e))

        with tab_act:
            if is_active:
                st.info("该物料正在使用中,无需启用")
            else:
                if st.button("✅ 启用此物料", type="primary"):
                    try:
                        api_post(f"/api/materials/{mat_id}/activate")
                        st.success("已启用")
                        clear_material_cache()
                        st.rerun()
                    except APIError as e:
                        st.error(str(e))
