"""
文件: backend/mdm_client.py
用途: MDM Portal 主数据查询客户端(物料 mm 域 + 设备 eqp 域)
说明:
    - 封装对 MDM /api/v1/materials 与 /api/v1/equipments 的 HTTP 调用
    - 入库/建档时按编码查询身份信息
    - MDM 不可用时优雅降级(不阻塞本地操作)
    - 两域调用形态完全一致,收拢为 _get_by_code/_search 两个通用函数
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

log = logging.getLogger("cmc-labops.mdm")


class MdmUnavailableError(Exception):
    """MDM 服务不可用/返回异常。仅在 raise_unavailable=True 的严格模式下抛出,
    供批量同步等流程区分「查无此数据」和「MDM 挂了」——
    默认的优雅降级(返回 None/空列表)会让批量流程把中途故障当成"没有下一页"而误报成功。"""

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


def _get_by_code(
    endpoint: str, code: str, token: Optional[str] = None,
    raise_unavailable: bool = False,
) -> Optional[dict]:
    """按编码从 MDM 查询单条主数据。
    返回 dict(MDM Detail 结构)或 None(未找到 / MDM 不可用)。
    raise_unavailable=True 时,MDM 不可用/异常改抛 MdmUnavailableError(404 仍返回 None)。"""
    try:
        with _get_client(token) as client:
            resp = client.get(f"/{endpoint}/{code}")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", data)
            if resp.status_code == 404:
                return None
            log.warning("MDM 查询 %s/%s 返回 %s: %s",
                        endpoint, code, resp.status_code, resp.text[:200])
            if raise_unavailable:
                raise MdmUnavailableError(f"MDM 返回 {resp.status_code}")
            return None
    except MdmUnavailableError:
        raise
    except httpx.ConnectError:
        log.warning("MDM 服务不可用 (%s)，跳过远程查询", MDM_BASE_URL)
        if raise_unavailable:
            raise MdmUnavailableError(f"MDM 服务不可用 ({MDM_BASE_URL})")
        return None
    except Exception as e:
        log.exception("MDM 查询异常 (endpoint=%s code=%s)", endpoint, code)
        if raise_unavailable:
            raise MdmUnavailableError(f"MDM 查询异常: {e}")
        return None


def _search(
    endpoint: str, keyword: str, page: int = 1, page_size: int = 20,
    token: Optional[str] = None, raise_unavailable: bool = False,
) -> dict:
    """搜索 MDM 主数据列表。返回 {data: [...], pagination/meta: {...}} 或空结构。
    raise_unavailable=True 时,MDM 不可用/非 200 改抛 MdmUnavailableError。"""
    try:
        with _get_client(token) as client:
            resp = client.get(f"/{endpoint}", params={
                "q": keyword,
                "page": page,
                "page_size": page_size,
            })
            if resp.status_code == 200:
                return resp.json()
            if raise_unavailable:
                raise MdmUnavailableError(f"MDM 返回 {resp.status_code}")
            return {"data": [], "pagination": {"total": 0}}
    except MdmUnavailableError:
        raise
    except Exception as e:
        log.exception("MDM 搜索异常 (endpoint=%s keyword=%s)", endpoint, keyword)
        if raise_unavailable:
            raise MdmUnavailableError(f"MDM 搜索异常: {e}")
        return {"data": [], "pagination": {"total": 0}}


# ---- 物料(mm 域) ----
def get_material_by_code(code: str, token: Optional[str] = None) -> Optional[dict]:
    return _get_by_code("materials", code, token)


def search_materials(
    keyword: str, page: int = 1, page_size: int = 20, token: Optional[str] = None,
) -> dict:
    return _search("materials", keyword, page, page_size, token)


# ---- 设备(eqp 域) ----
def get_equipment_by_code(
    code: str, token: Optional[str] = None, raise_unavailable: bool = False,
) -> Optional[dict]:
    return _get_by_code("equipments", code, token, raise_unavailable=raise_unavailable)


def search_equipments(
    keyword: str, page: int = 1, page_size: int = 20, token: Optional[str] = None,
    raise_unavailable: bool = False,
) -> dict:
    return _search("equipments", keyword, page, page_size, token,
                   raise_unavailable=raise_unavailable)


def resolve_equipment_by_no(no: str, token: Optional[str] = None) -> Optional[dict]:
    """按业务编号(equipment_no, 如 TT-SC-009)实时解析 MDM 设备。
    MDM 详情接口 /equipments/{code} 只认 equipment_code(EQP-...),业务编号须走搜索;
    在搜索结果中取 equipment_no 精确(忽略大小写/首尾空格)相等的唯一一条,否则 None。"""
    no = (no or "").strip()
    if not no:
        return None
    result = search_equipments(no, page=1, page_size=50, token=token)
    items = result.get("data") or []
    matched = [it for it in items
               if (it.get("equipment_no") or "").strip().lower() == no.lower()]
    return matched[0] if len(matched) == 1 else None


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """从 Authorization header 中提取 Bearer token，便于路由层透传到 MDM。"""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None
