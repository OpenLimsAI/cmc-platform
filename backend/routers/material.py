"""
文件: backend/routers/material.py
用途: 物料相关 API:列表/详情/更新/停用/启用 + 字典查询(category/unit)
v1.2:
    - 主键改为 material_id(因为 'TT内部物料' 这个保留 code 允许重复);
      所有 mutate 路由按 /api/materials/{material_id} 操作
    - 加 hazard_class 多选字段
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

import crud
from audit import model_snapshot, write_audit
from auth import require_admin
from database import get_db
from models import AppUser
from schemas import (
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
    current: AppUser = Depends(require_admin),
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
        source_ip=request.client.host if request.client else None,
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
    current: AppUser = Depends(require_admin),
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
        source_ip=request.client.host if request.client else None,
    )
    db.commit()
    return obj


@router.post("/materials/{material_id}/deactivate", response_model=MaterialOut)
def deactivate(
    material_id: int,
    payload: DeactivateRequest,
    request: Request,
    current: AppUser = Depends(require_admin),
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
        source_ip=request.client.host if request.client else None,
    )
    db.commit()
    return obj


@router.post("/materials/{material_id}/activate", response_model=MaterialOut)
def activate(
    material_id: int,
    request: Request,
    current: AppUser = Depends(require_admin),
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
        source_ip=request.client.host if request.client else None,
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
