"""
文件: frontend/utils.py
用途: 后端 API 调用封装 + Streamlit 通用工具
说明:
    - API_BASE_URL 从环境变量读取(docker-compose 注入)
    - 提供 cache_data 包裹的字典加载,降低下拉响应延迟
    - 友好错误处理:把 HTTP 错误转成中文提示
    - 关键字搜索归一化:NFKC + lower + 去空白,兼容全角/半角混用
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, Optional, List, Dict

import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 30


# ---------------------------------------------------------------------------
# 通用请求
# ---------------------------------------------------------------------------
class APIError(Exception):
    pass


def _handle(resp: requests.Response) -> Any:
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = resp.text
        raise APIError(f"[{resp.status_code}] {detail}")
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


def api_get(path: str, params: Optional[dict] = None) -> Any:
    return _handle(requests.get(f"{API_BASE_URL}{path}", params=params, timeout=TIMEOUT))


def api_post(path: str, json: Optional[dict] = None, files: Optional[dict] = None,
             data: Optional[dict] = None) -> Any:
    return _handle(requests.post(
        f"{API_BASE_URL}{path}", json=json, files=files, data=data, timeout=TIMEOUT
    ))


def api_patch(path: str, json: Optional[dict] = None) -> Any:
    return _handle(requests.patch(f"{API_BASE_URL}{path}", json=json, timeout=TIMEOUT))


# ---------------------------------------------------------------------------
# 字典缓存(用 session_state,提升下拉响应速度)
# ---------------------------------------------------------------------------
def get_categories(force_refresh: bool = False) -> List[str]:
    if force_refresh or "categories" not in st.session_state:
        try:
            data = api_get("/api/categories") or []
            st.session_state["categories"] = [d["category"] for d in data]
        except APIError:
            st.session_state["categories"] = []
    return st.session_state["categories"]


def get_units(force_refresh: bool = False) -> List[str]:
    if force_refresh or "units" not in st.session_state:
        try:
            data = api_get("/api/units") or []
            st.session_state["units"] = [d["unit"] for d in data]
        except APIError:
            st.session_state["units"] = []
    return st.session_state["units"]


def get_locations(force_refresh: bool = False) -> List[Dict]:
    if force_refresh or "locations" not in st.session_state:
        try:
            st.session_state["locations"] = api_get("/api/locations") or []
        except APIError:
            st.session_state["locations"] = []
    return st.session_state["locations"]


def get_materials(active_only: bool = True, force_refresh: bool = False) -> List[Dict]:
    """缓存物料字典(给下拉用),停用物料默认不显示。"""
    key = "materials_active" if active_only else "materials_all"
    if force_refresh or key not in st.session_state:
        try:
            params = {"is_active": "true"} if active_only else {"include_inactive": "true"}
            st.session_state[key] = api_get("/api/materials", params=params) or []
        except APIError:
            st.session_state[key] = []
    return st.session_state[key]


def clear_material_cache() -> None:
    """物料字典发生变化(导入/停用/启用)后调用。"""
    for k in ("materials_active", "materials_all", "categories", "units"):
        st.session_state.pop(k, None)


# ---------------------------------------------------------------------------
# 展示工具
# ---------------------------------------------------------------------------
def fmt_null(v) -> str:
    """NULL 显示为 '-'。"""
    if v is None or v == "":
        return "-"
    return str(v)


def material_label(m: Dict) -> str:
    """下拉显示:`代码 - 名称(规格)`"""
    spec = m.get("spec_model")
    base = f"{m['material_code']} - {m['name_cn']}"
    return f"{base}({spec})" if spec else base


# ---------------------------------------------------------------------------
# 文本归一化(供模糊搜索使用)
#
# 解决 bug:用户在「入库登记」搜索时,因数据/输入混用全角半角(如 全角括号
# 「(」 vs 半角 「(」、全角空格 vs 半角空格)导致匹配失败。
# 用 Unicode NFKC 把全角折叠为半角,再去掉所有空白,再 lower。
# ---------------------------------------------------------------------------
_WS_RE = re.compile(r"\s+")


def normalize_text(s: Optional[str]) -> str:
    """归一化文本用于模糊匹配:NFKC 折叠 → 去全部空白 → lower。"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = _WS_RE.sub("", s)
    return s.lower()


def fuzzy_match_material(m: Dict, keyword: str) -> bool:
    """归一化后判断关键字是否落在 material_code / name_cn / spec_model / catalog_no 之内。
    匹配范围特意比原来宽,避免"用户记得的字符串"与"录入字段"放错位置导致搜不到。
    """
    if not keyword:
        return True
    k = normalize_text(keyword)
    if not k:
        return True
    haystack = "|".join(
        normalize_text(m.get(field))
        for field in ("material_code", "name_cn", "spec_model", "catalog_no")
    )
    return k in haystack
