"""
文件: backend/routers/location.py
用途: 储存位置 API:查询 + 新增
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import crud
from audit import model_snapshot, write_audit
from auth import require_admin
from database import get_db
from models import AppUser
from schemas import LocationCreate, LocationOut

router = APIRouter(prefix="/api/locations", tags=["location"])


@router.get("", response_model=List[LocationOut])
def list_locations(db: Session = Depends(get_db)):
    return crud.list_locations(db)


@router.post("", response_model=LocationOut)
def create_location(
    payload: LocationCreate,
    request: Request,
    current: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        obj = crud.create_location(db, payload.name, payload.storage_condition, payload.remark)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"位置 '{payload.name}' 已存在")
    write_audit(
        db, current, "location.create",
        entity_type="location", entity_id=obj.location_id,
        before=None, after=model_snapshot(obj),
        source_ip=request.client.host if request.client else None,
    )
    db.commit()
    return obj
