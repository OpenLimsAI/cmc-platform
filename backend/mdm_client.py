"""
文件: backend/mdm_client.py
用途: MDM Portal 物料查询客户端
说明:
    - 封装对 MDM /api/v1/materials 的 HTTP 调用
    - 入库时按 material_code 查询物料身份信息
    - MDM 不可用时优雅降级（不阻塞本地操作）
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

log = logging.getLogger("cmc-inventory.mdm")

# 开发环境 MDM 后端为 Docker 映射端口 18000(见 ~/code/PORTS.md),与 auth_router 保持一致
MDM_BASE_URL = os.getenv("MDM_BASE_URL", "http://127.0.0.1:18000/api/v1")
MDM_TIMEOUT = float(os.getenv("MDM_TIMEOUT", "5"))


def _get_client(token: Optional[str] = None) -> httpx.Client:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.Client(
        base_url=MDM_BASE_URL,
        timeout=MDM_TIMEOUT,
        trust_env=False,
        headers=headers,
    )


def get_material_by_code(code: str, token: Optional[str] = None) -> Optional[dict]:
    """按物料编码从 MDM 查询物料身份信息。
    返回 dict（MDM MaterialDetail 结构）或 None（未找到 / MDM 不可用）。
    """
    try:
        with _get_client(token) as client:
            resp = client.get(f"/materials/{code}")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", data)
            if resp.status_code == 404:
                return None
            log.warning("MDM 查询 %s 返回 %s: %s", code, resp.status_code, resp.text[:200])
            return None
    except httpx.ConnectError:
        log.warning("MDM 服务不可用 (%s)，跳过远程查询", MDM_BASE_URL)
        return None
    except Exception:
        log.exception("MDM 查询异常 (code=%s)", code)
        return None


def search_materials(
    keyword: str, page: int = 1, page_size: int = 20, token: Optional[str] = None,
) -> dict:
    """搜索 MDM 物料列表。返回 {data: [...], pagination: {...}} 或空结构。"""
    try:
        with _get_client(token) as client:
            resp = client.get("/materials", params={
                "q": keyword,
                "page": page,
                "page_size": page_size,
            })
            if resp.status_code == 200:
                return resp.json()
            return {"data": [], "pagination": {"total": 0}}
    except Exception:
        log.exception("MDM 搜索异常 (keyword=%s)", keyword)
        return {"data": [], "pagination": {"total": 0}}


def get_equipment_by_code(code: str, token: Optional[str] = None) -> Optional[dict]:
    """按设备编码从 MDM(eqp 域) 查询设备身份信息。
    返回 dict（MDM EquipmentDetail 结构）或 None（未找到 / MDM 不可用）。
    """
    try:
        with _get_client(token) as client:
            resp = client.get(f"/equipments/{code}")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", data)
            if resp.status_code == 404:
                return None
            log.warning("MDM 设备查询 %s 返回 %s: %s", code, resp.status_code, resp.text[:200])
            return None
    except httpx.ConnectError:
        log.warning("MDM 服务不可用 (%s)，跳过远程查询", MDM_BASE_URL)
        return None
    except Exception:
        log.exception("MDM 设备查询异常 (code=%s)", code)
        return None


def search_equipments(
    keyword: str, page: int = 1, page_size: int = 20, token: Optional[str] = None,
) -> dict:
    """搜索 MDM 设备列表。返回 {data: [...], pagination: {...}} 或空结构。"""
    try:
        with _get_client(token) as client:
            resp = client.get("/equipments", params={
                "q": keyword,
                "page": page,
                "page_size": page_size,
            })
            if resp.status_code == 200:
                return resp.json()
            return {"data": [], "pagination": {"total": 0}}
    except Exception:
        log.exception("MDM 设备搜索异常 (keyword=%s)", keyword)
        return {"data": [], "pagination": {"total": 0}}


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """从 Authorization header 中提取 Bearer token，便于路由层透传到 MDM。"""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None
