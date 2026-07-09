"""
文件: backend/crud.py
用途: 通用数据访问层(查询/聚合/UPSERT)
原则:
    - 库存数量永远从 inventory_txn 实时聚合,绝不缓存到 batch
    - 所有金额/数量字段使用 Decimal
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Tuple, Sequence

from sqlalchemy import select, func, and_, or_, case, exists, text, delete, insert
from sqlalchemy.orm import Session

from models import (
    Material,
    Batch,
    InventoryTxn,
    Location,
    StorageNode,
    CellOccupancy,
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
_MATERIAL_SEARCH_COLUMNS = (
    Material.material_code,
    Material.name_cn,
    Material.manufacturer,
    Material.spec_model,
    Material.catalog_no,
)


def _build_keyword_pattern(token: str) -> str:
    """把用户输入的单个关键词转成 ILIKE 模式。
    - SQL 通配符 % 和 _ 在原文中先转义,避免误匹配
    - 用户的 * 视作通配符,翻译成 %
    - 不含 * 时按子串匹配 (%kw%)
    """
    token = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    if "*" in token:
        return token.replace("*", "%")
    return f"%{token}%"


def list_materials(
    db: Session,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    is_active: Optional[bool] = None,
    include_inactive: bool = False,
) -> List[Material]:
    """物料列表查询。
    - is_active: 显式指定 True/False;若 None 且 include_inactive=False,则只查 active
    - keyword: 在 物料代码/名称/生产商/规格/货号 5 列中模糊匹配(ILIKE 大小写不敏感)
              空格分隔多关键词时,所有词都要命中(AND),每个词在任一列命中即可(OR)
              支持 * 作为通配符 (例 "ABC*123" 匹配 ABC 开头 123 结尾)
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
        for token in keyword.split():
            pattern = _build_keyword_pattern(token)
            stmt = stmt.where(
                or_(*(col.ilike(pattern, escape="\\") for col in _MATERIAL_SEARCH_COLUMNS))
            )

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
        data_source=data.get("data_source", "local"),
    )
    db.add(obj)
    db.flush()
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
    db.flush()
    db.refresh(obj)
    return obj


def deactivate_material(
    db: Session, material_id: int, operator: str, reason: Optional[str]
) -> Optional[Material]:
    obj = db.get(Material, material_id)
    if not obj:
        return None
    obj.is_active = False
    # 裸上海墙钟,与其他时间字段(created_at/updated_at)统一时区口径
    obj.deactivated_at = datetime.now()
    obj.deactivated_by = operator
    obj.deactivate_reason = reason
    db.flush()
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
    db.flush()
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
    db.flush()
    db.refresh(obj)
    return obj


# ---------------------------------------------------------------------------
# StorageNode (存放位置层级树) - v1.5
#   覆盖在 location 之上的树。bulk 叶子回链一条 location 行,批次照旧挂 location。
# ---------------------------------------------------------------------------
_TEMP_TEXT = {"normal": "常温", "2-8": "2~8℃", "-20": "-20~-40℃", "-80": "-80℃"}


def assert_equipment_no_unused(db: Session, equipment_no: str) -> None:
    """一台物理设备只能绑定一个冰箱节点:若已有(任意房间的)FRIDGE 节点绑了该业务编号,拒绝。"""
    dup = db.execute(select(StorageNode).where(
        StorageNode.node_type == "FRIDGE",
        StorageNode.equipment_no == equipment_no,
    )).scalar_one_or_none()
    if dup is not None:
        raise ValueError(f"设备 {equipment_no} 已绑定到位置「{dup.path or dup.label or dup.code}」,不可重复绑定")


def equipment_names_by_no(db: Session, nos: Sequence[str]) -> dict:
    """按业务编号批量取本地已同步设备的中文名(显示用 join);未同步的编号缺省不在结果里。"""
    nos = [n for n in set(nos) if n]
    if not nos:
        return {}
    rows = db.execute(text(
        "SELECT equipment_no, name FROM equipment_mgmt.equipment "
        "WHERE equipment_no = ANY(:nos) AND is_active = TRUE"
    ), {"nos": nos}).all()
    return {r[0]: r[1] for r in rows}


def list_child_nodes(
    db: Session, parent_id: Optional[int] = None, node_type: Optional[str] = None,
) -> List[StorageNode]:
    """取某节点的直接下级(parent_id 为空 → 根节点/房间);按 sort_order, code 排序。"""
    cond = [StorageNode.parent_id.is_(None)] if parent_id is None else [StorageNode.parent_id == parent_id]
    if node_type:
        cond.append(StorageNode.node_type == node_type)
    return list(db.execute(
        select(StorageNode).where(*cond).order_by(StorageNode.sort_order, StorageNode.code)
    ).scalars().all())


def node_ids_with_children(db: Session, ids: Sequence[int]) -> set:
    """返回这些 id 中"有子节点"的 id 集合(给前端 has_children 用)。"""
    if not ids:
        return set()
    return set(db.execute(
        select(StorageNode.parent_id).where(StorageNode.parent_id.in_(list(ids))).distinct()
    ).scalars().all())


def get_node_ancestors(db: Session, node_id: int) -> List[StorageNode]:
    """从根到该节点的祖先链(含自身);选了柜要回填房间时用。"""
    chain: List[StorageNode] = []
    cur = db.get(StorageNode, node_id)
    while cur is not None:
        chain.append(cur)
        cur = db.get(StorageNode, cur.parent_id) if cur.parent_id is not None else None
    chain.reverse()
    return chain


def get_or_create_room(db: Session, room_no: str) -> StorageNode:
    room = db.execute(select(StorageNode).where(
        StorageNode.parent_id.is_(None),
        StorageNode.node_type == "ROOM",
        StorageNode.code == room_no,
    )).scalar_one_or_none()
    if room is None:
        room = StorageNode(
            parent_id=None, node_type="ROOM", code=room_no,
            label=room_no, path=room_no, depth=0, sort_order=0,
        )
        db.add(room)
        db.flush()
    return room


