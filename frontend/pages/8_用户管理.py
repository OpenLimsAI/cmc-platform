"""
文件: frontend/pages/8_用户管理.py
用途: 用户管理 + 操作日志查看(仅管理员)
两个 tab:
    - 用户管理:列表 / 新增 / 改角色 / 启停 / 重置密码
    - 操作日志:近 N 天 audit_log 查询
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from utils import api_get, api_post, api_patch, APIError
from auth_helper import require_admin, get_user

st.set_page_config(page_title="用户管理", page_icon="👤", layout="wide")
require_admin()
st.header("👤 用户管理")

current = get_user()

tab_users, tab_audit = st.tabs(["用户列表", "操作日志"])

# ============================================================================
# 用户列表
# ============================================================================
with tab_users:
    # 新增用户
    with st.expander("➕ 新增用户", expanded=False):
        with st.form("new_user_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                nu = st.text_input("用户名 *", max_chars=50)
            with col2:
                npwd = st.text_input("初始密码 *(至少 8 位)", type="password")
            with col3:
                nrole = st.selectbox("角色 *", ["user", "admin"], index=0)
            submit_new = st.form_submit_button("✅ 创建用户", type="primary")
        if submit_new:
            if not nu or not npwd:
                st.error("用户名 / 密码 必填")
            elif len(npwd) < 8:
                st.error("密码至少 8 位")
            else:
                try:
                    api_post("/api/users", json={
                        "username": nu.strip(), "password": npwd, "role": nrole,
                    })
                    st.success(f"用户 {nu} 创建成功(must_change_password=True,首次登录需改密)")
                    st.rerun()
                except APIError as e:
                    st.error(f"创建失败: {e}")

    # 列表
    try:
        users = api_get("/api/users") or []
    except APIError as e:
        st.error(str(e))
        users = []

    if users:
        df = pd.DataFrame([
            {
                "ID": u["id"],
                "用户名": u["username"],
                "角色": u["role"],
                "状态": "启用" if u["is_active"] else "停用",
                "需改密": "是" if u["must_change_password"] else "",
                "上次登录": u.get("last_login_at") or "-",
                "创建时间": u["created_at"],
            }
            for u in users
        ])
        st.dataframe(df, use_container_width=True, height=300)

        st.markdown("---")
        st.subheader("✏️ 操作")

        opt_map = {f"{u['username']} (id={u['id']}, {u['role']})": u for u in users}
        sel = st.selectbox("选择用户", list(opt_map.keys()))
        if sel:
            target = opt_map[sel]
            is_self = target["id"] == current["id"]

            t_role, t_status, t_pwd = st.tabs(["改角色", "启用 / 停用", "重置密码"])

            with t_role:
                new_role = st.selectbox(
                    "新角色", ["user", "admin"],
                    index=0 if target["role"] == "user" else 1,
                    key=f"role_{target['id']}",
                )
                if st.button("保存角色", key=f"save_role_{target['id']}"):
                    if is_self and new_role == "user":
                        st.error("不能把自己从 admin 降级")
                    else:
                        try:
                            api_patch(f"/api/users/{target['id']}", json={"role": new_role})
                            st.success("角色已更新(该用户其他设备的会话已被踢下线)")
                            st.rerun()
                        except APIError as e:
                            st.error(str(e))

            with t_status:
                if is_self:
                    st.info("不能停用自己当前登录的账号。")
                else:
                    new_active = not target["is_active"]
                    btn_label = "停用此用户" if target["is_active"] else "启用此用户"
                    if st.button(btn_label, key=f"toggle_{target['id']}"):
                        try:
                            api_patch(f"/api/users/{target['id']}", json={"is_active": new_active})
                            st.success("已更新")
                            st.rerun()
                        except APIError as e:
                            st.error(str(e))

            with t_pwd:
                np1 = st.text_input("新密码 *(至少 8 位)", type="password",
                                     key=f"pwd1_{target['id']}")
                require_change = st.checkbox("登录后强制改密", value=True,
                                              key=f"req_chg_{target['id']}")
                if st.button("重置密码", key=f"rst_{target['id']}", type="primary"):
                    if not np1 or len(np1) < 8:
                        st.error("密码至少 8 位")
                    else:
                        try:
                            api_post(
                                f"/api/users/{target['id']}/reset-password",
                                json={
                                    "new_password": np1,
                                    "require_change_on_login": require_change,
                                },
                            )
                            st.success("密码已重置(该用户所有会话已被踢下线)")
                            st.rerun()
                        except APIError as e:
                            st.error(str(e))


# ============================================================================
# 操作日志
# ============================================================================
with tab_audit:
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        usernames = ["(全部)"] + sorted({u["username"] for u in users}) if users else ["(全部)"]
        f_user = st.selectbox("用户", usernames)
    with c2:
        f_action = st.text_input("动作(精确,如 material.create)")
    with c3:
        f_entity = st.selectbox(
            "实体类型",
            ["(全部)", "material", "batch", "inventory_txn",
             "location", "import_log", "app_user"],
        )
    with c4:
        f_eid = st.text_input("实体 ID")
    with c5:
        f_days = st.number_input("近 N 天", min_value=1, max_value=365, value=30, step=1)

    params = {"days": f_days, "limit": 500}
    if f_user != "(全部)":
        params["username"] = f_user
    if f_action:
        params["action"] = f_action.strip()
    if f_entity != "(全部)":
        params["entity_type"] = f_entity
    if f_eid:
        params["entity_id"] = f_eid.strip()

    try:
        logs = api_get("/api/audit/logs", params=params) or []
    except APIError as e:
        st.error(str(e))
        logs = []

    st.caption(f"共 {len(logs)} 条")

    if logs:
        df = pd.DataFrame([
            {
                "时间": l["created_at"],
                "用户": l.get("username") or "-",
                "动作": l["action"],
                "实体": f"{l.get('entity_type') or '-'}/{l.get('entity_id') or '-'}",
                "IP": l.get("source_ip") or "-",
                "ID": l["id"],
            }
            for l in logs
        ])
        st.dataframe(df, use_container_width=True, height=400)

        # 详情:JSON 展开看 before / after
        st.markdown("**展开某条详情**")
        sel_id = st.number_input("日志 ID", min_value=0, value=0, step=1)
        if sel_id:
            hit = next((l for l in logs if l["id"] == sel_id), None)
            if hit:
                cc1, cc2 = st.columns(2)
                with cc1:
                    st.markdown("**Before**")
                    st.json(hit.get("before_json") or {})
                with cc2:
                    st.markdown("**After**")
                    st.json(hit.get("after_json") or {})
            else:
                st.caption("当前结果中没有这条 ID。")
