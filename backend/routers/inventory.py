"""
文件: backend/routers/inventory.py
用途: 出入库流水 API
权限:
    - 写操作要求 admin
    - operator 自动取登录用户
    - 触发 audit_log
"""
from __future__ import annotations

from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

import crud
from audit import get_request_ip, model_snapshot, write_audit
from auth import require_warehouse
from database import get_db
from models import AppUser
from schemas import (
    TxnAdjustRequest,
    TxnInRequest,
    TxnOut,
    TxnOutRequest,
    TransferRequest,
)

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.post("/in", response_model=TxnOut)
def receive_in(
    payload: TxnInRequest,
    request: Request,
    current: AppUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """已有批次追加入库。"""
    b = crud.get_batch(db, payload.batch_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"批次 {payload.batch_id} 不存在")
    txn = crud.add_in(
        db, payload.batch_id, payload.qty, payload.txn_date, current.username, payload.remark
    )
    write_audit(
        db, current, "inventory.in",
        entity_type="inventory_txn", entity_id=txn.txn_id,
        before=None, after=model_snapshot(txn),
        source_ip=get_request_ip(request),
    )
    db.commit()
    return _to_txn_out(db, txn)


@router.post("/out", response_model=TxnOut)
def issue_out(
    payload: TxnOutRequest,
    request: Request,
    current: AppUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """从指定批次出库。"""
    b = crud.get_batch(db, payload.batch_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"批次 {payload.batch_id} 不存在")
    current_qty = crud.get_batch_qty(db, payload.batch_id)
    if payload.qty > current_qty:
        raise HTTPException(
            status_code=400,
            detail=f"出库数量 {payload.qty} 超过批次现有库存 {current_qty}",
        )
    txn = crud.add_out(
        db, payload.batch_id, payload.qty, payload.txn_date,
        current.username, payload.purpose, payload.remark,
    )
    write_audit(
        db, current, "inventory.out",
        entity_type="inventory_txn", entity_id=txn.txn_id,
        before=None, after=model_snapshot(txn),
        source_ip=get_request_ip(request),
    )
    db.commit()
    return _to_txn_out(db, txn)


@router.post("/adjust", response_model=TxnOut)
def adjust(
    payload: TxnAdjustRequest,
    request: Request,
    current: AppUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """盘点调整,可正可负;但调整后批次库存不得 < 0。"""
    b = crud.get_batch(db, payload.batch_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"批次 {payload.batch_id} 不存在")
    current_qty = crud.get_batch_qty(db, payload.batch_id)
    if current_qty + payload.qty < 0:
        raise HTTPException(
            status_code=400,
            detail=f"调整后库存为负({current_qty} + {payload.qty} < 0),已拒绝",
        )
    txn = crud.add_adjust(
        db, payload.batch_id, payload.qty, payload.txn_date, current.username, payload.remark
    )
    write_audit(
        db, current, "inventory.adjust",
        entity_type="inventory_txn", entity_id=txn.txn_id,
        before=None, after=model_snapshot(txn),
        source_ip=get_request_ip(request),
    )
    db.commit()
    return _to_txn_out(db, txn)


@router.post("/transfer", response_model=List[TxnOut])
def transfer(
    payload: TransferRequest,
    request: Request,
    current: AppUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """移库:一笔操作 = 源 OUT + 目的 IN(同物料同批号在两个位置间搬)。
    返回两条 txn。审计落一条 inventory.transfer。"""
    try:
        src_txn, dest_txn, dest_batch = crud.transfer_batch(
            db,
            source_batch_id=payload.source_batch_id,
            dest_location_id=payload.dest_location_id,
            qty=payload.qty,
            operator=current.username,
            txn_date=payload.txn_date,
            remark=payload.remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    write_audit(
        db, current, "inventory.transfer",
        entity_type="batch", entity_id=payload.source_batch_id,
        before=None,
        after={
            "source_batch_id": payload.source_batch_id,
            "dest_batch_id": dest_batch.batch_id,
            "dest_location_id": payload.dest_location_id,
            "qty": str(payload.qty),
            "source_txn_id": src_txn.txn_id,
            "dest_txn_id": dest_txn.txn_id,
        },
        source_ip=get_request_ip(request),
    )
    db.commit()
    return [_to_txn_out(db, src_txn), _to_txn_out(db, dest_txn)]


@router.get("/txns", response_model=List[TxnOut])
def list_txns(
    batch_id: Optional[int] = None,
    material_id: Optional[int] = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    rows = crud.list_txns(db, batch_id=batch_id, material_id=material_id, limit=limit)
    out = []
    for txn, batch_no, mat_id, mat_code, mat_name, loc_name in rows:
        out.append({
            "txn_id": txn.txn_id,
            "batch_id": txn.batch_id,
            "txn_type": txn.txn_type,
            "qty": txn.qty,
            "txn_date": txn.txn_date,
            "operator": txn.operator,
            "purpose": txn.purpose,
            "remark": txn.remark,
            "created_at": txn.created_at,
            "batch_no": batch_no,
            "material_id": mat_id,
            "material_code": mat_code,
            "material_name": mat_name,
            "location_name": loc_name,
        })
    return out


# ---------------- 工具 ----------------
def _to_txn_out(db, txn) -> dict:
    b = txn.batch
    m = b.material if b else None
    loc = b.location if b else None
    return {
        "txn_id": txn.txn_id,
        "batch_id": txn.batch_id,
        "txn_type": txn.txn_type,
        "qty": txn.qty,
        "txn_date": txn.txn_date,
        "operator": txn.operator,
        "purpose": txn.purpose,
        "remark": txn.remark,
        "created_at": txn.created_at,
        "batch_no": b.batch_no if b else None,
        "material_id": m.material_id if m else None,
        "material_code": m.material_code if m else None,
        "material_name": m.name_cn if m else None,
        "location_name": loc.name if loc else None,
    }