def create_cabinet(
    db: Session, room_no: str, cabinet_no: str, layer_count: int,
    storage_condition: Optional[str], remark: Optional[str],
) -> StorageNode:
    """试剂柜模板: 房间(复用/新建) + 1 柜 + N 个 bulk 板层(各建一条 location 并回链)。"""
    room = get_or_create_room(db, room_no)
    dup = db.execute(select(StorageNode).where(
        StorageNode.parent_id == room.node_id,
        StorageNode.node_type == "CABINET",
        StorageNode.code == cabinet_no,
    )).scalar_one_or_none()
    if dup is not None:
        raise ValueError(f"房间 {room_no} 下试剂柜 {cabinet_no} 已存在")

    cab = StorageNode(
        parent_id=room.node_id, node_type="CABINET", code=cabinet_no,
        label=cabinet_no, path=f"{room_no} / {cabinet_no}", depth=1,
        sort_order=0, remark=remark,
    )
    db.add(cab)
    db.flush()
    for i in range(1, layer_count + 1):
        loc = Location(
            room_no=room_no, cabinet_no=cabinet_no, layer_no=i,
            storage_condition=storage_condition, remark=remark,
        )
        db.add(loc)
        db.flush()
        db.add(StorageNode(
            parent_id=cab.node_id, node_type="CABINET_LAYER", code=str(i),
            label=f"L{i}", path=f"{room_no} / {cabinet_no} / L{i}", depth=2,
            sort_order=i, capacity_kind="bulk", location_id=loc.location_id,
        ))
    db.flush()
    return cab


def create_fridge(
    db: Session, room_no: str, equipment_no: str, equipment_code: Optional[str],
    temp_category: str, shelf_count: int,
    storage_condition: Optional[str], remark: Optional[str],
) -> StorageNode:
    """普通冰箱模板(2~8/-20): 房间 + 1 冰箱(绑 MDM 设备编号) + N 个 bulk 隔板(回链 location)。
    冰箱以 MDM 业务编号(equipment_no)作 code/label,身份归 MDM。"""
    assert_equipment_no_unused(db, equipment_no)
    room = get_or_create_room(db, room_no)
    dup = db.execute(select(StorageNode).where(
        StorageNode.parent_id == room.node_id,
        StorageNode.node_type == "FRIDGE",
        StorageNode.code == equipment_no,
    )).scalar_one_or_none()
    if dup is not None:
        raise ValueError(f"房间 {room_no} 下冰箱 {equipment_no} 已存在")

    fridge = StorageNode(
        parent_id=room.node_id, node_type="FRIDGE", code=equipment_no,
        label=equipment_no, path=f"{room_no} / {equipment_no}", depth=1, sort_order=0,
        temp_category=temp_category, temp_text=_TEMP_TEXT.get(temp_category),
        equipment_no=equipment_no, equipment_code=equipment_code, remark=remark,
    )
    db.add(fridge)
    db.flush()
    for i in range(1, shelf_count + 1):
        loc = Location(
            room_no=room_no, cabinet_no=equipment_no, layer_no=i,
            storage_condition=storage_condition or _TEMP_TEXT.get(temp_category), remark=remark,
        )
        db.add(loc)
        db.flush()
        db.add(StorageNode(
            parent_id=fridge.node_id, node_type="FRIDGE_SHELF", code=str(i),
            label=f"层{i}", path=f"{room_no} / {equipment_no} / 层{i}", depth=2,
            sort_order=i, capacity_kind="bulk", location_id=loc.location_id,
        ))
    db.flush()
    return fridge


def update_node(
    db: Session, node_id: int,
    label: Optional[str], remark: Optional[str], is_active: Optional[bool],
) -> Optional[StorageNode]:
    node = db.get(StorageNode, node_id)
    if node is None:
        return None
    if label is not None and label != node.label:
        _rename_node(db, node, label)
    if remark is not None:
        node.remark = remark
    if is_active is not None:
        node.is_active = is_active
    db.flush()
    return node


# 改名需要同步 location 编号字段的节点类型(库存查询按 room_no/cabinet_no 显示位置)
_RENAME_LOC_FIELD = {"ROOM": "room_no", "CABINET": "cabinet_no", "FRIDGE": "cabinet_no"}


def _rename_node(db: Session, node: StorageNode, new_label: str) -> None:
    """改名三处同步:本节点 label+path、全部子孙的 path 前缀、子树回链 location 的编号字段。
    path 是建树时写死的展示串,不重建会一直显示旧名(曾发生 F007→TT-SC-009 改名后路径不变)。"""
    old_path = node.path
    parent = db.get(StorageNode, node.parent_id) if node.parent_id is not None else None
    new_path = f"{parent.path} / {new_label}" if parent is not None and parent.path else new_label
    node.label = new_label
    node.path = new_path
    db.flush()
    if old_path and old_path != new_path:
        db.execute(text(
            """
            WITH RECURSIVE sub AS (
                SELECT node_id FROM material_mgmt.storage_node WHERE parent_id = :nid
                UNION ALL
                SELECT c.node_id
                FROM material_mgmt.storage_node c JOIN sub ON c.parent_id = sub.node_id
            )
            UPDATE material_mgmt.storage_node s
            SET path = :new_path || substr(s.path, length(:old_path) + 1)
            FROM sub
            WHERE s.node_id = sub.node_id
              AND left(s.path, length(:old_path) + 3) = :old_path || ' / '
            """
        ), {"nid": node.node_id, "new_path": new_path, "old_path": old_path})
    loc_field = _RENAME_LOC_FIELD.get(node.node_type)
    if loc_field:
        db.execute(text(
            f"""
            WITH RECURSIVE sub AS (
                SELECT node_id, location_id FROM material_mgmt.storage_node WHERE node_id = :nid
                UNION ALL
                SELECT c.node_id, c.location_id
                FROM material_mgmt.storage_node c JOIN sub ON c.parent_id = sub.node_id
            )
            UPDATE material_mgmt.location l
            SET {loc_field} = :new_label
            FROM sub
            WHERE l.location_id = sub.location_id
            """
        ), {"nid": node.node_id, "new_label": new_label})


def _subtree_location_ids(db: Session, node_id: int) -> List[int]:
    """该节点子树(含自身)下所有 bulk 叶子回链的 location_id。"""
    rows = db.execute(text(
        """
        WITH RECURSIVE sub AS (
            SELECT node_id, location_id FROM material_mgmt.storage_node WHERE node_id = :nid
            UNION ALL
            SELECT c.node_id, c.location_id
            FROM material_mgmt.storage_node c JOIN sub ON c.parent_id = sub.node_id
        )
        SELECT location_id FROM sub WHERE location_id IS NOT NULL
        """
    ), {"nid": node_id}).all()
    return [r[0] for r in rows]


