"""
文件: backend/routers/inventory.py
用途: 出入库流水 API:对已有批次追加入库 / 出库 / 调整 / 流水查询
约束:
    - 出库数量不可超过批次实时库存
    - 调整无强制约束(允许将库存从 5 调到 4),但若结果为负数会拒绝
"""
from __future__ import annotations

from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import crud
from database import get_db
from schemas import (
    TxnInRequest,
    TxnOutRequest,
    TxnAdjustRequest,
    TxnOut,
)

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.post("/in", response_model=TxnOut)
def receive_in(payload: TxnInRequest, db: Session = Depends(get_db)):
    """已有批次追加入库。"""
    b = crud.get_batch(db, payload.batch_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"批次 {payload.batch_id} 不存在")
    txn = crud.add_in(
        db, payload.batch_id, payload.qty, payload.txn_date, payload.operator, payload.remark
    )
    return _to_txn_out(db, txn)


@router.post("/out", response_model=TxnOut)
def issue_out(payload: TxnOutRequest, db: Session = Depends(get_db)):
    """从指定批次出库。"""
    b = crud.get_batch(db, payload.batch_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"批次 {payload.batch_id} 不存在")
    current = crud.get_batch_qty(db, payload.batch_id)
    if payload.qty > current:
        raise HTTPException(
            status_code=400,
            detail=f"出库数量 {payload.qty} 超过批次现有库存 {current}",
        )
    txn = crud.add_out(
        db, payload.batch_id, payload.qty, payload.txn_date,
        payload.operator, payload.purpose, payload.remark,
    )
    return _to_txn_out(db, txn)


@router.post("/adjust", response_model=TxnOut)
def adjust(payload: TxnAdjustRequest, db: Session = Depends(get_db)):
    """盘点调整,可正可负;但调整后批次库存不得 < 0。"""
    b = crud.get_batch(db, payload.batch_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"批次 {payload.batch_id} 不存在")
    current = crud.get_batch_qty(db, payload.batch_id)
    if current + payload.qty < 0:
        raise HTTPException(
            status_code=400,
            detail=f"调整后库存为负({current} + {payload.qty} < 0),已拒绝",
        )
    txn = crud.add_adjust(
        db, payload.batch_id, payload.qty, payload.txn_date, payload.operator, payload.remark
    )
    return _to_txn_out(db, txn)


@router.get("/txns", response_model=List[TxnOut])
def list_txns(
    batch_id: Optional[int] = None,
    material_code: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    rows = crud.list_txns(db, batch_id=batch_id, material_code=material_code, limit=limit)
    out = []
    for txn, batch_no, mat_code, mat_name in rows:
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
            "material_code": mat_code,
            "material_name": mat_name,
        })
    return out


# ---------------- 工具 ----------------
def _to_txn_out(db, txn) -> dict:
    b = txn.batch
    m = b.material if b else None
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
        "material_code": b.material_code if b else None,
        "material_name": m.name_cn if m else None,
    }
