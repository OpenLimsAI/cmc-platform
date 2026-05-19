"""
文件: backend/routers/batch.py
用途: 批次相关 API:查询、创建(同步首笔入库)、详情
v1.2:
    - 物料标识改用 material_id(TT 内部物料允许 code 重复)
    - 唯一性变成 (material_id, batch_no, location_id) 三键 ——
      同一物料同一批号可以散落多个位置,各自独立计数
    - location_id 必填
"""
from __future__ import annotations

from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

import crud
from audit import get_request_ip, model_snapshot, write_audit
from auth import require_warehouse
from database import get_db
from models import AppUser
from schemas import BatchCreate, BatchOut

router = APIRouter(prefix="/api/batches", tags=["batch"])


@router.get("", response_model=List[BatchOut])
def list_batches(
    material_id: Optional[int] = None,
    only_with_stock: bool = False,
    include_expired: bool = True,
    db: Session = Depends(get_db),
):
    rows = crud.list_batches(
        db,
        material_id=material_id,
        only_with_stock=only_with_stock,
        include_expired=include_expired,
    )
    out = []
    for batch, qty, loc, mat_code, mat_name, unit in rows:
        out.append({
            "batch_id": batch.batch_id,
            "material_id": batch.material_id,
            "batch_no": batch.batch_no,
            "expiry_date": batch.expiry_date,
            "location_id": batch.location_id,
            "received_date": batch.received_date,
            "initial_qty": batch.initial_qty,
            "remark": batch.remark,
            "concentration": batch.concentration,
            "extinction_coefficient": batch.extinction_coefficient,
            "serial_no": batch.serial_no,
            "asset_no": batch.asset_no,
            "responsible_person": batch.responsible_person,
            "created_at": batch.created_at,
            "current_qty": Decimal(qty),
            "location_name": loc,
            "material_code": mat_code,
            "material_name": mat_name,
            "unit": unit,
        })
    return out


@router.post("", response_model=BatchOut)
def create_batch(
    payload: BatchCreate,
    request: Request,
    current: AppUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """新建批次:同 (material_id, batch_no, location_id) 不允许重复;
    若该三键已存在,客户端应改走 /api/inventory/in 追加入库。"""
    mat = crud.get_material(db, payload.material_id)
    if not mat:
        raise HTTPException(status_code=404, detail=f"物料 #{payload.material_id} 不存在")
    if not mat.is_active:
        raise HTTPException(
            status_code=400, detail=f"物料 {mat.material_code} 已停用,不可入库"
        )
    if payload.initial_qty <= 0:
        raise HTTPException(status_code=400, detail="入库数量必须 > 0")

    existing = crud.find_batch_at_location(
        db, payload.material_id, payload.batch_no, payload.location_id
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"物料 {mat.material_code} 批号 {payload.batch_no} 在该位置已存在,"
                f"请通过追加入库(批次 ID={existing.batch_id})"
            ),
        )

    batch = crud.create_batch_with_initial_in(
        db,
        material_id=payload.material_id,
        batch_no=payload.batch_no,
        expiry_date=payload.expiry_date,
        location_id=payload.location_id,
        received_date=payload.received_date,
        initial_qty=payload.initial_qty,
        operator=current.username,
        remark=payload.remark,
        concentration=payload.concentration,
        extinction_coefficient=payload.extinction_coefficient,
        serial_no=payload.serial_no,
        asset_no=payload.asset_no,
        responsible_person=payload.responsible_person,
    )
    write_audit(
        db, current, "batch.create",
        entity_type="batch", entity_id=batch.batch_id,
        before=None, after=model_snapshot(batch),
        source_ip=get_request_ip(request),
    )
    db.commit()
    qty = crud.get_batch_qty(db, batch.batch_id)
    return {
        "batch_id": batch.batch_id,
        "material_id": batch.material_id,
        "batch_no": batch.batch_no,
        "expiry_date": batch.expiry_date,
        "location_id": batch.location_id,
        "received_date": batch.received_date,
        "initial_qty": batch.initial_qty,
        "remark": batch.remark,
        "concentration": batch.concentration,
        "serial_no": batch.serial_no,
        "asset_no": batch.asset_no,
        "responsible_person": batch.responsible_person,
        "created_at": batch.created_at,
        "current_qty": qty,
        "location_name": batch.location.name if batch.location else None,
        "material_code": mat.material_code,
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
        "material_id": b.material_id,
        "batch_no": b.batch_no,
        "expiry_date": b.expiry_date,
        "location_id": b.location_id,
        "received_date": b.received_date,
        "initial_qty": b.initial_qty,
        "remark": b.remark,
        "concentration": b.concentration,
        "extinction_coefficient": b.extinction_coefficient,
        "serial_no": b.serial_no,
        "asset_no": b.asset_no,
        "responsible_person": b.responsible_person,
        "created_at": b.created_at,
        "current_qty": qty,
        "location_name": b.location.name if b.location else None,
        "material_code": b.material.material_code if b.material else None,
        "material_name": b.material.name_cn if b.material else None,
        "unit": b.material.unit if b.material else None,
    }
