"""
文件: frontend/auth_helper.py
用途: Streamlit 端的登录/鉴权辅助
设计:
    - token 写入 浏览器 localStorage + st.session_state 双份,刷新不丢登录态
      (用 streamlit-local-storage;刷新后的第一轮先等待浏览器回传
       localStorage,避免还没读到 token 就误判为未登录)
    - 后端 session 10 分钟无操作自动过期(SESSION_DURATION);只要还在用,
      每次 API 调用后端自动续期
    - 每个 page 顶部调 require_login() / require_admin()
    - must_change_password=True 时,只允许走改密流程
"""
from __future__ import annotations

import time
from typing import Optional, Dict

import streamlit as st
from streamlit_local_storage import _st_local_storage

from utils import APIError, AuthError, api_get, api_post

STORAGE_TOKEN_KEY = "cmc_auth_token"
STORAGE_BOOTSTRAP_KEY = "cmc_storage_bootstrap"


def _storage_component_key(prefix: str) -> str:
    """为写入/删除操作生成唯一 key,确保连续登录/登出都会触发组件。"""
    return f"{prefix}_{time.time_ns()}"


def _get_storage_snapshot() -> Optional[Dict]:
    """读取浏览器 localStorage 的快照。

    streamlit-local-storage 的 LocalStorage 封装默认返回 {},导致刷新后的
    第一轮渲染无法区分"浏览器还没回传"和"确实没有 token"。这里直接调用
    底层组件并把 default 设为 None:None 表示还在等待 iframe 回传,dict
    才表示已经拿到浏览器里的真实 localStorage。
    """
    return _st_local_storage(
        method="getAll",
        key=STORAGE_BOOTSTRAP_KEY,
        default=None,
    )


def _set_storage_token(token: str) -> None:
    _st_local_storage(
        method="setItem",
        itemKey=STORAGE_TOKEN_KEY,
        itemValue=token,
        key=_storage_component_key("cmc_ls_set_login"),
    )


def _delete_storage_token(prefix: str = "cmc_ls_del_token") -> None:
    _st_local_storage(
        method="deleteItem",
        itemKey=STORAGE_TOKEN_KEY,
        key=_storage_component_key(prefix),
    )


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
    """登录;成功写 session_state + localStorage,失败 raise APIError。"""
    res = api_post("/api/auth/login", json={
        "username": username.strip(),
        "password": password,
    })
    token = res["access_token"]
    st.session_state["auth_token"] = token
    st.session_state["auth_user"] = res["user"]
    # 写浏览器 localStorage,F5 后能恢复
    _set_storage_token(token)
    # 登录后业务字典可能因身份变化(其实不会),稳一点清下
    for k in ("materials_active", "materials_all", "categories", "units", "locations"):
        st.session_state.pop(k, None)


def persist_session_to_storage() -> None:
    """已登录页面渲染时调用,确保当前 token 已落到浏览器 localStorage。

    登录表单提交后会立刻 st.rerun(),那一轮里渲染出的 setItem 组件不一定
    已经在浏览器执行。把持久化动作放到登录后的正常页面渲染中再确认一次,
    才能保证用户按 F5 时 localStorage 里确实有 token 可恢复。
    """
    token = st.session_state.get("auth_token")
    if not token:
        return
    if st.session_state.get("auth_storage_token_persisted") == token:
        return
    _set_storage_token(token)
    st.session_state["auth_storage_token_persisted"] = token


def logout() -> None:
    try:
        api_post("/api/auth/logout")
    except APIError:
        pass  # 失败也清本地状态
    try:
        _delete_storage_token("cmc_ls_del_logout")
    except Exception:
        pass
    for k in list(st.session_state.keys()):
        if k.startswith("auth_") or k in (
            "materials_active", "materials_all", "categories", "units", "locations"
        ):
            st.session_state.pop(k, None)


def restore_session_from_storage() -> None:
    """页面初次渲染时调用:session_state 没 token 但 localStorage 有 → 恢复并
    用 /api/users/me 验证 token 仍然有效;无效则一并清掉。

    需要在 app.py 顶部、is_logged_in() 检查之前调用。
    localStorage 来自浏览器 iframe,刷新后的第一轮 Python 脚本通常还拿不到
    值;此时先 st.stop(),等待组件回传后 Streamlit 自动 rerun。这样不会
    在 token 尚未恢复时错误渲染登录页。
    """
    if st.session_state.get("auth_token"):
        return  # 已有 token,无需 storage 兜底

    storage_snapshot = _get_storage_snapshot()
    if storage_snapshot is None:
        st.info("正在恢复登录状态...")
        st.stop()

    if not isinstance(storage_snapshot, dict):
        return

    tok = storage_snapshot.get(STORAGE_TOKEN_KEY)
    if not tok:
        return
    st.session_state["auth_token"] = tok
    try:
        user = api_get("/api/users/me")
        st.session_state["auth_user"] = user
        st.session_state["auth_storage_token_persisted"] = tok
    except (APIError, AuthError):
        # 后端已拒(过期或被撤),清掉本地与 localStorage
        st.session_state.pop("auth_token", None)
        st.session_state.pop("auth_user", None)
        st.session_state.pop("auth_storage_token_persisted", None)
        try:
            _delete_storage_token("cmc_ls_del_invalid")
        except Exception:
            pass


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
