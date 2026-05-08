"""
文件: backend/routers/location.py
用途: 储存位置 API:查询 + 新增
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import crud
from database import get_db
from schemas import LocationCreate, LocationOut

router = APIRouter(prefix="/api/locations", tags=["location"])


@router.get("", response_model=List[LocationOut])
def list_locations(db: Session = Depends(get_db)):
    return crud.list_locations(db)


@router.post("", response_model=LocationOut)
def create_location(payload: LocationCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_location(db, payload.name, payload.storage_condition, payload.remark)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"位置 '{payload.name}' 已存在")
