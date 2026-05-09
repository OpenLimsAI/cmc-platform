"""
文件: backend/routers/material.py
用途: 物料相关 API:列表/详情/更新/停用/启用 + 字典查询(category/unit)
v1.1:
    - 写操作要求 admin role
    - operator 字段从手填改为登录用户(deactivate)
    - 所有写操作触发 audit_log
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
    """单条创建物料。冲突 / 单位不存在等业务错误返 400。"""
    try:
        obj = crud.create_material(db, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    write_audit(
        db, current, "material.create",
        entity_type="material", entity_id=obj.material_code,
        before=None, after=model_snapshot(obj),
        source_ip=request.client.host if request.client else None,
    )
    db.commit()
    return obj


@router.get("/materials/{code}", response_model=MaterialOut)
def get_material(code: str, db: Session = Depends(get_db)):
    obj = crud.get_material(db, code)
    if not obj:
        raise HTTPException(status_code=404, detail=f"物料 {code} 不存在")
    return obj


@router.patch("/materials/{code}", response_model=MaterialOut)
def update_material(
    code: str,
    payload: MaterialUpdate,
    request: Request,
    current: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    obj = crud.get_material(db, code)
    if not obj:
        raise HTTPException(status_code=404, detail=f"物料 {code} 不存在")
    before = model_snapshot(obj)

    obj = crud.update_material(db, code, payload.model_dump(exclude_unset=True))

    write_audit(
        db, current, "material.update",
        entity_type="material", entity_id=code,
        before=before, after=model_snapshot(obj),
        source_ip=request.client.host if request.client else None,
    )
    db.commit()
    return obj


@router.post("/materials/{code}/deactivate", response_model=MaterialOut)
def deactivate(
    code: str,
    payload: DeactivateRequest,
    request: Request,
    current: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    obj = crud.get_material(db, code)
    if not obj:
        raise HTTPException(status_code=404, detail=f"物料 {code} 不存在")
    before = model_snapshot(obj)

    obj = crud.deactivate_material(db, code, current.username, payload.reason)

    write_audit(
        db, current, "material.deactivate",
        entity_type="material", entity_id=code,
        before=before, after=model_snapshot(obj),
        source_ip=request.client.host if request.client else None,
    )
    db.commit()
    return obj


@router.post("/materials/{code}/activate", response_model=MaterialOut)
def activate(
    code: str,
    request: Request,
    current: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    obj = crud.get_material(db, code)
    if not obj:
        raise HTTPException(status_code=404, detail=f"物料 {code} 不存在")
    before = model_snapshot(obj)

    obj = crud.activate_material(db, code)

    write_audit(
        db, current, "material.activate",
        entity_type="material", entity_id=code,
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
