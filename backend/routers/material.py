"""
文件: backend/routers/material.py
用途: 物料相关 API:列表/详情/更新/停用/启用 + MDM 物料查询 + 字典查询
v2.0:
    - 新增 MDM 物料查询接口（/api/mdm/materials/...）
    - 入库时按需从 MDM 拉取物料身份并建立本地记录
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

import crud
import mdm_client
from audit import get_request_ip, model_snapshot, write_audit
from database import get_db
from auth import CurrentUser, require_warehouse
from schemas import (
    CATEGORY_VALUES,
    CategoryOut,
    DeactivateRequest,
    MaterialCreate,
    MaterialOut,
    MaterialUpdate,
    UnitOut,
)

router = APIRouter(prefix="/api", tags=["material"])


@router.get("/materials", response_model=List[MaterialOut])
def list_materials(
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    is_active: Optional[bool] = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    return crud.list_materials(
        db,
        category=category,
        keyword=keyword,
        is_active=is_active,
        include_inactive=include_inactive,
    )


@router.post("/materials", response_model=MaterialOut, status_code=201)
def create_material(
    payload: MaterialCreate,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """单条创建物料。冲突 / 单位不存在等业务错误返 400。
    'TT内部物料' 这个保留 code 允许多条共存(部门内无编码的临时物料)。"""
    try:
        obj = crud.create_material(db, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    write_audit(
        db, current, "material.create",
        entity_type="material", entity_id=obj.material_id,
        before=None, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    return obj


@router.get("/materials/{material_id}", response_model=MaterialOut)
def get_material(material_id: int, db: Session = Depends(get_db)):
    obj = crud.get_material(db, material_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"物料 #{material_id} 不存在")
    return obj


@router.patch("/materials/{material_id}", response_model=MaterialOut)
def update_material(
    material_id: int,
    payload: MaterialUpdate,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    obj = crud.get_material(db, material_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"物料 #{material_id} 不存在")
    before = model_snapshot(obj)

    obj = crud.update_material(db, material_id, payload.model_dump(exclude_unset=True))

    write_audit(
        db, current, "material.update",
        entity_type="material", entity_id=material_id,
        before=before, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    return obj


@router.post("/materials/{material_id}/deactivate", response_model=MaterialOut)
def deactivate(
    material_id: int,
    payload: DeactivateRequest,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    obj = crud.get_material(db, material_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"物料 #{material_id} 不存在")
    before = model_snapshot(obj)

    obj = crud.deactivate_material(db, material_id, current.username, payload.reason)

    write_audit(
        db, current, "material.deactivate",
        entity_type="material", entity_id=material_id,
        before=before, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    return obj


@router.post("/materials/{material_id}/activate", response_model=MaterialOut)
def activate(
    material_id: int,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    obj = crud.get_material(db, material_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"物料 #{material_id} 不存在")
    before = model_snapshot(obj)

    obj = crud.activate_material(db, material_id)

    write_audit(
        db, current, "material.activate",
        entity_type="material", entity_id=material_id,
        before=before, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    return obj


# ---------------- 字典 ----------------
@router.get("/categories", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return [{"category": c} for c in crud.list_categories(db)]


@router.get("/units", response_model=List[UnitOut])
def list_units(db: Session = Depends(get_db)):
    return crud.list_units(db)


@router.get("/categories/values")
def list_category_values():
    """返回 MDM 对齐的 category 枚举值列表。"""
    return sorted(CATEGORY_VALUES)


# ---------------- MDM 物料查询 ----------------
@router.get("/mdm/materials/{code}")
def mdm_lookup(code: str, authorization: Optional[str] = Header(default=None)):
    """从 MDM 按物料编码查询身份信息（不写本地库）。"""
    token = mdm_client.extract_bearer_token(authorization)
    data = mdm_client.get_material_by_code(code, token=token)
    if data is None:
        raise HTTPException(status_code=404, detail=f"MDM 中未找到物料 {code}")
    return data


@router.get("/mdm/materials")
def mdm_search(
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    authorization: Optional[str] = Header(default=None),
):
    """搜索 MDM 物料列表（透传 MDM API）。"""
    token = mdm_client.extract_bearer_token(authorization)
    return mdm_client.search_materials(q, page=page, page_size=page_size, token=token)


@router.post("/materials/from-mdm/{code}", response_model=MaterialOut, status_code=201)
def create_from_mdm(
    code: str,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """从 MDM 拉取物料身份信息，在本地创建记录（data_source='mdm'）。
    如果本地已存在该编码，返回已有记录。"""
    existing = crud.get_material_by_code(db, code)
    if existing:
        return existing

    token = mdm_client.extract_bearer_token(authorization)
    mdm_data = mdm_client.get_material_by_code(code, token=token)
    if mdm_data is None:
        raise HTTPException(status_code=404, detail=f"MDM 中未找到物料 {code}")

    unit = mdm_data.get("unit", "ea")
    if not db.get(crud.UnitDict, unit):
        db.add(crud.UnitDict(unit=unit, description=unit))
        db.flush()

    category = mdm_data.get("category")
    if category and not db.get(crud.CategoryDict, category):
        db.add(crud.CategoryDict(category=category))
        db.flush()

    from models import Material
    from decimal import Decimal

    obj = Material(
        material_code=mdm_data.get("material_code", code),
        name_cn=mdm_data.get("material_name", mdm_data.get("name_cn", code)),
        category=category,
        material_type=mdm_data.get("material_type"),
        grade=mdm_data.get("grade"),
        manufacturer=mdm_data.get("manufacturer"),
        spec_model=mdm_data.get("spec_model"),
        catalog_no=mdm_data.get("catalog_no"),
        unit=unit,
        package_spec=mdm_data.get("package_spec"),
        hazard_class=mdm_data.get("hazard_class"),
        safety_stock=Decimal("0"),
        is_active=True,
        data_source="mdm",
    )
    db.add(obj)
    db.flush()
    db.refresh(obj)

    write_audit(
        db, current, "material.create_from_mdm",
        entity_type="material", entity_id=obj.material_id,
        before=None, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    return obj
