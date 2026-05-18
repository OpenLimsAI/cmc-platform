"""
文件: frontend/utils.py
用途: 后端 API 调用封装 + Streamlit 通用工具
说明:
    - API_BASE_URL 从环境变量读取
    - api_get/post/patch 自动注入 Authorization: Bearer <token>(从 session_state 取)
    - 401 → 清空 session_state.token,抛 AuthError,由 auth_helper 重新跳登录
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

# v1.2 保留 material_code,允许多条同名(部门内无编码物料)
TT_INTERNAL_CODE = "TT内部物料"

# v1.2 危化品分类可选值(后端 schemas.HAZARD_CLASS_VALUES 镜像)
HAZARD_CLASS_OPTIONS = ["危化品", "易燃", "易制毒", "易制爆", "剧毒品"]

# 标签颜色:与化工常用的安全色靠近,提升现场可读性
HAZARD_BADGE_COLORS = {
    "危化品": "#d32f2f",  # 红
    "易燃":   "#ef6c00",  # 橙
    "易制毒": "#6a1b9a",  # 紫
    "易制爆": "#b71c1c",  # 深红
    "剧毒品": "#212121",  # 近黑
}


# ---------------------------------------------------------------------------
# 通用请求
# ---------------------------------------------------------------------------
class APIError(Exception):
    pass


class AuthError(APIError):
    """401:未登录或会话过期。auth_helper 捕获后跳登录。"""


def _auth_headers() -> Dict[str, str]:
    token = st.session_state.get("auth_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _handle(resp: requests.Response) -> Any:
    if resp.status_code == 401:
        # 顺手清掉 session,前端下次 require_login 会重显登录表单
        for k in ("auth_token", "auth_user"):
            st.session_state.pop(k, None)
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = resp.text
        raise AuthError(f"[401] {detail}")
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
    return _handle(requests.get(
        f"{API_BASE_URL}{path}", params=params, timeout=TIMEOUT,
        headers=_auth_headers(),
    ))


def api_post(path: str, json: Optional[dict] = None, files: Optional[dict] = None,
             data: Optional[dict] = None) -> Any:
    return _handle(requests.post(
        f"{API_BASE_URL}{path}", json=json, files=files, data=data, timeout=TIMEOUT,
        headers=_auth_headers(),
    ))


def api_patch(path: str, json: Optional[dict] = None) -> Any:
    return _handle(requests.patch(
        f"{API_BASE_URL}{path}", json=json, timeout=TIMEOUT,
        headers=_auth_headers(),
    ))


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


def clear_location_cache() -> None:
    for k in ("locations",):
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
    """下拉显示:`代码 - 名称(规格)`;TT 内部物料会附 #id 以区分多条同 code。"""
    spec = m.get("spec_model")
    base = f"{m['material_code']} - {m['name_cn']}"
    if m.get("material_code") == TT_INTERNAL_CODE and m.get("material_id"):
        base = f"{base} [#{m['material_id']}]"
    return f"{base}({spec})" if spec else base


def location_label(loc: Dict) -> str:
    """位置显示:`房间-柜号-L层`(name 字段后端已计算好)。"""
    return loc.get("name") or f"{loc.get('room_no','?')}-{loc.get('cabinet_no','?')}-L{loc.get('layer_no','?')}"


def render_hazard_badges(hazards) -> None:
    """渲染一行危化品分类彩色标签。
    - 有标签:每个分类一个彩色 pill
    - 无标签:浅灰小字提示,提醒可在「物料管理」里补
    """
    if not hazards:
        st.markdown(
            '<span style="color:#9e9e9e;font-size:0.9em;">'
            '⬜ 该物料未标注危化品分类(可在「物料管理」补)</span>',
            unsafe_allow_html=True,
        )
        return
    spans = []
    for h in hazards:
        color = HAZARD_BADGE_COLORS.get(h, "#616161")
        spans.append(
            f'<span style="background:{color};color:white;'
            f'padding:3px 10px;border-radius:12px;margin-right:6px;'
            f'font-size:0.9em;font-weight:600;">⚠️ {h}</span>'
        )
    st.markdown("".join(spans), unsafe_allow_html=True)


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


def fuzzy_match_material(m: Dict, keyword: str,
                         extra_haystack: Optional[List[str]] = None) -> bool:
    """归一化后判断关键字是否落在 material_code / name_cn / spec_model / catalog_no
    之内;extra_haystack 可塞入额外字符串(如该物料的全部 batch_no)
    实现"代码/名称/批号 三合一搜索框"。
    """
    if not keyword:
        return True
    k = normalize_text(keyword)
    if not k:
        return True
    parts = [
        normalize_text(m.get(field))
        for field in ("material_code", "name_cn", "spec_model", "catalog_no")
    ]
    if extra_haystack:
        parts.extend(normalize_text(s) for s in extra_haystack)
    return k in "|".join(parts)


# ---------------------------------------------------------------------------
# 位置分组(给入库/盘点页的级联下拉用)
# ---------------------------------------------------------------------------
def locations_grouped(locations: List[Dict]) -> Dict[str, Dict[str, List[Dict]]]:
    """把扁平 locations 列表分组成 {room: {cabinet: [loc_row,...]}}。
    每一层按字符串自然顺序排;layer 按数值升序。
    给入库登记页做 房间→柜号→层 三级联用。
    """
    grouped: Dict[str, Dict[str, List[Dict]]] = {}
    for loc in locations:
        room = loc.get("room_no", "?")
        cab = loc.get("cabinet_no", "?")
        grouped.setdefault(room, {}).setdefault(cab, []).append(loc)
    for room, cabs in grouped.items():
        for cab, rows in cabs.items():
            rows.sort(key=lambda r: r.get("layer_no") or 0)
    return grouped