def delete_node(db: Session, node_id: int) -> str:
    """删除节点及其子树。子树下任一位置存在批次则拒绝(改为停用)。
    返回 'deleted';不存在抛 KeyError,有库存抛 ValueError。"""
    node = db.get(StorageNode, node_id)
    if node is None:
        raise KeyError(node_id)
    loc_ids = _subtree_location_ids(db, node_id)
    if loc_ids:
        used = db.execute(
            select(func.count()).select_from(Batch).where(Batch.location_id.in_(loc_ids))
        ).scalar_one()
        if used:
            raise ValueError("该位置下存在批次/库存记录,不能删除,请改为停用")
    # 架/层/盒/孔没有回链 location,上面的批次守卫拦不住它们;
    # 而 cell_occupancy 对 CELL 是 ON DELETE CASCADE,直接删会静默抹掉在存样品的孔位记录
    stored = db.execute(text(
        """
        WITH RECURSIVE sub AS (
            SELECT node_id FROM material_mgmt.storage_node WHERE node_id = :nid
            UNION ALL
            SELECT c.node_id FROM material_mgmt.storage_node c JOIN sub ON c.parent_id = sub.node_id
        )
        SELECT count(*) FROM material_mgmt.cell_occupancy o
        JOIN sub ON sub.node_id = o.cell_node_id
        WHERE o.status = 'stored'
        """
    ), {"nid": node_id}).scalar_one()
    if stored:
        raise ValueError(f"该位置下有 {stored} 个孔位存放着样品,不能删除,请先出库或改为停用")
    db.delete(node)        # storage_node 自引用 ON DELETE CASCADE 清子树
    db.flush()
    if loc_ids:            # 清掉回链的孤儿 location 行
        db.execute(delete(Location).where(Location.location_id.in_(loc_ids)))
    return "deleted"


# ---------------------------------------------------------------------------
# -80℃ 冰箱模板 + 孔位占用(期2)
# ---------------------------------------------------------------------------
def create_freezer(
    db: Session, room_no: str, equipment_no: str, equipment_code: Optional[str],
    rack_count: int, layers_per_rack: int, boxes_per_layer: int, cells_per_box: int,
    remark: Optional[str],
) -> StorageNode:
    """-80℃ 冰箱: 房间 + FRIDGE(绑 MDM 设备编号, temp=-80, 锚一条 location) +
    架(A..) → 层(1..) → 盒区(A..) → 孔(1..) 整棵子树。孔位为 cell 叶子(不进 location)。"""
    total = rack_count * layers_per_rack * boxes_per_layer * cells_per_box
    if total > 60000:
        raise ValueError(f"将生成 {total} 个孔位,超过 60000 上限,请减少规模")

    assert_equipment_no_unused(db, equipment_no)
    room = get_or_create_room(db, room_no)
    dup = db.execute(select(StorageNode).where(
        StorageNode.parent_id == room.node_id,
        StorageNode.node_type == "FRIDGE",
        StorageNode.code == equipment_no,
    )).scalar_one_or_none()
    if dup is not None:
        raise ValueError(f"房间 {room_no} 下冰箱 {equipment_no} 已存在")

    # 冰箱级锚 location(批次挂这里;细位置由 cell_occupancy 表达)
    loc = Location(room_no=room_no, cabinet_no=equipment_no, layer_no=1,
                   storage_condition="-80℃", remark=remark)
    db.add(loc)
    db.flush()
    fridge = StorageNode(
        parent_id=room.node_id, node_type="FRIDGE", code=equipment_no, label=equipment_no,
        path=f"{room_no} / {equipment_no}", depth=1, sort_order=0,
        temp_category="-80", temp_text="-80℃", location_id=loc.location_id,
        equipment_no=equipment_no, equipment_code=equipment_code, remark=remark,
    )
    db.add(fridge)
    db.flush()

    cell_rows: List[dict] = []
    for ri in range(rack_count):
        rc = chr(65 + ri)  # A, B, ...
        rack = StorageNode(
            parent_id=fridge.node_id, node_type="RACK", code=rc, label=rc,
            path=f"{room_no} / {equipment_no} / {rc}", depth=2, sort_order=ri,
        )
        db.add(rack)
        db.flush()
        for li in range(1, layers_per_rack + 1):
            layer = StorageNode(
                parent_id=rack.node_id, node_type="RACK_LAYER", code=str(li), label=str(li),
                path=f"{room_no} / {equipment_no} / {rc} / {li}", depth=3, sort_order=li,
            )
            db.add(layer)
            db.flush()
            for bi in range(boxes_per_layer):
                bc = chr(65 + bi)
                box = StorageNode(
                    parent_id=layer.node_id, node_type="BOX", code=bc, label=bc,
                    path=f"{room_no} / {equipment_no} / {rc} / {li} / {bc}", depth=4, sort_order=bi,
                )
                db.add(box)
                db.flush()
                base = box.path
                for ci in range(1, cells_per_box + 1):
                    cell_rows.append({
                        "parent_id": box.node_id, "node_type": "CELL", "code": str(ci),
                        "label": str(ci), "path": f"{base} / {ci}", "depth": 5,
                        "sort_order": ci, "capacity_kind": "cell", "is_active": True,
                    })
    if cell_rows:
        db.execute(insert(StorageNode), cell_rows)  # 批量插孔位(可能上万行)
    db.flush()
    return fridge


def cell_address(db: Session, cell_node_id: int) -> str:
    """由祖先链拼短地址,如 'TT3 B3:A,23'(冰箱 架层:盒,孔)。"""
    chain = get_node_ancestors(db, cell_node_id)  # [room, fridge, rack, layer, box, cell]
    by = {n.node_type: n for n in chain}
    fr = by.get("FRIDGE")
    rk = by.get("RACK")
    ly = by.get("RACK_LAYER")
    bx = by.get("BOX")
    cell = by.get("CELL")
    if not all([fr, rk, ly, bx, cell]):
        return cell.path if cell else f"#{cell_node_id}"
    return f"{fr.label or fr.code} {rk.code}{ly.code}:{bx.code},{cell.code}"


def list_box_cells(db: Session, box_id: int) -> List[dict]:
    """盒内全部孔 + 占用信息(热力图数据源)。"""
    cells = list(db.execute(
        select(StorageNode).where(
            StorageNode.parent_id == box_id, StorageNode.node_type == "CELL"
        ).order_by(StorageNode.sort_order)
    ).scalars().all())
    cell_ids = [c.node_id for c in cells]
    occ: dict = {}
    if cell_ids:
        rows = db.execute(
            select(
                CellOccupancy, Material.material_code, Material.name_cn,
                Batch.batch_no, Batch.expiry_date,
            )
            .join(Batch, Batch.batch_id == CellOccupancy.batch_id)
            .join(Material, Material.material_id == Batch.material_id)
            .where(
                CellOccupancy.cell_node_id.in_(cell_ids),
                CellOccupancy.status == "stored",
            )
        ).all()
        today = date.today()
        for o, mcode, mname, bno, exp in rows:
            occ[o.cell_node_id] = {
                "occupancy_id": o.occupancy_id, "batch_id": o.batch_id,
                "material_code": mcode, "material_name": mname,
                "batch_no": bno, "sample_label": o.sample_label,
                "expiry_date": exp,
                "days_to_expiry": (exp - today).days if exp else None,
            }
    out = []
    for c in cells:
        info = occ.get(c.node_id)
        out.append({
            "cell_node_id": c.node_id, "code": c.code, "occupied": info is not None,
            "occupancy_id": info["occupancy_id"] if info else None,
            "batch_id": info["batch_id"] if info else None,
            "material_code": info["material_code"] if info else None,
            "material_name": info["material_name"] if info else None,
            "batch_no": info["batch_no"] if info else None,
            "sample_label": info["sample_label"] if info else None,
            "expiry_date": info["expiry_date"] if info else None,
            "days_to_expiry": info["days_to_expiry"] if info else None,
        })
    return out


