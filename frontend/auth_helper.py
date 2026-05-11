"""
文件: frontend/auth_helper.py
用途: Streamlit 端的登录/鉴权辅助
设计:
    - token 与 user 信息存在 st.session_state,刷新页面会丢失需重新登录
      (MVP 取舍:不引入 cookie/storage 第三方库;每天登录一次成本可接受)
    - 每个 page 顶部调 require_login() / require_admin()
    - must_change_password=True 时,只允许走改密流程
"""
from __future__ import annotations

from typing import Optional, Dict

import streamlit as st

from utils import APIError, AuthError, api_get, api_post


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------
def get_user() -> Optional[Dict]:
    return st.session_state.get("auth_user")


def is_logged_in() -> bool:
    return bool(st.session_state.get("auth_token") and st.session_state.get("auth_user"))


def is_admin() -> bool:
    u = get_user()
    return bool(u and u.get("role") == "admin")


def needs_password_change() -> bool:
    u = get_user()
    return bool(u and u.get("must_change_password"))


def login(username: str, password: str) -> None:
    """登录;成功写 session_state,失败 raise APIError。"""
    res = api_post("/api/auth/login", json={
        "username": username.strip(),
        "password": password,
    })
    st.session_state["auth_token"] = res["access_token"]
    st.session_state["auth_user"] = res["user"]
    # 登录后业务字典可能因身份变化(其实不会),稳一点清下
    for k in ("materials_active", "materials_all", "categories", "units", "locations"):
        st.session_state.pop(k, None)


def logout() -> None:
    try:
        api_post("/api/auth/logout")
    except APIError:
        pass  # 失败也清本地状态
    for k in list(st.session_state.keys()):
        if k.startswith("auth_") or k in (
            "materials_active", "materials_all", "categories", "units", "locations"
        ):
            st.session_state.pop(k, None)


# ---------------------------------------------------------------------------
# UI: 登录表单 / 改密表单
# ---------------------------------------------------------------------------
def render_login_form() -> None:
    """在当前位置渲染登录表单。登录成功后会 st.rerun。"""
    st.markdown("### 🔐 登录")
    with st.form("login_form", clear_on_submit=False):
        u = st.text_input("用户名", autocomplete="username")
        p = st.text_input("密码", type="password", autocomplete="current-password")
        submit = st.form_submit_button("登录", type="primary")
    if submit:
        if not u or not p:
            st.error("请填写用户名和密码")
        else:
            try:
                login(u, p)
                st.success("登录成功")
                st.rerun()
            except APIError as e:
                st.error(str(e))


def render_change_password_form() -> None:
    """首次登录强制改密时的表单。"""
    st.warning("首次登录,需修改密码后才能继续使用")
    with st.form("change_pwd_form", clear_on_submit=True):
        op = st.text_input("当前密码", type="password")
        np1 = st.text_input("新密码 *(至少 8 位)", type="password")
        np2 = st.text_input("再次输入新密码", type="password")
        submit = st.form_submit_button("修改密码", type="primary")
    if submit:
        if not op or not np1 or not np2:
            st.error("三项都需填写")
        elif np1 != np2:
            st.error("两次输入的新密码不一致")
        elif len(np1) < 8:
            st.error("新密码至少 8 位")
        elif np1 == op:
            st.error("新密码不能与原密码相同")
        else:
            try:
                api_post("/api/auth/change-password", json={
                    "old_password": op, "new_password": np1,
                })
                # 后端会撤销所有 session(包括当前 token)
                st.success("密码已修改,请用新密码重新登录")
                logout()
                st.rerun()
            except APIError as e:
                st.error(str(e))


# ---------------------------------------------------------------------------
# 页面级守卫
# ---------------------------------------------------------------------------
def render_user_chip() -> None:
    """sidebar 顶部显示当前用户 + 登出按钮。每个 page 都调一下。"""
    u = get_user()
    if not u:
        return
    role_label = "管理员" if u.get("role") == "admin" else "普通用户"
    st.sidebar.success(f"👤 {u['username']} · {role_label}")
    if st.sidebar.button("🚪 登出", use_container_width=True):
        logout()
        st.rerun()


def require_login() -> None:
    """每个 page 顶部调用。
    未登录 → 显示登录表单 + st.stop()
    需要改密 → 显示改密表单 + st.stop()
    用户卡片(render_user_chip) 由入口 app.py 统一调,这里不再重复 render
    避免 sidebar 出现两份。
    """
    if not is_logged_in():
        # 简化:在 page 顶部直接渲染登录表单
        st.title("🔐 请先登录")
        render_login_form()
        st.stop()
    if needs_password_change():
        st.title("🔑 修改密码")
        render_change_password_form()
        st.stop()


def require_admin() -> None:
    """页面级 admin 守卫;未登录 / 非 admin 都拦下。"""
    require_login()
    if not is_admin():
        st.error("⛔ 此页面仅管理员可访问")
        st.stop()
