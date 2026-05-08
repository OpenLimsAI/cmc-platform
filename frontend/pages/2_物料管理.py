"""
文件: frontend/pages/2_物料管理.py
用途: 物料检索 + 安全库存维护 + 停用/启用
"""
from __future__ import annotations

from decimal import Decimal

import pandas as pd
import streamlit as st

from utils import (
    api_get, api_patch, api_post, APIError,
    get_categories, fmt_null, clear_material_cache,
)

st.set_page_config(page_title="物料管理", page_icon="🗂️", layout="wide")
st.header("🗂️ 物料管理")

# 顶部筛选
c1, c2, c3, c4 = st.columns([2, 3, 2, 1])
with c1:
    cats = ["(全部分类)"] + get_categories()
    cat = st.selectbox("分类", cats, index=0)
with c2:
    keyword = st.text_input("代码 / 名称 模糊搜索", "")
with c3:
    show_inactive = st.checkbox("查看已停用", value=False)
with c4:
    if st.button("🔄 刷新"):
        clear_material_cache()
        st.rerun()

# 拉取数据
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
    st.info("无数据。可前往「物料导入」页导入主数据。")
else:
    # 表格(只读概览)
    df = pd.DataFrame([
        {
            "代码": m["material_code"],
            "分类": fmt_null(m.get("category")),
            "物料名称": m["name_cn"],
            "级别": fmt_null(m.get("grade")),
            "生产商": fmt_null(m.get("manufacturer")),
            "规格/型号": fmt_null(m.get("spec_model")),
            "货号": fmt_null(m.get("catalog_no")),
            "单位": m["unit"],
            "包装规格": fmt_null(m.get("package_spec")),
            "安全库存": m.get("safety_stock") or 0,
            "状态": "在用" if m["is_active"] else "已停用",
        }
        for m in materials
    ])
    st.dataframe(df, use_container_width=True, height=420)

    st.markdown("---")
    st.subheader("✏️ 行内操作")

    # 选择一条进行操作
    options = {f"{m['material_code']} - {m['name_cn']}": m for m in materials}
    sel = st.selectbox("选择物料", list(options.keys()))
    if sel:
        m = options[sel]
        is_active = m["is_active"]
        st.write(
            f"**当前**: 状态 = {'在用 ✅' if is_active else '已停用 ⛔'},"
            f"安全库存 = `{m.get('safety_stock') or 0}`"
        )

        tab_safety, tab_deact, tab_act = st.tabs(["设置安全库存", "停用", "启用"])

        with tab_safety:
            new_val = st.number_input(
                "安全库存(同物料单位)", min_value=0.0, step=1.0,
                value=float(m.get("safety_stock") or 0),
            )
            if st.button("保存安全库存"):
                try:
                    api_patch(f"/api/materials/{m['material_code']}",
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
                op = st.text_input("操作人", key="deact_op")
                reason = st.text_input("停用原因", key="deact_reason")
                if st.button("⛔ 停用此物料", type="primary"):
                    if not op:
                        st.warning("请填写操作人")
                    else:
                        try:
                            api_post(
                                f"/api/materials/{m['material_code']}/deactivate",
                                json={"operator": op, "reason": reason or None},
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
                        api_post(f"/api/materials/{m['material_code']}/activate")
                        st.success("已启用")
                        clear_material_cache()
                        st.rerun()
                    except APIError as e:
                        st.error(str(e))