def list_batch_cells(db: Session, batch_id: int) -> List[dict]:
    """某批次当前占用的全部孔(出库勾选 / 物料详情弹窗用)。空列表表示该批次非孔位存储(散放)。"""
    batch = db.get(Batch, batch_id)
    if batch is None:
        return []
    rows = db.execute(
        select(CellOccupancy, StorageNode.code, StorageNode.parent_id)
        .join(StorageNode, StorageNode.node_id == CellOccupancy.cell_node_id)
        .where(
            CellOccupancy.batch_id == batch_id,
            CellOccupancy.status == "stored",
        )
    ).all()
    today = date.today()
    days = (batch.expiry_date - today).days if batch.expiry_date else None
    out = [
        {
            "cell_node_id": o.cell_node_id,
            "code": code,
            "box_node_id": box_id,            # CELL 的父节点即所在盒区
            "address": cell_address(db, o.cell_node_id),
            "sample_label": o.sample_label,
            "expiry_date": batch.expiry_date,
            "days_to_expiry": days,
        }
        for o, code, box_id in rows
    ]
    # 地址里层号/孔号是数字串,按整串文字排会把 10 排到 2 前面;
    # 自然序 key:把地址拆成 文字/数字 段,数字段按数值比较(盒地址如 'TT3 A10:B')
    out.sort(key=lambda x: (_natural_key(x["address"].rsplit(",", 1)[0]),
                            len(x["code"]), x["code"]))
    return out


def _natural_key(s: str) -> tuple:
    """'A10:B' → ('A', 10, ':B') 式的自然排序 key,数字段按数值比。"""
    return tuple(int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s or ""))


def batch_stored_cell_count(db: Session, batch_id: int) -> int:
    """该批次当前占用(stored)的孔数;>0 表示是 -80 孔位存放批次。"""
    return db.execute(
        select(func.count()).select_from(CellOccupancy).where(
            CellOccupancy.batch_id == batch_id,
            CellOccupancy.status == "stored",
        )
    ).scalar_one()


def batch_cell_location_names(db: Session, batch_ids: Sequence[int]) -> dict:
    """孔位批次的真实位置文本(批量): {batch_id: 'TT-SC-002 A架1层A盒'(跨盒加 ' 等N盒')}。
    批次挂的 location 是整台 -80 冰箱的锚定行(名字固定带 -L1,不代表真实层),
    列表展示必须改用孔位占用聚合出的 冰箱/架/层/盒;非孔位批次不在返回里。"""
    ids = [i for i in set(batch_ids) if i is not None]
    if not ids:
        return {}
    rows = db.execute(text(
        """
        SELECT o.batch_id,
               COALESCE(fr.label, fr.code) AS fridge,
               rk.code AS rack, ly.code AS layer, bx.code AS box
        FROM material_mgmt.cell_occupancy o
        JOIN material_mgmt.storage_node c  ON c.node_id  = o.cell_node_id
        JOIN material_mgmt.storage_node bx ON bx.node_id = c.parent_id
        JOIN material_mgmt.storage_node ly ON ly.node_id = bx.parent_id
        JOIN material_mgmt.storage_node rk ON rk.node_id = ly.parent_id
        JOIN material_mgmt.storage_node fr ON fr.node_id = rk.parent_id
        WHERE o.status = 'stored' AND o.batch_id = ANY(:ids)
        GROUP BY o.batch_id, COALESCE(fr.label, fr.code), rk.code, ly.code, bx.code
        ORDER BY o.batch_id, rk.code, length(ly.code), ly.code, bx.code
        """
    ), {"ids": ids}).all()
    boxes: dict = {}
    for bid, fridge, rack, layer, box in rows:
        boxes.setdefault(bid, []).append((fridge, rack, layer, box))
    out = {}
    for bid, bs in boxes.items():
        fridge, rack, layer, box = bs[0]
        name = f"{fridge} {rack}架{layer}层{box}盒"
        if len(bs) > 1:
            name += f" 等{len(bs)}盒"
        out[bid] = name
    return out


def release_cells(
    db: Session, cell_node_ids: Sequence[int], operator: str,
    txn_date=None, purpose: Optional[str] = None, remark: Optional[str] = None,
) -> dict:
    """出库:批量释放若干孔。每孔置 removed + 一条 OUT 流水(qty=-1)。
    任一孔为空即整体报错(ValueError)。返回 {count, batch_ids, addresses}。"""
    if not cell_node_ids:
        raise ValueError("未选择任何孔位")
    txn_date = txn_date or date.today()
    # FOR UPDATE:并发/重复提交时第二笔会等锁后重读,发现已 removed → 走下面的"孔位为空"报错,
    # 不加锁则两笔都读到 stored,一支管扣两次库存
    occ_rows = list(db.execute(
        select(CellOccupancy).where(
            CellOccupancy.cell_node_id.in_(list(cell_node_ids)),
            CellOccupancy.status == "stored",
        ).with_for_update()
    ).scalars().all())
    found = {o.cell_node_id for o in occ_rows}
    missing = [cid for cid in cell_node_ids if cid not in found]
    if missing:
        addrs = ", ".join(cell_address(db, cid) for cid in missing)
        raise ValueError(f"以下孔位当前为空,无法出库: {addrs}")

    now = datetime.now()  # 裸上海墙钟
    batch_ids = set()
    for o in occ_rows:
        o.status = "removed"
        o.removed_at = now
        if remark:
            o.remark = remark
        batch_ids.add(o.batch_id)
        db.add(InventoryTxn(
            batch_id=o.batch_id, txn_type="OUT", qty=Decimal("-1"),
            txn_date=txn_date, operator=operator, purpose=purpose or "出库", remark=remark,
        ))
    db.flush()
    return {
        "count": len(occ_rows),
        "batch_ids": sorted(batch_ids),
        "addresses": [cell_address(db, cid) for cid in cell_node_ids],
    }


