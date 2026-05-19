"""
文件: backend/routers/stock.py
用途: 库存查询与预警 API
    - by-material:物料级总库存
    - by-batch:批次级当前库存
    - alerts/expiry:效期预警(EXPIRED/URGENT/WARNING)
    - alerts/low-stock:低库存预警
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import crud
from database import get_db
from schemas import StockByMaterial, StockByBatch, ExpiryAlert, LowStockAlert

router = APIRouter(prefix="/api/stock", tags=["stock"])


@router.get("/by-material", response_model=List[StockByMaterial])
def by_material(
    category: Optional[str] = None,
    material_type: Optional[str] = None,
    keyword: Optional[str] = None,
    include_inactive: bool = False,
    exclude_expired: bool = True,
    only_positive: bool = True,
    db: Session = Depends(get_db),
):
    """物料级总库存。
    - 默认排除已过期批次(可用库存口径,README §5.5)
    - 默认 only_positive=True,只返回总库存 > 0 的物料(用户日常视图);
      勾"包含零库存"传 False 看完整目录
    - material_type: 按入库大类筛选 (reagent/consumable/standard/column)
    """
    return crud.stock_by_material(
        db, category, keyword, include_inactive,
        exclude_expired=exclude_expired,
        only_positive=only_positive,
        material_type=material_type,
    )


@router.get("/by-batch", response_model=List[StockByBatch])
def by_batch(
    category: Optional[str] = None,
    material_type: Optional[str] = None,
    material_id: Optional[int] = None,
    location_id: Optional[int] = None,
    keyword: Optional[str] = None,
    include_inactive: bool = False,
    include_expired: bool = True,
    only_positive: bool = True,
    db: Session = Depends(get_db),
):
    return crud.stock_by_batch(
        db,
        category=category,
        material_id=material_id,
        location_id=location_id,
        keyword=keyword,
        include_inactive=include_inactive,
        include_expired=include_expired,
        only_positive=only_positive,
        material_type=material_type,
    )


@router.get("/alerts/expiry", response_model=List[ExpiryAlert])
def alerts_expiry(
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
):
    return crud.expiry_alerts(db, days=days)


@router.get("/alerts/low-stock", response_model=List[LowStockAlert])
def alerts_low_stock(db: Session = Depends(get_db)):
    return crud.low_stock_alerts(db)
