"""
文件: backend/routers/location.py
用途: 储存位置 API:查询 + 新增
v1.2:
    - 位置改用 (room_no, cabinet_no, layer_no) 三元组定位
    - name 由后端从三字段拼成 "{room}-{cabinet}-L{layer}",前端只读不输
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
        obj = crud.create_location(
            db,
            room_no=payload.room_no.strip(),
            cabinet_no=payload.cabinet_no.strip(),
            layer_no=payload.layer_no,
            storage_condition=payload.storage_condition,
            remark=payload.remark,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"位置 ({payload.room_no}, {payload.cabinet_no}, L{payload.layer_no}) 已存在",
        )
    write_audit(
        db, current, "location.create",
        entity_type="location", entity_id=obj.location_id,
        before=None, after=model_snapshot(obj),
        source_ip=request.client.host if request.client else None,
    )
    db.commit()
    return obj
