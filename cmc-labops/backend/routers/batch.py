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

from datetime import datetime
from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

import crud
from audit import get_request_ip, model_snapshot, write_audit
from database import get_db
from auth import CurrentUser, require_warehouse, verify_reviewer
from models import InventoryTxn
from schemas import BatchCreate, BatchOut, BatchMetaUpdate

# 复核人需具备的角色(库管理员或系统管理员)
REVIEWER_ALLOWED_ROLES = {"SYS_ADMIN", "CMC_WAREHOUSE_ADMIN"}

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
            "intake_type": batch.intake_type,
            "concentration": batch.concentration,
            "extinction_coefficient": batch.extinction_coefficient,
            "serial_no": batch.serial_no,
            "asset_no": batch.asset_no,
            "responsible_person": batch.responsible_person,
            "project_no": batch.project_no,
            "originator_batch_no": batch.originator_batch_no,
            "aliquot_date": batch.aliquot_date,
            "aliquot_spec": batch.aliquot_spec,
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
    current: CurrentUser = Depends(require_warehouse),
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
    try:
        crud.assert_not_freezer_anchor(db, payload.location_id)
        crud.assert_location_active(db, payload.location_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
        intake_operator_name=current.full_name,
        remark=payload.remark,
        intake_type=payload.intake_type,
        concentration=payload.concentration,
        extinction_coefficient=payload.extinction_coefficient,
        serial_no=payload.serial_no,
        asset_no=payload.asset_no,
        responsible_person=payload.responsible_person,
        project_no=payload.project_no,
        originator_batch_no=payload.originator_batch_no,
        aliquot_date=payload.aliquot_date,
        aliquot_spec=payload.aliquot_spec,
    )
    write_audit(
        db, current, "batch.create",
        entity_type="batch", entity_id=batch.batch_id,
        before=None, after=model_snapshot(batch),
        source_ip=get_request_ip(request),
    )
    # 首笔 IN 流水单独落审计("所有写操作落 audit_log"——流水也是一条写入)
    initial_txn = db.execute(
        select(InventoryTxn).where(InventoryTxn.batch_id == batch.batch_id)
        .order_by(InventoryTxn.txn_id)
    ).scalars().first()
    if initial_txn:
        write_audit(
            db, current, "inventory.in",
            entity_type="inventory_txn", entity_id=initial_txn.txn_id,
            before=None, after=model_snapshot(initial_txn),
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
        "intake_type": batch.intake_type,
        "concentration": batch.concentration,
        "extinction_coefficient": batch.extinction_coefficient,
        "serial_no": batch.serial_no,
        "asset_no": batch.asset_no,
        "responsible_person": batch.responsible_person,
        "project_no": batch.project_no,
        "originator_batch_no": batch.originator_batch_no,
        "aliquot_date": batch.aliquot_date,
        "aliquot_spec": batch.aliquot_spec,
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
        "intake_type": b.intake_type,
        "concentration": b.concentration,
        "extinction_coefficient": b.extinction_coefficient,
        "serial_no": b.serial_no,
        "asset_no": b.asset_no,
        "responsible_person": b.responsible_person,
        "project_no": b.project_no,
        "originator_batch_no": b.originator_batch_no,
        "aliquot_date": b.aliquot_date,
        "aliquot_spec": b.aliquot_spec,
        "created_at": b.created_at,
        "current_qty": qty,
        "location_name": crud.batch_cell_location_names(db, [b.batch_id]).get(b.batch_id)
        or (b.location.name if b.location else None),
        "material_code": b.material.material_code if b.material else None,
        "material_name": b.material.name_cn if b.material else None,
        "unit": b.material.unit if b.material else None,
    }


@router.patch("/{batch_id}", response_model=BatchOut)
def update_batch(
    batch_id: int,
    payload: BatchMetaUpdate,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """修改批次元信息 —— 需第二位库管员/管理员当场电子签名复核(四眼原则)。
    可改:有效期/原研药批号/浓度/消光系数/序列号/资产编号/负责人/项目编号/分装日期/入库日期/备注。
    不可改:批号(身份)、数量(走盘点调整)、位置(走移库)。"""
    b = crud.get_batch(db, batch_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"批次 {batch_id} 不存在")

    # 只取显式提交的、且排除复核凭据的字段
    changes = payload.model_dump(
        exclude_unset=True,
        exclude={"reviewer_username", "reviewer_password"},
    )
    if not changes:
        raise HTTPException(status_code=400, detail="没有要修改的字段")
    if "received_date" in changes and changes["received_date"] is None:
        raise HTTPException(status_code=400, detail="入库日期不能为空")
    # 丢掉"值没变"的字段(前端数字/字符串格式差异会误报改动,如 1.5 与 "1.50"),
    # 以免为一次空操作消耗复核人签名并写审计
    changes = {k: v for k, v in changes.items() if getattr(b, k, None) != v}
    if not changes:
        raise HTTPException(status_code=400, detail="没有任何改动")

    # 复核签名:第二位库管员/管理员凭据 → 向 MDM 验证身份
    reviewer = verify_reviewer(payload.reviewer_username, payload.reviewer_password)
    if reviewer.user_id == current.user_id:
        raise HTTPException(
            status_code=400, detail="复核人不能是修改本人,请由第二位库管员复核"
        )
    if not (set(reviewer.roles) & REVIEWER_ALLOWED_ROLES):
        raise HTTPException(
            status_code=403, detail="复核人需具备库管理员或系统管理员权限"
        )

    before = model_snapshot(b)
    crud.update_batch_meta(db, b, changes)
    after = model_snapshot(b)
    after["__review_signature__"] = {
        "reviewer_id": reviewer.user_id,
        "reviewer_name": reviewer.username,
        "meaning": "批次信息修改二人复核确认",
        "signed_at": datetime.now().isoformat(),
    }
    write_audit(
        db, current, "batch.update",
        entity_type="batch", entity_id=batch_id,
        before=before, after=after,
        source_ip=get_request_ip(request),
    )
    db.commit()
    db.refresh(b)
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
        "intake_type": b.intake_type,
        "concentration": b.concentration,
        "extinction_coefficient": b.extinction_coefficient,
        "serial_no": b.serial_no,
        "asset_no": b.asset_no,
        "responsible_person": b.responsible_person,
        "project_no": b.project_no,
        "originator_batch_no": b.originator_batch_no,
        "aliquot_date": b.aliquot_date,
        "aliquot_spec": b.aliquot_spec,
        "created_at": b.created_at,
        "current_qty": qty,
        "location_name": crud.batch_cell_location_names(db, [b.batch_id]).get(b.batch_id)
        or (b.location.name if b.location else None),
        "material_code": b.material.material_code if b.material else None,
        "material_name": b.material.name_cn if b.material else None,
        "unit": b.material.unit if b.material else None,
    }