def assert_location_active(db: Session, location_id: int) -> None:
    """位置回链的树节点或其任一祖先已停用则拒绝写入(ValueError)。
    停用状态记录在 storage_node.is_active,location 行本身没有;未挂树的历史 location 视为可用。"""
    row = db.execute(text(
        """
        WITH RECURSIVE up AS (
            SELECT node_id, parent_id, is_active
            FROM material_mgmt.storage_node WHERE location_id = :lid
            UNION ALL
            SELECT p.node_id, p.parent_id, p.is_active
            FROM material_mgmt.storage_node p JOIN up ON p.node_id = up.parent_id
        )
        SELECT 1 FROM up WHERE NOT is_active LIMIT 1
        """
    ), {"lid": location_id}).first()
    if row is not None:
        raise ValueError("该位置已停用,不能入库/移入;如需使用请先在「位置管理」启用")


def assert_cells_active(db: Session, cell_node_ids: Sequence[int]) -> None:
    """任一孔位自身或其盒/层/架/冰箱/房间已停用则拒绝占用(ValueError)。"""
    rows = db.execute(text(
        """
        WITH RECURSIVE up AS (
            SELECT node_id AS leaf, node_id, parent_id, is_active
            FROM material_mgmt.storage_node WHERE node_id = ANY(:ids)
            UNION ALL
            SELECT up.leaf, p.node_id, p.parent_id, p.is_active
            FROM material_mgmt.storage_node p JOIN up ON p.node_id = up.parent_id
        )
        SELECT DISTINCT leaf FROM up WHERE NOT is_active
        """
    ), {"ids": list(cell_node_ids)}).scalars().all()
    if rows:
        addrs = ", ".join(cell_address(db, cid) for cid in list(rows)[:5])
        raise ValueError(f"以下孔位所在位置已停用,不能入库: {addrs}")


# 空孔遍历顺序:架(字母) → 层(数字,按长度+字面即自然序) → 盒(字母) → 孔号(数字)。
# 不能 ORDER BY path:层号是数字串,按整串文字排会把 10 层排到 2 层前面。
_CELL_WALK_SQL = """
    WITH RECURSIVE sub AS (
        SELECT node_id, node_type, code, parent_id, is_active AS active
        FROM material_mgmt.storage_node WHERE node_id = :fid
        UNION ALL
        SELECT c.node_id, c.node_type, c.code, c.parent_id, (sub.active AND c.is_active) AS active
        FROM material_mgmt.storage_node c JOIN sub ON c.parent_id = sub.node_id
    )
    SELECT s.node_id, (o.occupancy_id IS NOT NULL) AS occupied
    FROM sub s
    JOIN material_mgmt.storage_node bx ON bx.node_id = s.parent_id
    JOIN material_mgmt.storage_node ly ON ly.node_id = bx.parent_id
    JOIN material_mgmt.storage_node rk ON rk.node_id = ly.parent_id
    LEFT JOIN material_mgmt.cell_occupancy o
           ON o.cell_node_id = s.node_id AND o.status = 'stored'
    WHERE s.node_type = 'CELL' AND s.active
    ORDER BY rk.code, length(ly.code), ly.code, bx.code, length(s.code), s.code
"""


def find_free_cells(db: Session, freezer_id: int, count: int) -> List[int]:
    """冰箱内最多 count 个空孔(盒内连续优先);停用的盒/架/孔不参与推荐。"""
    rows = db.execute(text(_CELL_WALK_SQL), {"fid": freezer_id}).all()
    return [r[0] for r in rows if not r[1]][:count]


def occupy_cells(
    db: Session, material_id: int, batch_no: str, expiry_date, received_date,
    cell_node_ids: Sequence[int], operator: str,
    sample_labels: Optional[Sequence[Optional[str]]] = None,
    intake_type: Optional[str] = None, concentration: Optional[str] = None,
    extinction_coefficient: Optional[Decimal] = None,
    project_no: Optional[str] = None, originator_batch_no: Optional[str] = None,
    aliquot_date=None, remark: Optional[str] = None,
    intake_operator_name: Optional[str] = None,
) -> dict:
    """把若干空孔分配给某物料批次: 校验空孔 → 找/建批次(锚冰箱 location) →
    写 cell_occupancy + 一条 IN 流水(qty=孔数)。返回 {batch_id, count, addresses}。"""
    if not cell_node_ids:
        raise ValueError("未选择任何孔位")

    cells = list(db.execute(
        select(StorageNode).where(StorageNode.node_id.in_(list(cell_node_ids)))
    ).scalars().all())
    if len(cells) != len(set(cell_node_ids)):
        raise ValueError("存在无效的孔位")
    if any(c.node_type != "CELL" for c in cells):
        raise ValueError("选中的节点不是孔位")
    assert_cells_active(db, cell_node_ids)

    # 全部孔必须在同一台冰箱:批次锚在冰箱的 location 上,跨冰箱会把 B 冰箱的样品记到 A 冰箱账下
    fridge_ids = db.execute(text(
        """
        WITH RECURSIVE up AS (
            SELECT node_id, parent_id, node_type
            FROM material_mgmt.storage_node WHERE node_id = ANY(:ids)
            UNION ALL
            SELECT p.node_id, p.parent_id, p.node_type
            FROM material_mgmt.storage_node p JOIN up ON p.node_id = up.parent_id
        )
        SELECT DISTINCT node_id FROM up WHERE node_type = 'FRIDGE'
        """
    ), {"ids": list(cell_node_ids)}).scalars().all()
    if len(fridge_ids) > 1:
        raise ValueError("所选孔位分属多台冰箱,一次入库只能选同一台冰箱的孔位")
    fridge = next((n for n in get_node_ancestors(db, cells[0].node_id) if n.node_type == "FRIDGE"), None)
    if fridge is None or fridge.location_id is None:
        raise ValueError("孔位未挂在 -80℃ 冰箱下")

    # 占用冲突检查
    taken = db.execute(
        select(CellOccupancy.cell_node_id).where(
            CellOccupancy.cell_node_id.in_(list(cell_node_ids)),
            CellOccupancy.status == "stored",
        )
    ).scalars().all()
    if taken:
        addrs = ", ".join(cell_address(db, cid) for cid in taken)
        raise ValueError(f"以下孔位已被占用: {addrs}")

    # material_type 跟随 intake_type(与散放入库一致)
    if intake_type:
        mat = db.get(Material, material_id)
        if mat and mat.material_type != intake_type:
            mat.material_type = intake_type

    n = len(cell_node_ids)
    batch = find_batch_at_location(db, material_id, batch_no, fridge.location_id)
    if batch is None:
        batch = Batch(
            material_id=material_id, batch_no=batch_no, expiry_date=expiry_date,
            location_id=fridge.location_id, received_date=received_date,
            initial_qty=Decimal(n), remark=remark, intake_type=intake_type,
            concentration=concentration, extinction_coefficient=extinction_coefficient,
            project_no=project_no, originator_batch_no=originator_batch_no,
            aliquot_date=aliquot_date, intake_operator_name=intake_operator_name,
        )
        db.add(batch)
        db.flush()

    labels = list(sample_labels) if sample_labels else [None] * n
    for cid, label in zip(cell_node_ids, labels):
        db.add(CellOccupancy(
            cell_node_id=cid, batch_id=batch.batch_id,
            sample_label=(label or None), stored_by=operator,
        ))
    db.add(InventoryTxn(
        batch_id=batch.batch_id, txn_type="IN", qty=Decimal(n),
        txn_date=received_date, operator=operator, purpose="-80冻存入库",
    ))
    db.flush()
    return {
        "batch_id": batch.batch_id,
        "count": n,
        "addresses": [cell_address(db, cid) for cid in cell_node_ids],
    }


