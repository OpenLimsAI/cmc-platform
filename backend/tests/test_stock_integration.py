"""
文件: backend/tests/test_stock_integration.py
用途: 库存计算关键路径的集成测试,用真实 PG 跑
覆盖:
    - txn 聚合(IN/OUT/ADJUST 累加)
    - 默认排除已过期批次的可用库存口径(README §5.5)
    - 低库存预警触发条件
    - 出库超量被拒绝(API 层)
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import crud


def _make_batch(db, code, batch_no, expiry, qty, loc_id, op="测试"):
    return crud.create_batch_with_initial_in(
        db,
        material_code=code,
        batch_no=batch_no,
        expiry_date=expiry,
        location_id=loc_id,
        received_date=date.today(),
        initial_qty=Decimal(str(qty)),
        operator=op,
        remark=None,
    )


# ---------------------------------------------------------------------------
# 1. txn 聚合
# ---------------------------------------------------------------------------
def test_txn_aggregation_in_out_adjust(db, seed_material):
    code, loc = seed_material
    b = _make_batch(db, code, "B001", date.today() + timedelta(days=180), 100, loc)

    # 再追加 50 入库
    crud.add_in(db, b.batch_id, Decimal("50"), date.today(), "测试", None)
    # 出库 30
    crud.add_out(db, b.batch_id, Decimal("30"), date.today(), "测试", None, None)
    # 调整 -5
    crud.add_adjust(db, b.batch_id, Decimal("-5"), date.today(), "测试", None)

    assert crud.get_batch_qty(db, b.batch_id) == Decimal("115")  # 100+50-30-5

    rows = crud.stock_by_material(db)
    hit = next(r for r in rows if r["material_code"] == code)
    assert hit["total_qty"] == Decimal("115")


# ---------------------------------------------------------------------------
# 2. 已过期批次默认不计入可用总库存(修复 #4 的回归测试)
# ---------------------------------------------------------------------------
def test_expired_batch_excluded_from_total(db, seed_material):
    code, loc = seed_material
    # 一个有效批次 + 一个过期批次
    _make_batch(db, code, "OK",     date.today() + timedelta(days=60), 30, loc)
    _make_batch(db, code, "EXPIRED", date.today() - timedelta(days=1),  70, loc)

    # 默认 exclude_expired=True
    rows_default = crud.stock_by_material(db)
    hit = next(r for r in rows_default if r["material_code"] == code)
    assert hit["total_qty"] == Decimal("30"), "过期批次不应计入可用库存"

    # 显式取全量
    rows_all = crud.stock_by_material(db, exclude_expired=False)
    hit_all = next(r for r in rows_all if r["material_code"] == code)
    assert hit_all["total_qty"] == Decimal("100")


# ---------------------------------------------------------------------------
# 2.5 默认排除零库存物料(v1.1 A.2 回归测试)
# ---------------------------------------------------------------------------
def test_only_positive_default_filters_zero_stock(db, seed_material):
    """seed_material 创建了 1 个物料但没建批次,总库存 = 0;
    默认 only_positive=True 应过滤掉;显式 False 才返回。"""
    code, _ = seed_material

    # 默认行为:零库存物料不出现
    rows_default = crud.stock_by_material(db)
    assert all(r["material_code"] != code for r in rows_default), \
        "only_positive=True(默认)应排除零库存物料"

    # 显式取全量
    rows_all = crud.stock_by_material(db, only_positive=False)
    assert any(r["material_code"] == code for r in rows_all), \
        "only_positive=False 应包含零库存物料"


# ---------------------------------------------------------------------------
# 3. 低库存预警
# ---------------------------------------------------------------------------
def test_low_stock_alert_triggers_when_below_safety(db, seed_material):
    code, loc = seed_material  # safety_stock=100
    _make_batch(db, code, "B1", date.today() + timedelta(days=180), 30, loc)

    alerts = crud.low_stock_alerts(db)
    hit = next((a for a in alerts if a["material_code"] == code), None)
    assert hit is not None, "总库存 30 < 安全库存 100 应触发告警"
    assert hit["gap"] == Decimal("70")


def test_low_stock_alert_silent_when_safety_zero(db, seed_material):
    code, loc = seed_material
    # 把安全库存改为 0
    crud.update_material(db, code, {"safety_stock": Decimal("0")})
    _make_batch(db, code, "B1", date.today() + timedelta(days=180), 0, loc)

    alerts = crud.low_stock_alerts(db)
    assert all(a["material_code"] != code for a in alerts), "safety_stock=0 不应产生低库存告警"


# ---------------------------------------------------------------------------
# 4. 出库超量被 API 拒绝
# ---------------------------------------------------------------------------
def test_out_exceeds_stock_rejected(client, db, seed_material):
    code, loc = seed_material
    b = _make_batch(db, code, "B1", date.today() + timedelta(days=30), 10, loc)

    resp = client.post("/api/inventory/out", json={
        "batch_id": b.batch_id,
        "qty": "20",
        "txn_date": str(date.today()),
        "operator": "测试",
        "purpose": None,
        "remark": None,
    })
    assert resp.status_code == 400
    assert "超过批次现有库存" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 5. 调整后库存为负被拒绝
# ---------------------------------------------------------------------------
def test_adjust_negative_result_rejected(client, db, seed_material):
    code, loc = seed_material
    b = _make_batch(db, code, "B1", date.today() + timedelta(days=30), 5, loc)

    resp = client.post("/api/inventory/adjust", json={
        "batch_id": b.batch_id,
        "qty": "-10",
        "txn_date": str(date.today()),
        "operator": "测试",
        "remark": None,
    })
    assert resp.status_code == 400
    assert "调整后库存为负" in resp.json()["detail"]
