"""
文件: backend/routers/storage.py
用途: 存放位置层级树 API(v1.5)
说明:
    - storage_node 是覆盖在 location 之上的层级树:
        试剂柜   ROOM → CABINET → CABINET_LAYER(bulk)
        普通冰箱 ROOM → FRIDGE  → FRIDGE_SHELF(bulk)
      bulk 叶子 1:1 回链 location;批次仍挂 location_id,现有库存逻辑零改动。
    - 级联取数: GET /nodes?parent_id= 取下一级;选到叶子拿 location_id 走原入库 API。
    - -80 冰箱(RACK/BOX/CELL)与孔位占用属期2,本文件暂不实现。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import crud
from audit import get_request_ip, model_snapshot, write_audit
from database import get_db
from auth import CurrentUser, require_warehouse, require_admin
from schemas import (
    CabinetCreate, FridgeCreate, FreezerCreate, NodeUpdate, StorageNodeOut,
    CellOut, OccupyRequest, OccupyResult, ReleaseRequest, AddChildrenRequest,
    OccupyFromRequest, BatchCellOut, ReleaseCellsRequest,
)

router = APIRouter(prefix="/api/storage", tags=["storage"])


def _to_out(node, has_children: bool) -> dict:
    return {
        "node_id": node.node_id,
        "parent_id": node.parent_id,
        "node_type": node.node_type,
        "code": node.code,
        "label": node.label,
        "path": node.path,
        "depth": node.depth,
        "sort_order": node.sort_order,
        "capacity_kind": node.capacity_kind,
        "location_id": node.location_id,
        "temp_category": node.temp_category,
        "temp_text": node.temp_text,
        "is_active": node.is_active,
        "remark": node.remark,
        "has_children": has_children,
    }


@router.get("/nodes", response_model=List[StorageNodeOut])
def list_nodes(
    parent_id: Optional[int] = None,
    node_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """取某节点的直接下级;parent_id 省略 → 根节点(房间)。"""
    nodes = crud.list_child_nodes(db, parent_id=parent_id, node_type=node_type)
    child_set = crud.node_ids_with_children(db, [n.node_id for n in nodes])
    return [_to_out(n, n.node_id in child_set) for n in nodes]


@router.get("/nodes/{node_id}/ancestors", response_model=List[StorageNodeOut])
def list_ancestors(node_id: int, db: Session = Depends(get_db)):
    """从根到该节点的祖先链(含自身);选了柜回填房间用。"""
    chain = crud.get_node_ancestors(db, node_id)
    if not chain:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    return [_to_out(n, False) for n in chain]


@router.post("/cabinets", response_model=StorageNodeOut)
def create_cabinet(
    payload: CabinetCreate,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """试剂柜模板新增: 房间(复用/新建) + 1 柜 + N 个 bulk 板层。"""
    try:
        cab = crud.create_cabinet(
            db,
            room_no=payload.room_no.strip(),
            cabinet_no=payload.cabinet_no.strip(),
            layer_count=payload.layer_count,
            storage_condition=payload.storage_condition,
            remark=payload.remark,
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="存在重复的位置(房间/柜/层)")
    write_audit(
        db, current, "storage.cabinet.create",
        entity_type="storage_node", entity_id=cab.node_id,
        before=None, after=model_snapshot(cab),
        source_ip=get_request_ip(request),
    )
    db.commit()
    return _to_out(cab, True)


@router.post("/fridges", response_model=StorageNodeOut)
def create_fridge(
    payload: FridgeCreate,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """普通冰箱模板新增(2~8/-20): 房间 + 1 冰箱 + N 个 bulk 隔板。"""
    try:
        fridge = crud.create_fridge(
            db,
            room_no=payload.room_no.strip(),
            fridge_name=payload.fridge_name.strip(),
            temp_category=payload.temp_category,
            shelf_count=payload.shelf_count,
            storage_condition=payload.storage_condition,
            remark=payload.remark,
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="存在重复的位置(房间/冰箱/隔板)")
    write_audit(
        db, current, "storage.fridge.create",
        entity_type="storage_node", entity_id=fridge.node_id,
        before=None, after=model_snapshot(fridge),
        source_ip=get_request_ip(request),
    )
    db.commit()
    return _to_out(fridge, True)


@router.post("/freezers", response_model=StorageNodeOut)
def create_freezer(
    payload: FreezerCreate,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """-80℃ 冰箱模板新增: 房间 + 1 冰箱 + 架/层/盒/孔整棵子树。"""
    try:
        fridge = crud.create_freezer(
            db,
            room_no=payload.room_no.strip(),
            fridge_name=payload.fridge_name.strip(),
            rack_count=payload.rack_count,
            layers_per_rack=payload.layers_per_rack,
            boxes_per_layer=payload.boxes_per_layer,
            cells_per_box=payload.cells_per_box,
            remark=payload.remark,
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="存在重复的冰箱/位置")
    write_audit(
        db, current, "storage.freezer.create",
        entity_type="storage_node", entity_id=fridge.node_id,
        before=None, after=model_snapshot(fridge),
        source_ip=get_request_ip(request),
    )
    db.commit()
    return _to_out(fridge, True)


@router.get("/cells", response_model=List[CellOut])
def list_cells(box_id: int, db: Session = Depends(get_db)):
    """盒内全部孔位 + 占用信息(热力图)。"""
    return crud.list_box_cells(db, box_id)


@router.get("/batch-cells", response_model=List[BatchCellOut])
def batch_cells(batch_id: int, db: Session = Depends(get_db)):
    """某批次当前占用的孔位(地址+样品+有效期)。空列表 = 该批次为散放(非孔位)。"""
    return crud.list_batch_cells(db, batch_id)


@router.post("/release-cells")
def release_cells(
    payload: ReleaseCellsRequest,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """出库:批量释放(取走)若干孔。每孔置 removed + 一条 OUT 流水。"""
    try:
        res = crud.release_cells(
            db, payload.cell_node_ids, current.username,
            txn_date=payload.txn_date, purpose=payload.purpose, remark=payload.remark,
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    write_audit(
        db, current, "storage.release_cells",
        entity_type="batch", entity_id=(res["batch_ids"][0] if res["batch_ids"] else None),
        before={"addresses": res["addresses"], "count": res["count"]}, after=None,
        source_ip=get_request_ip(request),
    )
    db.commit()
    return {"ok": True, **res}


@router.get("/free-cells")
def free_cells(freezer_id: int, count: int = 1, db: Session = Depends(get_db)):
    """冰箱内最多 count 个空孔(连续优先);返回孔 id 与地址。"""
    ids = crud.find_free_cells(db, freezer_id, count)
    return {
        "count": len(ids),
        "cell_node_ids": ids,
        "addresses": [crud.cell_address(db, cid) for cid in ids],
    }


@router.post("/occupy", response_model=OccupyResult)
def occupy(
    payload: OccupyRequest,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """-80℃ 孔位入库: 占用选定空孔 + 一条 IN 流水。"""
    mat = crud.get_material(db, payload.material_id)
    if not mat:
        raise HTTPException(status_code=404, detail=f"物料 #{payload.material_id} 不存在")
    if not mat.is_active:
        raise HTTPException(status_code=400, detail=f"物料 {mat.material_code} 已停用,不可入库")
    if payload.sample_labels is not None and len(payload.sample_labels) != len(payload.cell_node_ids):
        raise HTTPException(status_code=400, detail="样品号数量与孔位数量不一致")
    try:
        res = crud.occupy_cells(
            db,
            material_id=payload.material_id,
            batch_no=payload.batch_no.strip(),
            expiry_date=payload.expiry_date,
            received_date=payload.received_date,
            cell_node_ids=payload.cell_node_ids,
            operator=current.username,
            sample_labels=payload.sample_labels,
            intake_type=payload.intake_type,
            concentration=payload.concentration,
            extinction_coefficient=payload.extinction_coefficient,
            remark=payload.remark,
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="孔位占用冲突,请刷新后重试")
    write_audit(
        db, current, "storage.occupy",
        entity_type="batch", entity_id=res["batch_id"],
        before=None, after={"count": res["count"], "addresses": res["addresses"]},
        source_ip=get_request_ip(request),
    )
    db.commit()
    return res


@router.post("/occupy-from", response_model=OccupyResult)
def occupy_from(
    payload: OccupyFromRequest,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """-80℃ 起始连续填充:从起始孔起取连续 count 个孔(须全空)占用入库。"""
    mat = crud.get_material(db, payload.material_id)
    if not mat:
        raise HTTPException(status_code=404, detail=f"物料 #{payload.material_id} 不存在")
    if not mat.is_active:
        raise HTTPException(status_code=400, detail=f"物料 {mat.material_code} 已停用,不可入库")
    if payload.sample_labels is not None and len(payload.sample_labels) != payload.count:
        raise HTTPException(status_code=400, detail="样品号数量与孔位数量不一致")
    try:
        res = crud.occupy_from_start(
            db,
            start_cell_node_id=payload.start_cell_node_id,
            count=payload.count,
            material_id=payload.material_id,
            batch_no=payload.batch_no.strip(),
            expiry_date=payload.expiry_date,
            received_date=payload.received_date,
            operator=current.username,
            sample_labels=payload.sample_labels,
            intake_type=payload.intake_type,
            concentration=payload.concentration,
            extinction_coefficient=payload.extinction_coefficient,
            remark=payload.remark,
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="孔位占用冲突,请刷新后重试")
    write_audit(
        db, current, "storage.occupy_from",
        entity_type="batch", entity_id=res["batch_id"],
        before=None, after={"count": res["count"], "addresses": res["addresses"]},
        source_ip=get_request_ip(request),
    )
    db.commit()
    return res


@router.post("/release")
def release(
    payload: ReleaseRequest,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """释放(取走)某孔的样品: 占用置 removed + 一条 OUT 流水。"""
    try:
        res = crud.release_cell(db, payload.cell_node_id, current.username, payload.remark)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    write_audit(
        db, current, "storage.release",
        entity_type="batch", entity_id=res["batch_id"],
        before={"address": res["address"]}, after=None,
        source_ip=get_request_ip(request),
    )
    db.commit()
    return {"ok": True, **res}


@router.patch("/nodes/{node_id}", response_model=StorageNodeOut)
def update_node(
    node_id: int,
    payload: NodeUpdate,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """改名 / 停用 / 备注(结构性字段不可改)。"""
    existing = db.get(crud.StorageNode, node_id)
    before = model_snapshot(existing) if existing else None
    node = crud.update_node(
        db, node_id,
        label=payload.label, remark=payload.remark, is_active=payload.is_active,
    )
    if node is None:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    write_audit(
        db, current, "storage.node.update",
        entity_type="storage_node", entity_id=node.node_id,
        before=before, after=model_snapshot(node),
        source_ip=get_request_ip(request),
    )
    db.commit()
    child_set = crud.node_ids_with_children(db, [node.node_id])
    return _to_out(node, node.node_id in child_set)


@router.post("/nodes/{node_id}/children")
def add_children(
    node_id: int,
    payload: AddChildrenRequest,
    request: Request,
    current: CurrentUser = Depends(require_warehouse),
    db: Session = Depends(get_db),
):
    """往已有节点追加下级(支持异构:某架单独加层、某层加不同规格的盒、分批加架)。"""
    try:
        res = crud.add_children(
            db, node_id,
            child_type=payload.child_type, count=payload.count,
            layers_per_rack=payload.layers_per_rack,
            boxes_per_layer=payload.boxes_per_layer,
            cells_per_box=payload.cells_per_box,
            storage_condition=payload.storage_condition,
            remark=payload.remark,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="存在重复的位置编号")
    write_audit(
        db, current, "storage.node.add_children",
        entity_type="storage_node", entity_id=node_id,
        before=None, after=res,
        source_ip=get_request_ip(request),
    )
    db.commit()
    return res


@router.delete("/nodes/{node_id}")
def delete_node(
    node_id: int,
    request: Request,
    current: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除节点及其子树(仅管理员);子树下存在批次/库存则拒绝(改为停用)。"""
    before = db.get(crud.StorageNode, node_id)
    before_snap = model_snapshot(before) if before else None
    try:
        crud.delete_node(db, node_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    write_audit(
        db, current, "storage.node.delete",
        entity_type="storage_node", entity_id=node_id,
        before=before_snap, after=None,
        source_ip=get_request_ip(request),
    )
    db.commit()
    return {"ok": True}