def occupy_from_start(
    db: Session, start_cell_node_id: int, count: int,
    material_id: int, batch_no: str, expiry_date, received_date, operator: str,
    sample_labels: Optional[Sequence[Optional[str]]] = None,
    intake_type: Optional[str] = None, concentration: Optional[str] = None,
    extinction_coefficient: Optional[Decimal] = None,
    project_no: Optional[str] = None, originator_batch_no: Optional[str] = None,
    aliquot_date=None, remark: Optional[str] = None,
    intake_operator_name: Optional[str] = None,
) -> dict:
    """从起始孔起,沿地址顺序取连续 count 个孔(须全部为空,中间有占用即报错),
    占用入库。复用 occupy_cells 落库。返回 {batch_id, count, addresses}。"""
    start = db.get(StorageNode, start_cell_node_id)
    if start is None or start.node_type != "CELL":
        raise ValueError("起始位置不是有效孔位")
    fridge = next((n for n in get_node_ancestors(db, start_cell_node_id) if n.node_type == "FRIDGE"), None)
    if fridge is None or fridge.location_id is None:
        raise ValueError("起始孔未挂在 -80℃ 冰箱下")

    # 冰箱内全部可用孔位,按 架/层/盒/孔 自然顺序,带占用标记(与 find_free_cells 同一遍历)
    rows = db.execute(text(_CELL_WALK_SQL), {"fid": fridge.node_id}).all()
    ids = [r[0] for r in rows]
    occupied = {r[0]: r[1] for r in rows}
    try:
        idx = ids.index(start_cell_node_id)
    except ValueError:
        raise ValueError("起始孔不在该冰箱内")

    window = ids[idx: idx + count]
    if len(window) < count:
        raise ValueError(f"从起始位置往后不足 {count} 个孔(仅剩 {len(window)} 个)")
    conflicts = [cid for cid in window if occupied.get(cid)]
    if conflicts:
        addrs = ", ".join(cell_address(db, cid) for cid in conflicts[:10])
        raise ValueError(f"起始位置起的 {count} 个连续孔中有已占用,无法连续填充: {addrs}")

    return occupy_cells(
        db, material_id=material_id, batch_no=batch_no, expiry_date=expiry_date,
        received_date=received_date, cell_node_ids=window, operator=operator,
        sample_labels=sample_labels, intake_type=intake_type,
        concentration=concentration, extinction_coefficient=extinction_coefficient,
        project_no=project_no, originator_batch_no=originator_batch_no,
        aliquot_date=aliquot_date, remark=remark,
        intake_operator_name=intake_operator_name,
    )


def release_cell(db: Session, cell_node_id: int, operator: str, remark: Optional[str] = None) -> dict:
    """释放某孔: 占用置 removed + 一条 OUT 流水(qty=-1)。返回 {batch_id, address}。"""
    occ = db.execute(
        select(CellOccupancy).where(
            CellOccupancy.cell_node_id == cell_node_id,
            CellOccupancy.status == "stored",
        ).with_for_update()  # 防重复释放双倍扣账,同 release_cells
    ).scalar_one_or_none()
    if occ is None:
        raise ValueError("该孔位当前为空")
    occ.status = "removed"
    occ.removed_at = datetime.now()  # 裸上海墙钟
    if remark:
        occ.remark = remark
    db.add(InventoryTxn(
        batch_id=occ.batch_id, txn_type="OUT", qty=Decimal("-1"),
        txn_date=date.today(), operator=operator, purpose="-80取管",
    ))
    db.flush()
    return {"batch_id": occ.batch_id, "address": cell_address(db, cell_node_id)}


# ---------------------------------------------------------------------------
# 往已有节点追加下级(结构性编辑;支持异构与分批)
# ---------------------------------------------------------------------------
# 合法的 父类型 → 可追加的子类型
_ADD_ALLOWED = {
    "CABINET": {"CABINET_LAYER"},
    "FRIDGE": {"FRIDGE_SHELF", "RACK"},
    "RACK": {"RACK_LAYER"},
    "RACK_LAYER": {"BOX"},
    "BOX": {"CELL"},
}


def _gen_box_cells(box: StorageNode, cells: int, cell_rows: list, start: int = 1) -> None:
    for ci in range(start, start + cells):
        cell_rows.append({
            "parent_id": box.node_id, "node_type": "CELL", "code": str(ci), "label": str(ci),
            "path": f"{box.path} / {ci}", "depth": box.depth + 1, "sort_order": ci,
            "capacity_kind": "cell", "is_active": True,
        })


def _gen_layer_subtree(db: Session, layer: StorageNode, boxes: int, cells: int, cell_rows: list) -> None:
    for bi in range(boxes):
        bc = chr(65 + bi)
        box = StorageNode(
            parent_id=layer.node_id, node_type="BOX", code=bc, label=bc,
            path=f"{layer.path} / {bc}", depth=layer.depth + 1, sort_order=bi,
        )
        db.add(box)
        db.flush()
        _gen_box_cells(box, cells, cell_rows)


def _gen_rack_subtree(db: Session, rack: StorageNode, layers: int, boxes: int, cells: int, cell_rows: list) -> None:
    for li in range(1, layers + 1):
        layer = StorageNode(
            parent_id=rack.node_id, node_type="RACK_LAYER", code=str(li), label=str(li),
            path=f"{rack.path} / {li}", depth=rack.depth + 1, sort_order=li,
        )
        db.add(layer)
        db.flush()
        _gen_layer_subtree(db, layer, boxes, cells, cell_rows)


