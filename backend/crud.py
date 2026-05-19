"""
文件: backend/crud.py
用途: 通用数据访问层(查询/聚合/UPSERT)
原则:
    - 库存数量永远从 inventory_txn 实时聚合,绝不缓存到 batch
    - 所有金额/数量字段使用 Decimal
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, List, Tuple, Sequence

from sqlalchemy import select, func, and_, or_, case, exists
from sqlalchemy.orm import Session

from models import (
    Material,
    Batch,
    InventoryTxn,
    Location,
    UnitDict,
    CategoryDict,
)
from schemas import TT_INTERNAL_CODE


def severity_of(days_to_expiry: int, warning_threshold: int = 90) -> Optional[str]:
    """根据剩余天数判断效期严重度(README §5.5 规则)。
    返回 EXPIRED / URGENT / WARNING / None(超出 threshold 不告警)。
    单独抽出便于单测。
    """
    if days_to_expiry < 0:
        return "EXPIRED"
    if days_to_expiry <= 30:
        return "URGENT"
    if days_to_expiry <= warning_threshold:
        return "WARNING"
    return None


# ---------------------------------------------------------------------------
# Material
# ---------------------------------------------------------------------------
def list_materials(
    db: Session,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    is_active: Optional[bool] = None,
    include_inactive: bool = False,
) -> List[Material]:
    """物料列表查询。
    - is_active: 显式指定 True/False;若 None 且 include_inactive=False,则只查 active
    - keyword 同时匹配 material_code 与 name_cn
    """
    stmt = select(Material)

    if is_active is True:
        stmt = stmt.where(Material.is_active.is_(True))
    elif is_active is False:
        stmt = stmt.where(Material.is_active.is_(False))
    elif not include_inactive:
        stmt = stmt.where(Material.is_active.is_(True))

    if category:
        stmt = stmt.where(Material.category == category)

    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(Material.material_code.ilike(kw), Material.name_cn.ilike(kw)))

    stmt = stmt.order_by(Material.material_code, Material.material_id)
    return list(db.execute(stmt).scalars().all())


def get_material(db: Session, material_id: int) -> Optional[Material]:
    """主键查询(material_id)。TT 例外下 material_code 不再唯一,所有 mutate
    都走 material_id。"""
    return db.get(Material, material_id)


def get_material_by_code(db: Session, code: str) -> Optional[Material]:
    """便利方法:按 code 取首条(给导入/测试用,业务路由请走 id)。"""
    return db.execute(
        select(Material).where(Material.material_code == code)
        .order_by(Material.material_id).limit(1)
    ).scalar_one_or_none()


def create_material(db: Session, data: dict) -> Material:
    """单条创建物料(供「物料管理」页"新增"按钮用)。
    校验:
        - material_code 不能为空
        - material_code 不能与已有冲突 —— 但保留值 'TT内部物料' 例外,允许重复
        - unit 必须在 unit_dict 中(否则 FK 报错)
        - category 若为新值,自动追加到 category_dict(与 Excel 导入流程一致)
    上层 router 把业务异常翻成 HTTPException。
    """
    code = data.get("material_code")
    if not code:
        raise ValueError("material_code 不能为空")

    # TT 内部物料不做唯一性检查;其他 code 检查冲突
    if code != TT_INTERNAL_CODE:
        existing = db.execute(
            select(Material.material_id).where(Material.material_code == code).limit(1)
        ).scalar_one_or_none()
        if existing:
            raise ValueError(f"物料代码 {code} 已存在,请改用「编辑物料」修改信息")

    unit = data.get("unit")
    if not unit:
        raise ValueError("unit 不能为空")
    if not db.get(UnitDict, unit):
        raise ValueError(f"单位 '{unit}' 不在字典中,请先维护单位字典")

    category = data.get("category")
    if category and not db.get(CategoryDict, category):
        # 与导入流程一致:文件中遇到新分类自动加入字典
        db.add(CategoryDict(category=category))

    obj = Material(
        material_code=code,
        category=category,
        name_cn=data["name_cn"],
        grade=data.get("grade"),
        manufacturer=data.get("manufacturer"),
        spec_model=data.get("spec_model"),
        catalog_no=data.get("catalog_no"),
        unit=unit,
        package_spec=data.get("package_spec"),
        hazard_class=data.get("hazard_class"),
        remark=data.get("remark"),
        safety_stock=data.get("safety_stock") or Decimal("0"),
        is_active=True,
        import_batch_id=None,  # 手工录入,不挂导入批次
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_material(db: Session, material_id: int, data: dict) -> Optional[Material]:
    """按 material_id 更新。data 来自 router 的 model_dump(exclude_unset=True),
    每个 key 都是用户显式传的字段;value=None 视为"清空"。
    若 category 改为字典中尚未存在的新值,自动加入 category_dict
    (与 create_material 行为一致)。
    """
    obj = db.get(Material, material_id)
    if not obj:
        return None

    new_cat = data.get("category")
    if new_cat and not db.get(CategoryDict, new_cat):
        db.add(CategoryDict(category=new_cat))

    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def deactivate_material(
    db: Session, material_id: int, operator: str, reason: Optional[str]
) -> Optional[Material]:
    obj = db.get(Material, material_id)
    if not obj:
        return None
    obj.is_active = False
    # 用 PG 服务器时间,与其他时间字段(created_at/updated_at)统一时区口径
    obj.deactivated_at = func.now()
    obj.deactivated_by = operator
    obj.deactivate_reason = reason
    db.commit()
    db.refresh(obj)
    return obj


def activate_material(db: Session, material_id: int) -> Optional[Material]:
    obj = db.get(Material, material_id)
    if not obj:
        return None
    obj.is_active = True
    obj.deactivated_at = None
    obj.deactivated_by = None
    obj.deactivate_reason = None
    db.commit()
    db.refresh(obj)
    return obj


# ---------------------------------------------------------------------------
# Dictionary
# ---------------------------------------------------------------------------
def list_units(db: Session) -> List[UnitDict]:
    return list(db.execute(select(UnitDict).order_by(UnitDict.unit)).scalars().all())


def list_categories(db: Session) -> List[str]:
    rows = db.execute(select(CategoryDict.category).order_by(CategoryDict.category)).all()
    return [r[0] for r in rows]


def upsert_units(db: Session, units: List[str]) -> None:
    for u in units:
        if not u:
            continue
        if not db.get(UnitDict, u):
            db.add(UnitDict(unit=u, description=u))
    db.commit()


def upsert_categories(db: Session, categories: List[str]) -> None:
    for c in categories:
        if not c:
            continue
        if not db.get(CategoryDict, c):
            db.add(CategoryDict(category=c))
    db.commit()


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------
def list_locations(db: Session) -> List[Location]:
    return list(db.execute(
        select(Location).order_by(Location.room_no, Location.cabinet_no, Location.layer_no)
    ).scalars().all())


def create_location(
    db: Session, room_no: str, cabinet_no: str, layer_no: int,
    storage_condition: Optional[str], remark: Optional[str],
) -> Location:
    obj = Location(
        room_no=room_no,
        cabinet_no=cabinet_no,
        layer_no=layer_no,
        storage_condition=storage_condition,
        remark=remark,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------
def list_batches(
    db: Session,
    material_id: Optional[int] = None,
    only_with_stock: bool = False,
    include_expired: bool = True,
) -> List[Tuple[Batch, Decimal, Optional[str], Optional[str], Optional[str], Optional[str]]]:
    """返回 (Batch, current_qty, location_name, material_code, material_name, unit) 元组列表。"""
    qty_subq = (
        select(InventoryTxn.batch_id, func.coalesce(func.sum(InventoryTxn.qty), 0).label("current_qty"))
        .group_by(InventoryTxn.batch_id)
        .subquery()
    )

    stmt = (
        select(
            Batch,
            func.coalesce(qty_subq.c.current_qty, 0).label("current_qty"),
            Location.name.label("location_name"),
            Material.material_code.label("material_code"),
            Material.name_cn.label("material_name"),
            Material.unit.label("unit"),
        )
        .join(Material, Material.material_id == Batch.material_id)
        .outerjoin(qty_subq, qty_subq.c.batch_id == Batch.batch_id)
        .join(Location, Location.location_id == Batch.location_id)
    )

    if material_id is not None:
        stmt = stmt.where(Batch.material_id == material_id)
    if only_with_stock:
        stmt = stmt.where(func.coalesce(qty_subq.c.current_qty, 0) > 0)
    if not include_expired:
        today = date.today()
        stmt = stmt.where(or_(Batch.expiry_date.is_(None), Batch.expiry_date >= today))

    stmt = stmt.order_by(
        Material.material_code,
        # 效期升序(NULL 放最后)
        Batch.expiry_date.asc().nullslast(),
        Batch.batch_id,
    )
    return [tuple(r) for r in db.execute(stmt).all()]


def get_batch(db: Session, batch_id: int) -> Optional[Batch]:
    return db.get(Batch, batch_id)


def get_batch_qty(db: Session, batch_id: int) -> Decimal:
    """实时聚合该批次当前库存。"""
    val = db.execute(
        select(func.coalesce(func.sum(InventoryTxn.qty), 0)).where(InventoryTxn.batch_id == batch_id)
    ).scalar_one()
    return Decimal(val) if val is not None else Decimal("0")


def find_batch_at_location(
    db: Session, material_id: int, batch_no: str, location_id: int,
) -> Optional[Batch]:
    """按三键 (material_id, batch_no, location_id) 找批次。
    入库时用:若命中 → 追加流水;若未命中但 (material_id, batch_no) 在别处有
    → 在新位置创建一条同号批次行(支持"同批号散落多柜")。
    """
    return db.execute(
        select(Batch).where(and_(
            Batch.material_id == material_id,
            Batch.batch_no == batch_no,
            Batch.location_id == location_id,
        ))
    ).scalar_one_or_none()


def create_batch_with_initial_in(
    db: Session,
    material_id: int,
    batch_no: str,
    expiry_date,
    location_id: int,
    received_date,
    initial_qty: Decimal,
    operator: str,
    remark: Optional[str],
    intake_type: Optional[str] = None,
    concentration: Optional[str] = None,
    extinction_coefficient: Optional[str] = None,
    serial_no: Optional[str] = None,
    asset_no: Optional[str] = None,
    responsible_person: Optional[str] = None,
) -> Batch:
    """新建批次并同步写入首笔入库 txn(IN)。"""
    b = Batch(
        material_id=material_id,
        batch_no=batch_no,
        expiry_date=expiry_date,
        location_id=location_id,
        received_date=received_date,
        initial_qty=initial_qty,
        remark=remark,
        intake_type=intake_type,
        concentration=concentration,
        extinction_coefficient=extinction_coefficient,
        serial_no=serial_no,
        asset_no=asset_no,
        responsible_person=responsible_person,
    )
    db.add(b)
    db.flush()  # 获得 batch_id

    txn = InventoryTxn(
        batch_id=b.batch_id,
        txn_type="IN",
        qty=initial_qty,
        txn_date=received_date,
        operator=operator,
        purpose=None,
        remark="批次创建-首次入库",
    )
    db.add(txn)
    db.commit()
    db.refresh(b)
    return b


# ---------------------------------------------------------------------------
# Inventory Txn
# ---------------------------------------------------------------------------
def add_in(db: Session, batch_id: int, qty: Decimal, txn_date, operator: str, remark: Optional[str]) -> InventoryTxn:
    txn = InventoryTxn(
        batch_id=batch_id, txn_type="IN", qty=qty, txn_date=txn_date,
        operator=operator, remark=remark,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def add_out(
    db: Session, batch_id: int, qty: Decimal, txn_date, operator: str,
    purpose: Optional[str], remark: Optional[str],
) -> InventoryTxn:
    """出库:qty 取负值落库。"""
    txn = InventoryTxn(
        batch_id=batch_id, txn_type="OUT", qty=-abs(qty), txn_date=txn_date,
        operator=operator, purpose=purpose, remark=remark,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def add_adjust(
    db: Session, batch_id: int, qty: Decimal, txn_date, operator: str, remark: Optional[str]
) -> InventoryTxn:
    """调整:qty 可正可负,直接落库。"""
    txn = InventoryTxn(
        batch_id=batch_id, txn_type="ADJUST", qty=qty, txn_date=txn_date,
        operator=operator, remark=remark,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def transfer_batch(
    db: Session, source_batch_id: int, dest_location_id: int,
    qty: Decimal, operator: str, txn_date, remark: Optional[str],
) -> Tuple[InventoryTxn, InventoryTxn, Batch]:
    """从源批次搬 qty 到目的位置(同物料同批号)。
    返回 (source_out_txn, dest_in_txn, dest_batch)。
    业务异常以 ValueError 抛,由 router 转 400。原子事务。
    """
    src = db.get(Batch, source_batch_id)
    if not src:
        raise ValueError(f"源批次 {source_batch_id} 不存在")
    if dest_location_id == src.location_id:
        raise ValueError("目的位置与源位置相同,无需移库")
    dest_loc = db.get(Location, dest_location_id)
    if not dest_loc:
        raise ValueError(f"目的位置 {dest_location_id} 不存在")
    current = get_batch_qty(db, source_batch_id)
    if qty > current:
        raise ValueError(f"移库数量 {qty} 超过源批次现有库存 {current}")

    # 目的位置有同 (material_id, batch_no) 批次 → 复用;否则新建
    dest = find_batch_at_location(db, src.material_id, src.batch_no, dest_location_id)
    if dest is None:
        dest = Batch(
            material_id=src.material_id,
            batch_no=src.batch_no,
            expiry_date=src.expiry_date,
            location_id=dest_location_id,
            received_date=src.received_date,
            initial_qty=Decimal("0"),  # 真实数量靠下面的 IN txn 累计
            remark=f"由移库自动建,源批次 #{source_batch_id}",
        )
        db.add(dest)
        db.flush()

    src_loc_name = src.location.name if src.location else f"#{src.location_id}"
    dest_loc_name = dest_loc.name

    src_txn = InventoryTxn(
        batch_id=source_batch_id, txn_type="OUT", qty=-abs(qty),
        txn_date=txn_date, operator=operator,
        purpose=f"移库 → {dest_loc_name}",
        remark=remark,
    )
    dest_txn = InventoryTxn(
        batch_id=dest.batch_id, txn_type="IN", qty=abs(qty),
        txn_date=txn_date, operator=operator,
        purpose=f"移库 ← {src_loc_name}",
        remark=remark,
    )
    db.add(src_txn)
    db.add(dest_txn)
    db.commit()
    db.refresh(src_txn); db.refresh(dest_txn); db.refresh(dest)
    return src_txn, dest_txn, dest


def list_txns(
    db: Session,
    batch_id: Optional[int] = None,
    material_id: Optional[int] = None,
    limit: int = 200,
):
    stmt = (
        select(
            InventoryTxn,
            Batch.batch_no,
            Batch.intake_type,
            Batch.concentration,
            Batch.extinction_coefficient,
            Batch.serial_no,
            Batch.asset_no,
            Batch.responsible_person,
            Material.material_id,
            Material.material_code,
            Material.name_cn,
            Location.name.label("location_name"),
        )
        .join(Batch, Batch.batch_id == InventoryTxn.batch_id)
        .join(Material, Material.material_id == Batch.material_id)
        .join(Location, Location.location_id == Batch.location_id)
    )
    if batch_id is not None:
        stmt = stmt.where(InventoryTxn.batch_id == batch_id)
    if material_id is not None:
        stmt = stmt.where(Batch.material_id == material_id)
    stmt = stmt.order_by(InventoryTxn.txn_id.desc()).limit(limit)
    return [tuple(r) for r in db.execute(stmt).all()]


# ---------------------------------------------------------------------------
# Stock 聚合 / 预警
# ---------------------------------------------------------------------------
def stock_by_material(
    db: Session,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    include_inactive: bool = False,
    exclude_expired: bool = True,
    only_positive: bool = True,
) -> List[dict]:
    """物料级总库存(实时聚合 inventory_txn)。
    exclude_expired=True 时,已过期批次的 txn 不计入「可用总库存」(README §5.5 规则);
    需要含过期的全量库存时显式传 False。
    only_positive=True(默认)时,只返回总库存 > 0 的物料 —— 默认就是用户最常看
    的"在库视图";勾"包含零库存"再传 False 看完整目录。
    """
    qty_subq_inner = (
        select(
            Batch.material_id.label("material_id"),
            func.coalesce(func.sum(InventoryTxn.qty), 0).label("total_qty"),
        )
        .join(InventoryTxn, InventoryTxn.batch_id == Batch.batch_id)
    )
    if exclude_expired:
        today = date.today()
        qty_subq_inner = qty_subq_inner.where(
            or_(Batch.expiry_date.is_(None), Batch.expiry_date >= today)
        )
    qty_subq = qty_subq_inner.group_by(Batch.material_id).subquery()

    stmt = (
        select(
            Material.material_id,
            Material.material_code,
            Material.name_cn,
            Material.category,
            Material.unit,
            Material.is_active,
            Material.safety_stock,
            func.coalesce(qty_subq.c.total_qty, 0).label("total_qty"),
        )
        .outerjoin(qty_subq, qty_subq.c.material_id == Material.material_id)
    )
    if not include_inactive:
        stmt = stmt.where(Material.is_active.is_(True))
    if category:
        stmt = stmt.where(Material.category == category)
    if keyword:
        kw = f"%{keyword}%"
        # 关键字命中范围:物料代码 / 物料名 / "该物料下任一批次的批号" 之一
        batch_match = exists().where(and_(
            Batch.material_id == Material.material_id,
            Batch.batch_no.ilike(kw),
        ))
        stmt = stmt.where(or_(
            Material.material_code.ilike(kw),
            Material.name_cn.ilike(kw),
            batch_match,
        ))
    stmt = stmt.order_by(Material.material_code, Material.material_id)

    out = []
    for row in db.execute(stmt).all():
        total_qty = Decimal(row.total_qty)
        if only_positive and total_qty <= 0:
            continue
        safety = Decimal(row.safety_stock or 0)
        low = bool(safety > 0 and total_qty < safety)
        out.append({
            "material_id": row.material_id,
            "material_code": row.material_code,
            "name_cn": row.name_cn,
            "category": row.category,
            "unit": row.unit,
            "is_active": row.is_active,
            "safety_stock": safety,
            "total_qty": total_qty,
            "low_stock": low,
        })
    return out


def stock_by_batch(
    db: Session,
    category: Optional[str] = None,
    material_id: Optional[int] = None,
    location_id: Optional[int] = None,
    keyword: Optional[str] = None,
    include_inactive: bool = False,
    include_expired: bool = True,
    only_positive: bool = True,
) -> List[dict]:
    """批次级当前库存(每行 = 一个 (material, batch_no, location) 的物理批次)。
    keyword 同时匹配 物料代码 / 物料名 / 批号(单一搜索框)。"""
    qty_subq = (
        select(InventoryTxn.batch_id, func.coalesce(func.sum(InventoryTxn.qty), 0).label("current_qty"))
        .group_by(InventoryTxn.batch_id)
        .subquery()
    )

    stmt = (
        select(
            Batch.batch_id,
            Material.material_id,
            Material.material_code,
            Material.name_cn,
            Material.unit,
            Batch.batch_no,
            Batch.expiry_date,
            Batch.location_id,
            Location.name.label("location_name"),
            Batch.received_date,
            func.coalesce(qty_subq.c.current_qty, 0).label("current_qty"),
            Material.is_active,
            Material.category,
        )
        .join(Material, Material.material_id == Batch.material_id)
        .outerjoin(qty_subq, qty_subq.c.batch_id == Batch.batch_id)
        .join(Location, Location.location_id == Batch.location_id)
    )
    if category:
        stmt = stmt.where(Material.category == category)
    if material_id is not None:
        stmt = stmt.where(Batch.material_id == material_id)
    if location_id is not None:
        stmt = stmt.where(Batch.location_id == location_id)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(or_(
            Material.material_code.ilike(kw),
            Material.name_cn.ilike(kw),
            Batch.batch_no.ilike(kw),
        ))
    if not include_inactive:
        stmt = stmt.where(Material.is_active.is_(True))
    if not include_expired:
        today = date.today()
        stmt = stmt.where(or_(Batch.expiry_date.is_(None), Batch.expiry_date >= today))
    if only_positive:
        stmt = stmt.where(func.coalesce(qty_subq.c.current_qty, 0) > 0)

    stmt = stmt.order_by(
        Material.material_code, Batch.expiry_date.asc().nullslast(), Batch.batch_id
    )

    today = date.today()
    out = []
    for r in db.execute(stmt).all():
        days = (r.expiry_date - today).days if r.expiry_date else None
        out.append({
            "batch_id": r.batch_id,
            "material_id": r.material_id,
            "material_code": r.material_code,
            "name_cn": r.name_cn,
            "unit": r.unit,
            "batch_no": r.batch_no,
            "expiry_date": r.expiry_date,
            "location_id": r.location_id,
            "location_name": r.location_name,
            "received_date": r.received_date,
            "current_qty": Decimal(r.current_qty),
            "days_to_expiry": days,
            "is_active": r.is_active,
        })
    return out


def expiry_alerts(db: Session, days: int = 90) -> List[dict]:
    """效期预警:已过期 + 即将过期(days 天内)。"""
    today = date.today()
    qty_subq = (
        select(InventoryTxn.batch_id, func.coalesce(func.sum(InventoryTxn.qty), 0).label("current_qty"))
        .group_by(InventoryTxn.batch_id)
        .subquery()
    )
    stmt = (
        select(
            Batch.batch_id,
            Material.material_id,
            Material.material_code,
            Material.name_cn,
            Material.unit,
            Batch.batch_no,
            Batch.expiry_date,
            Location.name.label("location_name"),
            func.coalesce(qty_subq.c.current_qty, 0).label("current_qty"),
        )
        .join(Material, Material.material_id == Batch.material_id)
        .outerjoin(qty_subq, qty_subq.c.batch_id == Batch.batch_id)
        .join(Location, Location.location_id == Batch.location_id)
        .where(
            and_(
                Batch.expiry_date.is_not(None),
                func.coalesce(qty_subq.c.current_qty, 0) > 0,
                Material.is_active.is_(True),
            )
        )
        .order_by(Batch.expiry_date.asc())
    )
    out = []
    for r in db.execute(stmt).all():
        d = (r.expiry_date - today).days
        sev = severity_of(d, warning_threshold=days)
        if sev is None:
            continue
        out.append({
            "batch_id": r.batch_id,
            "material_id": r.material_id,
            "material_code": r.material_code,
            "name_cn": r.name_cn,
            "unit": r.unit,
            "batch_no": r.batch_no,
            "expiry_date": r.expiry_date,
            "days_to_expiry": d,
            "current_qty": Decimal(r.current_qty),
            "location_name": r.location_name,
            "severity": sev,
        })
    return out


def low_stock_alerts(db: Session) -> List[dict]:
    """低库存预警:total_qty < safety_stock 且 safety_stock > 0,只看在用物料。
    显式传 only_positive=False,确保 0 库存物料也参与预警判断
    (零库存 < safety_stock 是最该报警的情况)。"""
    rows = stock_by_material(db, include_inactive=False, only_positive=False)
    return [
        {
            "material_id": r["material_id"],
            "material_code": r["material_code"],
            "name_cn": r["name_cn"],
            "unit": r["unit"],
            "safety_stock": r["safety_stock"],
            "total_qty": r["total_qty"],
            "gap": r["safety_stock"] - r["total_qty"],
        }
        for r in rows
        if r["low_stock"]
    ]
