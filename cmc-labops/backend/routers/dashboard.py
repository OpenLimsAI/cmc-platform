"""
文件: backend/routers/dashboard.py
用途: 仪表盘统计 API (UI-LABOPS-001 §4.2 / FR-EQP-063)
路径前缀: /api/dashboard
端点:
    GET /api/dashboard/stats    关键统计(物料数/设备数/活跃批次数)
说明:
    - 预警明细复用既有端点(/api/stock/alerts/* 与 /api/equipment/alerts),
      本路由只补列表页拿不到的聚合计数
    - 活跃批次 = 实时库存(SUM(inventory_txn.qty)) > 0 的批次
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from database import get_db
from models import Material, Batch, InventoryTxn
from models_equipment import Equipment

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class DashboardStats(BaseModel):
    material_count: int        # 启用中的物料数
    equipment_count: int       # 在册(未报废)设备数
    active_batch_count: int    # 实时库存 > 0 的批次数


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)):
    material_count = db.execute(
        select(func.count()).select_from(Material).where(Material.is_active.is_(True))
    ).scalar_one()

    equipment_count = db.execute(
        select(func.count()).select_from(Equipment).where(Equipment.is_active.is_(True))
    ).scalar_one()

    # 活跃批次:按批次聚合流水,SUM(qty) > 0
    qty_sub = (
        select(InventoryTxn.batch_id)
        .group_by(InventoryTxn.batch_id)
        .having(func.sum(InventoryTxn.qty) > 0)
        .subquery()
    )
    active_batch_count = db.execute(
        select(func.count()).select_from(Batch).join(
            qty_sub, Batch.batch_id == qty_sub.c.batch_id
        )
    ).scalar_one()

    return DashboardStats(
        material_count=material_count,
        equipment_count=equipment_count,
        active_batch_count=active_batch_count,
    )