def add_children(
    db: Session, parent_id: int, child_type: str, count: int,
    layers_per_rack: Optional[int] = None, boxes_per_layer: Optional[int] = None,
    cells_per_box: Optional[int] = None, storage_condition: Optional[str] = None,
    remark: Optional[str] = None,
) -> dict:
    """在 parent 下追加 count 个 child_type 节点,编号续接现有兄弟。
    异构由此达成:对某个架单独加层、对某层加不同孔数的盒、对冰箱分批加架。"""
    parent = db.get(StorageNode, parent_id)
    if parent is None:
        raise KeyError(parent_id)
    if child_type not in _ADD_ALLOWED.get(parent.node_type, set()):
        raise ValueError(f"{parent.node_type} 节点下不支持追加 {child_type}")
    if parent.node_type == "FRIDGE":
        is_80 = parent.temp_category == "-80"
        if is_80 and child_type != "RACK":
            raise ValueError("-80℃ 冰箱只能追加冻存架")
        if not is_80 and child_type != "FRIDGE_SHELF":
            raise ValueError("普通冰箱只能追加隔板")

    # 必填参数与规模守卫
    per_cells = {
        "RACK": (layers_per_rack or 0) * (boxes_per_layer or 0) * (cells_per_box or 0),
        "RACK_LAYER": (boxes_per_layer or 0) * (cells_per_box or 0),
        "BOX": (cells_per_box or 0),
        "CELL": 1,
    }.get(child_type, 0)
    if child_type == "RACK" and not (layers_per_rack and boxes_per_layer and cells_per_box):
        raise ValueError("追加冻存架需填:每架层数 / 每层盒数 / 每盒孔数")
    if child_type == "RACK_LAYER" and not (boxes_per_layer and cells_per_box):
        raise ValueError("追加层需填:每层盒数 / 每盒孔数")
    if child_type == "BOX" and not cells_per_box:
        raise ValueError("追加盒需填:每盒孔数")
    if per_cells * count > 60000:
        raise ValueError(f"将生成 {per_cells * count} 个孔位,超过 60000 上限")

    room_no = next((n.code for n in get_node_ancestors(db, parent_id) if n.node_type == "ROOM"), "")

    # 续接编号:RACK/BOX 用字母,其余用数字
    existing = list(db.execute(
        select(StorageNode.code).where(
            StorageNode.parent_id == parent_id, StorageNode.node_type == child_type
        )
    ).scalars().all())
    if child_type in ("RACK", "BOX"):
        used = set(existing)
        codes, i = [], 0
        while len(codes) < count and i < 26:
            c = chr(65 + i); i += 1
            if c not in used:
                codes.append(c)
        if len(codes) < count:
            raise ValueError("字母编号(A~Z)已用尽,无法继续追加")
    else:
        nums = [int(c) for c in existing if c.isdigit()]
        start = (max(nums) + 1) if nums else 1
        codes = [str(start + k) for k in range(count)]

    cell_rows: list = []
    for code in codes:
        sort_order = (ord(code) - 65) if child_type in ("RACK", "BOX") else int(code)
        node = StorageNode(
            parent_id=parent.node_id, node_type=child_type, code=code, label=code,
            path=f"{parent.path} / {code}", depth=parent.depth + 1, sort_order=sort_order,
            remark=remark,
        )
        if child_type == "CABINET_LAYER":
            loc = Location(room_no=room_no, cabinet_no=parent.code, layer_no=int(code),
                           storage_condition=storage_condition, remark=remark)
            db.add(loc); db.flush()
            node.label = f"L{code}"; node.capacity_kind = "bulk"; node.location_id = loc.location_id
        elif child_type == "FRIDGE_SHELF":
            loc = Location(room_no=room_no, cabinet_no=parent.code, layer_no=int(code),
                           storage_condition=storage_condition or parent.temp_text, remark=remark)
            db.add(loc); db.flush()
            node.label = f"层{code}"; node.capacity_kind = "bulk"; node.location_id = loc.location_id
        elif child_type == "CELL":
            node.capacity_kind = "cell"
        db.add(node)
        db.flush()
        if child_type == "RACK":
            _gen_rack_subtree(db, node, layers_per_rack, boxes_per_layer, cells_per_box, cell_rows)
        elif child_type == "RACK_LAYER":
            _gen_layer_subtree(db, node, boxes_per_layer, cells_per_box, cell_rows)
        elif child_type == "BOX":
            _gen_box_cells(node, cells_per_box, cell_rows)

    if cell_rows:
        db.execute(insert(StorageNode), cell_rows)
    db.flush()
    return {"created": len(codes), "child_type": child_type, "codes": codes}


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
    rows = [tuple(r) for r in db.execute(stmt).all()]
    cell_names = batch_cell_location_names(db, [r[0].batch_id for r in rows])
    return [
        (b, qty, cell_names.get(b.batch_id, loc), code, name, unit)
        for b, qty, loc, code, name, unit in rows
    ]


def get_batch(db: Session, batch_id: int) -> Optional[Batch]:
    return db.get(Batch, batch_id)


def lock_batch(db: Session, batch_id: int) -> None:
    """锁批次行(SELECT FOR UPDATE),把同批次的「读库存→写流水」串行化。
    出库/调整/移库都是先查现有库存再落账,不锁的话并发两笔各自通过校验,库存会被打成负数。"""
    db.execute(select(Batch.batch_id).where(Batch.batch_id == batch_id).with_for_update())


# 批次"元信息"白名单:可经双人复核修改的字段。
# 不含 batch_no(身份)/数量(走盘点)/location_id(走移库)/material_id/intake_type(分类权威)。
BATCH_EDITABLE_FIELDS = {
    "expiry_date", "received_date", "remark", "concentration",
    "extinction_coefficient", "serial_no", "asset_no",
    "responsible_person", "project_no", "originator_batch_no", "aliquot_date",
}


def update_batch_meta(db: Session, batch: Batch, changes: dict) -> Batch:
    """按白名单改批次元信息;审计与 commit 由调用方负责。"""
    for k, v in changes.items():
        if k in BATCH_EDITABLE_FIELDS:
            setattr(batch, k, v)
    db.flush()
    return batch


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
    project_no: Optional[str] = None,
    originator_batch_no: Optional[str] = None,
    aliquot_date=None,
    intake_operator_name: Optional[str] = None,
) -> Batch:
    """新建批次并同步写入首笔入库 txn(IN)。
    若 intake_type 提供, 与物料当前 material_type 不一致, 用 intake_type 覆盖。
    理由: 老物料的 material_type 是按 category 初始映射的(可能不准, 比如
    "一般耗材"里混着色谱柱); 用户在哪个 tab 入库, 那就是物料的真实分类。
    每次入库都同步, 让物料类型与最近一次入库 tab 保持一致。"""
    # 自动同步 material.material_type 到 intake_type
    if intake_type:
        mat = db.get(Material, material_id)
        if mat and mat.material_type != intake_type:
            mat.material_type = intake_type

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
        project_no=project_no,
        originator_batch_no=originator_batch_no,
        aliquot_date=aliquot_date,
        intake_operator_name=intake_operator_name,
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
    db.flush()
    db.refresh(b)
    return b


