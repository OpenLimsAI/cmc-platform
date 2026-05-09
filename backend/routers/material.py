"""
文件: backend/routers/material.py
用途: 物料相关 API:列表/详情/更新/停用/启用 + 字典查询(category/unit)
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import crud
from database import get_db
from schemas import (
    MaterialOut,
    MaterialCreate,
    MaterialUpdate,
    DeactivateRequest,
    UnitOut,
    CategoryOut,
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
    """物料列表查询。
    - 默认只返回启用中的物料
    - include_inactive=true 同时返回已停用物料
    - is_active=false 仅返回已停用物料
    """
    return crud.list_materials(
        db,
        category=category,
        keyword=keyword,
        is_active=is_active,
        include_inactive=include_inactive,
    )


@router.post("/materials", response_model=MaterialOut, status_code=201)
def create_material(payload: MaterialCreate, db: Session = Depends(get_db)):
    """单条创建物料。冲突 / 单位不存在等业务错误返 400。"""
    try:
        return crud.create_material(db, payload.model_dump())
    except ValueError as e:
        # 业务校验失败,翻 400 并把中文消息透出
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/materials/{code}", response_model=MaterialOut)
def get_material(code: str, db: Session = Depends(get_db)):
    obj = crud.get_material(db, code)
    if not obj:
        raise HTTPException(status_code=404, detail=f"物料 {code} 不存在")
    return obj


@router.patch("/materials/{code}", response_model=MaterialOut)
def update_material(code: str, payload: MaterialUpdate, db: Session = Depends(get_db)):
    obj = crud.update_material(db, code, payload.model_dump(exclude_unset=True))
    if not obj:
        raise HTTPException(status_code=404, detail=f"物料 {code} 不存在")
    return obj


@router.post("/materials/{code}/deactivate", response_model=MaterialOut)
def deactivate(code: str, payload: DeactivateRequest, db: Session = Depends(get_db)):
    obj = crud.deactivate_material(db, code, payload.operator, payload.reason)
    if not obj:
        raise HTTPException(status_code=404, detail=f"物料 {code} 不存在")
    return obj


@router.post("/materials/{code}/activate", response_model=MaterialOut)
def activate(code: str, db: Session = Depends(get_db)):
    obj = crud.activate_material(db, code)
    if not obj:
        raise HTTPException(status_code=404, detail=f"物料 {code} 不存在")
    return obj


# ---------------- 字典 ----------------
@router.get("/categories", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return [{"category": c} for c in crud.list_categories(db)]


@router.get("/units", response_model=List[UnitOut])
def list_units(db: Session = Depends(get_db)):
    return crud.list_units(db)
