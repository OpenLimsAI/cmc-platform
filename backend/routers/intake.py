"""
文件: backend/routers/intake.py
用途: 批量入库 API(期3, 散放层多行)
说明:
    - 一次提交多行 (物料/批号/有效期/数量/存放位置), 共用入库日期与入库类型。
    - 两遍式: 先逐行校验, 全部通过才在一个事务里写入; 任一行不合法 → 整体不写、回执逐行原因。
    - 命中同 (material, batch_no, location) 的批次 → 追加入库; 否则新建批次。
    - -80℃ 冻存走 /api/storage/occupy(单管占用), 不在本批量接口内。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

import crud
from audit import get_request_ip, write_audit
from database import get_db
from auth import CurrentUser, require_warehouse
from schemas import BulkIntakeRequest, BulkIntakeResult

router = APIRouter(prefix="/api/intake", tags=["intake"])


@router.post("/bulk", response_model=BulkIntakeResult)
def bulk_intake(
    payload: BulkIntakeRequest,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    res = crud.bulk_intake(
        db,
        rows=payload.rows,
        received_date=payload.received_date,
        operator=current.username,
        intake_type=payload.intake_type,
    )
    if not res["ok"]:
        db.rollback()
        return res
    write_audit(
        db, current, "intake.bulk",
        entity_type="batch", entity_id=None,
        before=None,
        after={"created": res["created"], "appended": res["appended"],
               "rows": len(payload.rows)},
        source_ip=get_request_ip(request),
    )
    db.commit()
    return res