def bulk_intake(db: Session, rows, received_date, operator: str, intake_type: Optional[str] = None, intake_operator_name: Optional[str] = None) -> dict:
    """散放层多行批量入库。两遍式: 先逐行校验, 全部通过才写入(任一行不合法 → 不写任何数据)。
    命中同 (material_id, batch_no, location_id) → 追加 IN; 否则建批次 + 首笔 IN。
    返回 {ok, created, appended, failed, results}。rows 为 BulkIntakeRow 序列。"""
    results: List[dict] = []
    has_error = False
    for i, r in enumerate(rows):
        msg = None
        mat = db.get(Material, r.material_id)
        if mat is None:
            msg = f"物料 #{r.material_id} 不存在"
        elif not mat.is_active:
            msg = f"物料 {mat.material_code} 已停用,不可入库"
        elif r.qty is None or r.qty <= 0:
            msg = "数量必须 > 0"
        elif db.get(Location, r.location_id) is None:
            msg = "存放位置不存在"
        else:
            try:
                assert_location_active(db, r.location_id)
            except ValueError as e:
                msg = str(e)
        if msg:
            has_error = True
        results.append({"index": i, "status": "error" if msg else "ok",
                        "batch_id": None, "message": msg})
    if has_error:
        return {"ok": False, "created": 0, "appended": 0,
                "failed": sum(1 for x in results if x["status"] == "error"),
                "results": results}

    created = appended = 0
    for i, r in enumerate(rows):
        existing = find_batch_at_location(db, r.material_id, r.batch_no, r.location_id)
        if existing is not None:
            add_in(db, existing.batch_id, r.qty, received_date, operator, remark="批量入库-追加")
            if intake_type:
                mat = db.get(Material, r.material_id)
                if mat and mat.material_type != intake_type:
                    mat.material_type = intake_type
            results[i] = {"index": i, "status": "appended", "batch_id": existing.batch_id, "message": None}
            appended += 1
        else:
            b = create_batch_with_initial_in(
                db, material_id=r.material_id, batch_no=r.batch_no, expiry_date=r.expiry_date,
                location_id=r.location_id, received_date=received_date, initial_qty=r.qty,
                operator=operator, remark=r.remark, intake_type=intake_type,
                concentration=r.concentration, extinction_coefficient=r.extinction_coefficient,
                serial_no=r.serial_no, asset_no=r.asset_no, responsible_person=r.responsible_person,
                project_no=r.project_no, originator_batch_no=r.originator_batch_no,
                aliquot_date=r.aliquot_date, intake_operator_name=intake_operator_name,
            )
            results[i] = {"index": i, "status": "created", "batch_id": b.batch_id, "message": None}
            created += 1
    db.flush()
    return {"ok": True, "created": created, "appended": appended, "failed": 0, "results": results}


# ---------------------------------------------------------------------------
# Inventory Txn
# ---------------------------------------------------------------------------
def add_in(db: Session, batch_id: int, qty: Decimal, txn_date, operator: str, remark: Optional[str]) -> InventoryTxn:
    txn = InventoryTxn(
        batch_id=batch_id, txn_type="IN", qty=qty, txn_date=txn_date,
        operator=operator, remark=remark,
    )
    db.add(txn)
    db.flush()
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
    db.flush()
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
    db.flush()
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
    src = db.execute(
        select(Batch).where(Batch.batch_id == source_batch_id).with_for_update()
    ).scalar_one_or_none()
    if not src:
        raise ValueError(f"源批次 {source_batch_id} 不存在")
    # -80℃ 孔位批次的数量与孔一一对应,按数量搬走会造成 孔数≠库存
    if batch_stored_cell_count(db, source_batch_id) > 0:
        raise ValueError("源批次为 -80℃ 孔位存放,不能按数量移库;请通过出库+重新入库迁移")
    if dest_location_id == src.location_id:
        raise ValueError("目的位置与源位置相同,无需移库")
    dest_loc = db.get(Location, dest_location_id)
    if not dest_loc:
        raise ValueError(f"目的位置 {dest_location_id} 不存在")
    # 目的位置不能是 -80 冰箱的整机锚定位置(那里的批次必须逐孔存放)
    anchor = db.execute(select(StorageNode).where(
        StorageNode.location_id == dest_location_id,
        StorageNode.node_type == "FRIDGE",
    )).scalar_one_or_none()
    if anchor is not None:
        raise ValueError("目的位置是 -80℃ 冰箱,散放数量不能移入;请通过出库+按孔位入库迁移")
    assert_location_active(db, dest_location_id)
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
            intake_operator_name=src.intake_operator_name,
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
    db.flush()
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
            Batch.project_no,
            Batch.originator_batch_no,
            Batch.aliquot_date,
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
    material_type: Optional[str] = None,
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
            Material.material_type,
            Material.manufacturer,
            Material.spec_model,
            Material.catalog_no,
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
    if material_type:
        stmt = stmt.where(Material.material_type == material_type)
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
            "material_type": row.material_type,
            "manufacturer": row.manufacturer,
            "spec_model": row.spec_model,
            "catalog_no": row.catalog_no,
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
    material_type: Optional[str] = None,
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
            Material.material_type,
            Batch.intake_type,
            Batch.originator_batch_no,
            Batch.intake_operator_name,
            Material.manufacturer,
            Material.spec_model,
            Material.catalog_no,
        )
        .join(Material, Material.material_id == Batch.material_id)
        .outerjoin(qty_subq, qty_subq.c.batch_id == Batch.batch_id)
        .join(Location, Location.location_id == Batch.location_id)
    )
    if category:
        stmt = stmt.where(Material.category == category)
    if material_type:
        stmt = stmt.where(Material.material_type == material_type)
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
    rows = db.execute(stmt).all()
    cell_names = batch_cell_location_names(db, [r.batch_id for r in rows])
    out = []
    for r in rows:
        days = (r.expiry_date - today).days if r.expiry_date else None
        out.append({
            "batch_id": r.batch_id,
            "material_id": r.material_id,
            "material_code": r.material_code,
            "name_cn": r.name_cn,
            "category": r.category,
            "material_type": r.material_type,
            "intake_type": r.intake_type,
            "manufacturer": r.manufacturer,
            "spec_model": r.spec_model,
            "catalog_no": r.catalog_no,
            "unit": r.unit,
            "batch_no": r.batch_no,
            "originator_batch_no": r.originator_batch_no,
            "intake_operator_name": r.intake_operator_name,
            "expiry_date": r.expiry_date,
            "location_id": r.location_id,
            "location_name": cell_names.get(r.batch_id, r.location_name),
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
    rows = db.execute(stmt).all()
    cell_names = batch_cell_location_names(db, [r.batch_id for r in rows])
    out = []
    for r in rows:
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
            "location_name": cell_names.get(r.batch_id, r.location_name),
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
