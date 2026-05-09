"""
文件: backend/routers/batch.py
用途: 批次相关 API:查询、创建(同步首笔入库)、详情
v1.1:
    - POST 要求 admin
    - operator 自动取登录用户
    - 写操作触发 audit_log
"""
from __future__ import annotations

from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

import crud
from audit import model_snapshot, write_audit
from auth import require_admin
from database import get_db
from models import AppUser
from schemas import BatchCreate, BatchOut

router = APIRouter(prefix="/api/batches", tags=["batch"])


@router.get("", response_model=List[BatchOut])
def list_batches(
    material_code: Optional[str] = None,
    only_with_stock: bool = False,
    include_expired: bool = True,
    db: Session = Depends(get_db),
):
    rows = crud.list_batches(
        db,
        material_code=material_code,
        only_with_stock=only_with_stock,
        include_expired=include_expired,
    )
    out = []
    for batch, qty, loc, mat_name, unit in rows:
        out.append({
            "batch_id": batch.batch_id,
            "material_code": batch.material_code,
            "batch_no": batch.batch_no,
            "expiry_date": batch.expiry_date,
            "location_id": batch.location_id,
            "received_date": batch.received_date,
            "initial_qty": batch.initial_qty,
            "remark": batch.remark,
            "created_at": batch.created_at,
            "current_qty": Decimal(qty),
            "location_name": loc,
            "material_name": mat_name,
            "unit": unit,
        })
    return out


@router.post("", response_model=BatchOut)
def create_batch(
    payload: BatchCreate,
    request: Request,
    current: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """新建批次:不允许 (material_code, batch_no) 重复;同一物料同一批号要追加请走 /api/inventory/in"""
    mat = crud.get_material(db, payload.material_code)
    if not mat:
        raise HTTPException(status_code=404, detail=f"物料 {payload.material_code} 不存在")
    if not mat.is_active:
        raise HTTPException(status_code=400, detail=f"物料 {payload.material_code} 已停用,不可入库")
    if payload.initial_qty <= 0:
        raise HTTPException(status_code=400, detail="入库数量必须 > 0")

    existing = crud.find_batch_by_material_and_no(db, payload.material_code, payload.batch_no)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"物料 {payload.material_code} 批号 {payload.batch_no} 已存在,请通过追加入库",
        )

    batch = crud.create_batch_with_initial_in(
        db,
        material_code=payload.material_code,
        batch_no=payload.batch_no,
        expiry_date=payload.expiry_date,
        location_id=payload.location_id,
        received_date=payload.received_date,
        initial_qty=payload.initial_qty,
        operator=current.username,
        remark=payload.remark,
    )
    write_audit(
        db, current, "batch.create",
        entity_type="batch", entity_id=batch.batch_id,
        before=None, after=model_snapshot(batch),
        source_ip=request.client.host if request.client else None,
    )
    db.commit()
    qty = crud.get_batch_qty(db, batch.batch_id)
    return {
        "batch_id": batch.batch_id,
        "material_code": batch.material_code,
        "batch_no": batch.batch_no,
        "expiry_date": batch.expiry_date,
        "location_id": batch.location_id,
        "received_date": batch.received_date,
        "initial_qty": batch.initial_qty,
        "remark": batch.remark,
        "created_at": batch.created_at,
        "current_qty": qty,
        "location_name": batch.location.name if batch.location else None,
        "material_name": mat.name_cn,
        "unit": mat.unit,
    }


@router.get("/{batch_id}", response_model=BatchOut)
def get_batch(batch_id: int, db: Session = Depends(get_db)):
    b = crud.get_batch(db, batch_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"批次 {batch_id} 不存在")
    qty = crud.get_batch_qty(db, batch_id)
    return {
        "batch_id": b.batch_id,
        "material_code": b.material_code,
        "batch_no": b.batch_no,
        "expiry_date": b.expiry_date,
        "location_id": b.location_id,
        "received_date": b.received_date,
        "initial_qty": b.initial_qty,
        "remark": b.remark,
        "created_at": b.created_at,
        "current_qty": qty,
        "location_name": b.location.name if b.location else None,
        "material_name": b.material.name_cn if b.material else None,
        "unit": b.material.unit if b.material else None,
    }
