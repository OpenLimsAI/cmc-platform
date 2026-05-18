"""
文件: frontend/views/1_物料导入.py
用途: Excel 物料主数据导入页(干跑校验 → 确认提交 → 显示结果)
"""
from __future__ import annotations

import io
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from utils import api_get, api_post, APIError, clear_material_cache, API_BASE_URL
from auth_helper import require_admin, get_user

require_admin()
st.header("📥 物料主数据导入")

# --- 顶部说明 ---
st.markdown(
    """
**步骤**:1) 上传 Excel → 2) 干跑校验 → 3) 确认提交 → 4) 查看结果

**模板字段**:`分类、代码、物料名称、级别、生产商、规格/型号、货号、单位、包装规格、备注`
> `代码`列必须保存为**文本**格式,避免前导 0 被 Excel 自动去除。
"""
)

import requests

# --- 1) 上传文件 ---
# 操作人 = 当前登录用户(自动写入 import_log,不再手填)
_user = get_user()
operator = _user["username"] if _user else ""
st.caption(f"当前操作人(登录用户):**{operator}**")
uploaded = st.file_uploader("选择 Excel 文件", type=["xlsx", "xls"])

col_dry, col_reset = st.columns([1, 1])
with col_reset:
    if st.button("🔄 清空当前预览结果"):
        st.session_state.pop("dry_run_result", None)
        st.rerun()

if uploaded is not None and col_dry.button("🔍 干跑校验", type="primary"):
    with st.spinner("正在解析与校验..."):
        try:
            files = {"file": (uploaded.name, uploaded.getvalue(),
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            # multipart upload 不走 utils.api_post(那个是 JSON);手工带上 Authorization
            token = st.session_state.get("auth_token")
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            resp = requests.post(
                f"{API_BASE_URL}/api/import/materials/dry-run",
                files=files, timeout=60, headers=headers,
            )
            if resp.status_code >= 400:
                detail = resp.json().get("detail") if resp.headers.get("content-type", "").startswith("application/json") else resp.text
                st.error(f"干跑失败: {detail}")
            else:
                st.session_state["dry_run_result"] = resp.json()
                st.session_state["dry_run_filename"] = uploaded.name
                st.success("干跑完成")
        except Exception as e:
            st.error(f"请求失败: {e}")

# --- 2) 干跑结果 ---
result: Dict[str, Any] | None = st.session_state.get("dry_run_result")
if result:
    st.markdown("---")
    st.subheader("干跑结果")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总行数", result["total_rows"])
    c2.metric("将插入", result["insert_count"])
    c3.metric("将更新", result["update_count"])
    c4.metric("错误行", result["error_count"])

    if result.get("leading_zero_codes"):
        st.warning(
            f"⚠️ 检测到 {len(result['leading_zero_codes'])} 条以 `0` 开头的代码,"
            f"请核对 Excel 是否被自动去 0:`{', '.join(result['leading_zero_codes'][:10])}` ..."
        )

    if result.get("new_categories"):
        st.info(f"📁 文件中新增分类(将自动加入字典): `{', '.join(result['new_categories'])}`")

    if result.get("new_units"):
        st.info(f"📐 文件中新增单位(可勾选自动加入): `{', '.join(result['new_units'])}`")

    rows = result["rows"]
    df = pd.DataFrame([
        {
            "行号": r["row_index"],
            "动作": r["action"],
            "代码": r.get("material_code"),
            "物料名称": r.get("name_cn"),
            "错误": "; ".join(r.get("errors") or []),
            "提示": "; ".join(r.get("warnings") or []),
        }
        for r in rows
    ])
    st.dataframe(df, use_container_width=True, height=380)

    # 错误行下载
    err_rows = [r for r in rows if r["action"] == "ERROR"]
    if err_rows:
        err_df = pd.DataFrame([
            {**r["raw"], "_错误": "; ".join(r.get("errors") or [])}
            for r in err_rows
        ])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            err_df.to_excel(w, index=False, sheet_name="错误行")
        st.download_button(
            "⬇️ 下载错误行 Excel",
            data=buf.getvalue(),
            file_name="导入错误行.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # --- 3) 确认提交 ---
    st.markdown("---")
    st.subheader("确认提交")
    auto_create_units = st.checkbox(
        "自动加入字典中不存在的新单位",
        value=True,
        help="若取消勾选,出现新单位的行将以错误处理",
    )

    can_commit = (result["insert_count"] + result["update_count"]) > 0

    if st.button("✅ 确认导入", type="primary", disabled=not can_commit):
        # 只提交非 ERROR 的行
        valid_rows = [r["raw"] for r in rows if r["action"] != "ERROR"]
        try:
            payload = {
                "file_name": st.session_state.get("dry_run_filename") or "unknown.xlsx",
                # operator 由后端从登录用户取,不再前端传
                "auto_create_units": auto_create_units,
                "rows": valid_rows,
            }
            res = api_post("/api/import/materials/commit", json=payload)
            st.success(
                f"导入完成!共 {res['total_rows']} 行,新增 {res['inserted_rows']} / "
                f"更新 {res['updated_rows']} / 失败 {res['failed_rows']}"
            )
            clear_material_cache()
            st.session_state.pop("dry_run_result", None)
        except APIError as e:
            st.error(f"导入失败: {e}")

# --- 4) 历史导入记录 ---
st.markdown("---")
st.subheader("📋 历史导入记录(最近 20 次)")
try:
    logs = api_get("/api/import/logs", params={"limit": 20}) or []
    if logs:
        log_df = pd.DataFrame([
            {
                "ID": x["import_id"],
                "文件": x.get("file_name") or "-",
                "操作人": x.get("operator") or "-",
                "时间": x.get("imported_at"),
                "总行": x["total_rows"],
                "新增": x["inserted_rows"],
                "更新": x["updated_rows"],
                "失败": x["failed_rows"],
            }
            for x in logs
        ])
        st.dataframe(log_df, use_container_width=True, height=300)
    else:
        st.caption("暂无导入历史")
except APIError as e:
    st.error(f"加载导入历史失败: {e}")
