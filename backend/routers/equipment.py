"""
文件: backend/routers/equipment.py
用途: 仪器设备管理模块 API (Phase 3)
路径前缀: /api/equipment
端点:
    GET    /api/equipment                          设备列表(分类/状态/关键词筛选)
    POST   /api/equipment                          新增设备
    GET    /api/equipment/alerts                   设备到期预警(校验/维护/保修)
    GET    /api/equipment/categories               设备分类去重值
    GET    /api/equipment/{id}                     设备详情
    PATCH  /api/equipment/{id}                     编辑设备
    POST   /api/equipment/batch-from-mdm           从 MDM 批量引用建档(V1.4,初始化)
    POST   /api/equipment/{id}/sync-mdm            从 MDM 刷新主数据快照(V1.4)
    POST   /api/equipment/{id}/deactivate          报废设备(软删除)
    GET/POST /api/equipment/{id}/calibrations      校验记录
    GET/POST /api/equipment/{id}/maintenances      维护记录
    GET/POST /api/equipment/{id}/repairs           维修记录
    PATCH  /api/equipment/{id}/repairs/{rid}       维修完成登记
    GET/PUT  /api/equipment/{id}/warranty          保修信息(一台一条,PUT upsert)
    GET/POST /api/equipment/{id}/attachments       附件
    GET    /api/equipment/{id}/attachments/{aid}/download   附件下载/预览
    DELETE /api/equipment/{id}/attachments/{aid}   删除附件
    GET    /api/mdm/equipments                     MDM 设备搜索(透传,mdm_router)
    GET    /api/mdm/equipments/{code}              MDM 设备详情(透传,mdm_router)
    POST   /api/equipment/from-mdm/{code}          从 MDM 引用建档
鉴权:
    - 查询: 登录即可(只读)
    - 写操作: require_equipment(SYS_ADMIN / CMC_EQUIPMENT_ADMIN)
业务规则:
    - FR-EQP-031: 新增未完成维修 → 状态自动 in_repair;维修完成且无其他在修 → 恢复 in_use
    - 报废(scrapped)为软删除,历史数据保留
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

import mdm_client
from audit import get_request_ip, model_snapshot, write_audit
from auth import CurrentUser, require_equipment
from database import get_db
from models_equipment import (
    Equipment, EquipmentCalibration, EquipmentMaintenance, EquipmentRepair,
    EquipmentWarranty, EquipmentAttachment, ATTACHMENT_TAG_VALUES,
)
from schemas_equipment import (
    EquipmentCreate, EquipmentUpdate, EquipmentDeactivateRequest,
    EquipmentFromMdmRequest, EquipmentOut,
    EquipmentBatchFromMdmRequest, EquipmentBatchFromMdmResult,
    CalibrationCreate, CalibrationOut,
    MaintenanceCreate, MaintenanceOut,
    RepairCreate, RepairUpdate, RepairOut,
    WarrantyUpsert, WarrantyOut,
    AttachmentOut, EquipmentAlert,
)

router = APIRouter(prefix="/api/equipment", tags=["equipment"])

# MDM 设备主数据查询(透传)，路径与物料的 /api/mdm/materials 对齐
mdm_router = APIRouter(prefix="/api/mdm", tags=["equipment"])

# 附件存储根目录(生产环境通过环境变量指到持久盘)
UPLOAD_DIR = Path(os.getenv("EQUIPMENT_UPLOAD_DIR", "uploads/equipment"))

# 文件扩展名 → file_type
_EXT_TYPE = {
    ".pdf": "pdf",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image",
    ".doc": "doc", ".docx": "doc", ".xls": "doc", ".xlsx": "doc",
}


def _get_equipment_or_404(db: Session, equipment_id: int) -> Equipment:
    obj = db.get(Equipment, equipment_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"设备 {equipment_id} 不存在")
    return obj


def _apply_mdm_snapshot(obj: Equipment, mdm_data: dict) -> None:
    """把 MDM eqp.equipment 的身份字段整体覆盖到本地快照(V1.4,对齐 MDM 迁移 0040~0044)。
    建档(from-mdm)与刷新(sync-mdm)共用;运营字段不受影响。"""
    obj.equipment_code = mdm_data.get("equipment_code", obj.equipment_code)
    obj.equipment_no = mdm_data.get("equipment_no")
    obj.fixed_asset_no = mdm_data.get("fixed_asset_no")
    obj.name = mdm_data.get("equipment_name") or obj.name
    obj.name_en = mdm_data.get("equipment_name_en")
    obj.category = mdm_data.get("category") or obj.category
    obj.model = mdm_data.get("model")
    obj.manufacturer = mdm_data.get("manufacturer")
    obj.serial_no = mdm_data.get("serial_no")
    obj.rated_power = mdm_data.get("rated_power")
    obj.origin = mdm_data.get("origin")
    obj.supplier = mdm_data.get("supplier")
    obj.has_workstation = bool(mdm_data.get("has_workstation", False))
    obj.workstation_info = mdm_data.get("workstation_info")
    obj.purchase_date = mdm_data.get("purchase_date")
    obj.asset_value = mdm_data.get("asset_value")
    obj.mdm_status = mdm_data.get("status")
    obj.mdm_equipment_id = mdm_data.get("equipment_id")
    obj.data_source = "mdm"
    obj.mdm_synced_at = datetime.now()


# ---------------------------------------------------------------------------
# 设备预警(放在 /{id} 之前注册,避免路径吞掉 'alerts')
# ---------------------------------------------------------------------------
@router.get("/alerts", response_model=List[EquipmentAlert])
def equipment_alerts(
    days: int = Query(30, ge=1, le=365, description="预警窗口天数"),
    db: Session = Depends(get_db),
):
    """到期预警:校验(最近一次的下次校验日)、维护(下次维护日)、保修(截止日)。
    severity: 已过期/7 天内 = red,窗口内 = yellow。"""
    today = date.today()
    alerts: List[EquipmentAlert] = []

    def _severity(days_left: int) -> str:
        return "red" if days_left <= 7 else "yellow"

    # 校验: 每台设备最近一次校验记录的 next_calibration_date
    latest_cal = (
        select(
            EquipmentCalibration.equipment_id,
            EquipmentCalibration.next_calibration_date,
            func.row_number().over(
                partition_by=EquipmentCalibration.equipment_id,
                order_by=(EquipmentCalibration.calibration_date.desc(),
                          EquipmentCalibration.calibration_id.desc()),
            ).label("rn"),
        ).subquery()
    )
    cal_rows = db.execute(
        select(Equipment, latest_cal.c.next_calibration_date)
        .join(latest_cal, Equipment.equipment_id == latest_cal.c.equipment_id)
        .where(
            latest_cal.c.rn == 1,
            latest_cal.c.next_calibration_date.is_not(None),
            Equipment.is_active.is_(True),
        )
    ).all()
    for eq, due in cal_rows:
        days_left = (due - today).days
        if days_left <= days:
            alerts.append(EquipmentAlert(
                equipment_id=eq.equipment_id, equipment_code=eq.equipment_code,
                name=eq.name, alert_type="calibration", due_date=due,
                days_left=days_left, severity=_severity(days_left),
            ))

    # 维护: 每台设备最近一次维护记录的 next_maintenance_date
    latest_maint = (
        select(
            EquipmentMaintenance.equipment_id,
            EquipmentMaintenance.next_maintenance_date,
            func.row_number().over(
                partition_by=EquipmentMaintenance.equipment_id,
                order_by=(EquipmentMaintenance.maintenance_date.desc(),
                          EquipmentMaintenance.maintenance_id.desc()),
            ).label("rn"),
        ).subquery()
    )
    maint_rows = db.execute(
        select(Equipment, latest_maint.c.next_maintenance_date)
        .join(latest_maint, Equipment.equipment_id == latest_maint.c.equipment_id)
        .where(
            latest_maint.c.rn == 1,
            latest_maint.c.next_maintenance_date.is_not(None),
            Equipment.is_active.is_(True),
        )
    ).all()
    for eq, due in maint_rows:
        days_left = (due - today).days
        if days_left <= days:
            alerts.append(EquipmentAlert(
                equipment_id=eq.equipment_id, equipment_code=eq.equipment_code,
                name=eq.name, alert_type="maintenance", due_date=due,
                days_left=days_left, severity=_severity(days_left),
            ))

    # 保修: warranty_end 在窗口内或已过期
    war_rows = db.execute(
        select(Equipment, EquipmentWarranty.warranty_end)
        .join(EquipmentWarranty, Equipment.equipment_id == EquipmentWarranty.equipment_id)
        .where(Equipment.is_active.is_(True))
    ).all()
    for eq, due in war_rows:
        days_left = (due - today).days
        if days_left <= days:
            alerts.append(EquipmentAlert(
                equipment_id=eq.equipment_id, equipment_code=eq.equipment_code,
                name=eq.name, alert_type="warranty", due_date=due,
                days_left=days_left, severity=_severity(days_left),
            ))

    alerts.sort(key=lambda a: a.days_left)
    return alerts


@router.get("/categories")
def equipment_categories(db: Session = Depends(get_db)) -> List[str]:
    """设备分类去重值(用于筛选下拉)。"""
    rows = db.execute(
        select(Equipment.category).distinct().order_by(Equipment.category)
    ).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# MDM 设备主数据(权威源)查询 + 引用建档
# ---------------------------------------------------------------------------
@mdm_router.get("/equipments/{code}")
def mdm_equipment_lookup(code: str, authorization: Optional[str] = Header(default=None)):
    """从 MDM 按设备编码查询身份信息（不写本地库）。"""
    token = mdm_client.extract_bearer_token(authorization)
    data = mdm_client.get_equipment_by_code(code, token=token)
    if data is None:
        raise HTTPException(status_code=404, detail=f"MDM 中未找到设备 {code}")
    return data


@mdm_router.get("/equipments")
def mdm_equipment_search(
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    authorization: Optional[str] = Header(default=None),
):
    """搜索 MDM 设备列表（透传 MDM API）。"""
    token = mdm_client.extract_bearer_token(authorization)
    return mdm_client.search_equipments(q, page=page, page_size=page_size, token=token)


@router.post("/from-mdm/{code}", response_model=EquipmentOut, status_code=201)
def create_from_mdm(
    code: str,
    payload: EquipmentFromMdmRequest,
    request: Request,
    current: CurrentUser = Depends(require_equipment),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """从 MDM 拉取设备主数据(身份字段)，在本地建台账(data_source='mdm')，
    运营字段(位置/负责人/状态等)由请求体补充。本地已存在该编码则直接返回已有记录。"""
    existing = db.execute(
        select(Equipment).where(Equipment.equipment_code == code)
    ).scalar_one_or_none()
    if existing:
        return existing

    token = mdm_client.extract_bearer_token(authorization)
    mdm_data = mdm_client.get_equipment_by_code(code, token=token)
    if mdm_data is None:
        raise HTTPException(status_code=404, detail=f"MDM 中未找到设备 {code}")

    obj = Equipment(
        # —— 身份字段以 MDM 为准(快照见 _apply_mdm_snapshot) ——
        equipment_code=mdm_data.get("equipment_code", code),
        name=mdm_data.get("equipment_name", code),
        category=mdm_data.get("category", "其他"),
        # —— 运营字段本地补充 ——
        location_room=payload.location_room,
        location_detail=payload.location_detail,
        responsible_person=payload.responsible_person,
        commission_date=payload.commission_date,
        status=payload.status,
        remark=payload.remark,
        created_by=current.username,
        updated_by=current.username,
    )
    _apply_mdm_snapshot(obj, mdm_data)
    db.add(obj)
    db.flush()
    write_audit(
        db, current, "equipment.create_from_mdm",
        entity_type="equipment", entity_id=obj.equipment_id,
        before=None, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/batch-from-mdm", response_model=EquipmentBatchFromMdmResult)
def batch_create_from_mdm(
    payload: EquipmentBatchFromMdmRequest,
    request: Request,
    current: CurrentUser = Depends(require_equipment),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """从 MDM 批量引用建档(V1.4,台账初始化用)。
    遍历 MDM 设备列表,本地不存在的逐台拉详情落快照(data_source='mdm');
    运营字段留空待后续补录,运营状态默认 in_use。
    已存在的编码跳过;可按分类过滤;默认不含 MDM 已退役设备。"""
    token = mdm_client.extract_bearer_token(authorization)
    existing = set(db.execute(select(Equipment.equipment_code)).scalars().all())
    created = 0
    skipped_existing = 0
    skipped_filtered = 0
    failed: List[str] = []

    page = 1
    while page <= 100:  # 防御上限: 100 页 x 100 条
        resp = mdm_client.search_equipments("", page=page, page_size=100, token=token)
        items = resp.get("data") or []
        if not items:
            break
        for it in items:
            code = it.get("equipment_code")
            if not code:
                continue
            if code in existing:
                skipped_existing += 1
                continue
            if payload.categories and it.get("category") not in payload.categories:
                skipped_filtered += 1
                continue
            if not payload.include_retired and it.get("status") == "retired":
                skipped_filtered += 1
                continue
            detail = mdm_client.get_equipment_by_code(code, token=token)
            if detail is None:
                failed.append(code)
                continue
            obj = Equipment(
                equipment_code=code,
                name=detail.get("equipment_name", code),
                category=detail.get("category", "其他"),
                status="in_use",
                created_by=current.username,
                updated_by=current.username,
            )
            _apply_mdm_snapshot(obj, detail)
            db.add(obj)
            existing.add(code)
            created += 1
        pagination = (resp.get("meta") or {}).get("pagination") or resp.get("pagination") or {}
        total_pages = pagination.get("total_pages")
        if total_pages is not None and page >= total_pages:
            break
        if total_pages is None and len(items) < 100:
            break
        page += 1

    db.flush()
    write_audit(
        db, current, "equipment.batch_from_mdm",
        entity_type="equipment", entity_id=None,
        before=None,
        after={
            "created": created,
            "skipped_existing": skipped_existing,
            "skipped_filtered": skipped_filtered,
            "failed": failed,
            "categories": payload.categories,
            "include_retired": payload.include_retired,
        },
        source_ip=get_request_ip(request),
    )
    db.commit()
    return EquipmentBatchFromMdmResult(
        created=created,
        skipped_existing=skipped_existing,
        skipped_filtered=skipped_filtered,
        failed=failed,
    )


@router.post("/{equipment_id}/sync-mdm", response_model=EquipmentOut)
def sync_equipment_from_mdm(
    equipment_id: int,
    request: Request,
    current: CurrentUser = Depends(require_equipment),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """从 MDM 重新拉取主数据,整体覆盖身份字段快照(V1.4)。
    - data_source='mdm': 按编码刷新,同步 mdm_status(active/retired)
    - data_source='local': MDM 补登后按编码回挂(回填 mdm_equipment_id 并转 'mdm')
    运营字段(位置/负责人/运营状态等)不受影响。"""
    obj = _get_equipment_or_404(db, equipment_id)
    token = mdm_client.extract_bearer_token(authorization)
    mdm_data = mdm_client.get_equipment_by_code(obj.equipment_code, token=token)
    if mdm_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"MDM 中未找到设备 {obj.equipment_code}(或 MDM 服务不可用)",
        )
    before = model_snapshot(obj)
    _apply_mdm_snapshot(obj, mdm_data)
    obj.updated_by = current.username
    obj.updated_at = datetime.now()
    db.flush()
    write_audit(
        db, current, "equipment.sync_mdm",
        entity_type="equipment", entity_id=obj.equipment_id,
        before=before, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    db.refresh(obj)
    return obj


# ---------------------------------------------------------------------------
# 设备台账 CRUD
# ---------------------------------------------------------------------------
@router.get("", response_model=List[EquipmentOut])
def list_equipment(
    category: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    stmt = select(Equipment)
    if not include_inactive:
        stmt = stmt.where(Equipment.is_active.is_(True))
    if category:
        stmt = stmt.where(Equipment.category == category)
    if status:
        stmt = stmt.where(Equipment.status == status)
    if keyword:
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(
            Equipment.equipment_code.ilike(kw),
            Equipment.equipment_no.ilike(kw),
            Equipment.fixed_asset_no.ilike(kw),
            Equipment.name.ilike(kw),
            Equipment.name_en.ilike(kw),
            Equipment.model.ilike(kw),
            Equipment.manufacturer.ilike(kw),
            Equipment.serial_no.ilike(kw),
            Equipment.responsible_person.ilike(kw),
            Equipment.location_room.ilike(kw),
        ))
    stmt = stmt.order_by(Equipment.equipment_code)
    return list(db.execute(stmt).scalars().all())


@router.post("", response_model=EquipmentOut, status_code=201)
def create_equipment(
    payload: EquipmentCreate,
    request: Request,
    current: CurrentUser = Depends(require_equipment),
    db: Session = Depends(get_db),
):
    dup = db.execute(
        select(Equipment).where(Equipment.equipment_code == payload.equipment_code)
    ).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=400, detail=f"设备编号 {payload.equipment_code} 已存在")

    obj = Equipment(
        **payload.model_dump(),
        created_by=current.username,
        updated_by=current.username,
    )
    db.add(obj)
    db.flush()
    write_audit(
        db, current, "equipment.create",
        entity_type="equipment", entity_id=obj.equipment_id,
        before=None, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{equipment_id}", response_model=EquipmentOut)
def get_equipment(equipment_id: int, db: Session = Depends(get_db)):
    return _get_equipment_or_404(db, equipment_id)


@router.patch("/{equipment_id}", response_model=EquipmentOut)
def update_equipment(
    equipment_id: int,
    payload: EquipmentUpdate,
    request: Request,
    current: CurrentUser = Depends(require_equipment),
    db: Session = Depends(get_db),
):
    obj = _get_equipment_or_404(db, equipment_id)
    before = model_snapshot(obj)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)
    obj.updated_by = current.username
    obj.updated_at = datetime.now()
    db.flush()
    write_audit(
        db, current, "equipment.update",
        entity_type="equipment", entity_id=obj.equipment_id,
        before=before, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/{equipment_id}/deactivate", response_model=EquipmentOut)
def deactivate_equipment(
    equipment_id: int,
    payload: EquipmentDeactivateRequest,
    request: Request,
    current: CurrentUser = Depends(require_equipment),
    db: Session = Depends(get_db),
):
    """报废设备(软删除):is_active=False + status=scrapped,历史数据完整保留。"""
    obj = _get_equipment_or_404(db, equipment_id)
    if not obj.is_active:
        raise HTTPException(status_code=400, detail="设备已是报废状态")
    before = model_snapshot(obj)
    obj.is_active = False
    obj.status = "scrapped"
    obj.deactivated_at = datetime.now()
    obj.deactivated_by = current.username
    obj.deactivate_reason = payload.reason
    obj.updated_by = current.username
    db.flush()
    write_audit(
        db, current, "equipment.deactivate",
        entity_type="equipment", entity_id=obj.equipment_id,
        before=before, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    db.refresh(obj)
    return obj


# ---------------------------------------------------------------------------
# 校验记录
# ---------------------------------------------------------------------------
@router.get("/{equipment_id}/calibrations", response_model=List[CalibrationOut])
def list_calibrations(equipment_id: int, db: Session = Depends(get_db)):
    _get_equipment_or_404(db, equipment_id)
    return list(db.execute(
        select(EquipmentCalibration)
        .where(EquipmentCalibration.equipment_id == equipment_id)
        .order_by(EquipmentCalibration.calibration_date.desc(),
                  EquipmentCalibration.calibration_id.desc())
    ).scalars().all())


@router.post("/{equipment_id}/calibrations", response_model=CalibrationOut, status_code=201)
def create_calibration(
    equipment_id: int,
    payload: CalibrationCreate,
    request: Request,
    current: CurrentUser = Depends(require_equipment),
    db: Session = Depends(get_db),
):
    _get_equipment_or_404(db, equipment_id)
    obj = EquipmentCalibration(
        equipment_id=equipment_id,
        **payload.model_dump(),
        created_by=current.username,
    )
    db.add(obj)
    db.flush()
    write_audit(
        db, current, "equipment.calibrate",
        entity_type="equipment_calibration", entity_id=obj.calibration_id,
        before=None, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    db.refresh(obj)
    return obj


# ---------------------------------------------------------------------------
# 维护记录
# ---------------------------------------------------------------------------
@router.get("/{equipment_id}/maintenances", response_model=List[MaintenanceOut])
def list_maintenances(equipment_id: int, db: Session = Depends(get_db)):
    _get_equipment_or_404(db, equipment_id)
    return list(db.execute(
        select(EquipmentMaintenance)
        .where(EquipmentMaintenance.equipment_id == equipment_id)
        .order_by(EquipmentMaintenance.maintenance_date.desc(),
                  EquipmentMaintenance.maintenance_id.desc())
    ).scalars().all())


@router.post("/{equipment_id}/maintenances", response_model=MaintenanceOut, status_code=201)
def create_maintenance(
    equipment_id: int,
    payload: MaintenanceCreate,
    request: Request,
    current: CurrentUser = Depends(require_equipment),
    db: Session = Depends(get_db),
):
    _get_equipment_or_404(db, equipment_id)
    obj = EquipmentMaintenance(
        equipment_id=equipment_id,
        **payload.model_dump(),
        created_by=current.username,
    )
    db.add(obj)
    db.flush()
    write_audit(
        db, current, "equipment.maintain",
        entity_type="equipment_maintenance", entity_id=obj.maintenance_id,
        before=None, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    db.refresh(obj)
    return obj


# ---------------------------------------------------------------------------
# 维修记录
# ---------------------------------------------------------------------------
@router.get("/{equipment_id}/repairs", response_model=List[RepairOut])
def list_repairs(equipment_id: int, db: Session = Depends(get_db)):
    _get_equipment_or_404(db, equipment_id)
    return list(db.execute(
        select(EquipmentRepair)
        .where(EquipmentRepair.equipment_id == equipment_id)
        .order_by(EquipmentRepair.report_date.desc(), EquipmentRepair.repair_id.desc())
    ).scalars().all())


@router.post("/{equipment_id}/repairs", response_model=RepairOut, status_code=201)
def create_repair(
    equipment_id: int,
    payload: RepairCreate,
    request: Request,
    current: CurrentUser = Depends(require_equipment),
    db: Session = Depends(get_db),
):
    eq = _get_equipment_or_404(db, equipment_id)
    obj = EquipmentRepair(
        equipment_id=equipment_id,
        **payload.model_dump(),
        created_by=current.username,
    )
    db.add(obj)
    # FR-EQP-031: 未完成维修 → 设备状态自动标记"送修中"
    if obj.completion_date is None and eq.status not in ("scrapped",):
        eq.status = "in_repair"
        eq.updated_by = current.username
    db.flush()
    write_audit(
        db, current, "equipment.repair",
        entity_type="equipment_repair", entity_id=obj.repair_id,
        before=None, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{equipment_id}/repairs/{repair_id}", response_model=RepairOut)
def complete_repair(
    equipment_id: int,
    repair_id: int,
    payload: RepairUpdate,
    request: Request,
    current: CurrentUser = Depends(require_equipment),
    db: Session = Depends(get_db),
):
    """维修完成登记:回填完成日期/费用/结论;若无其他在修记录则恢复 in_use。"""
    eq = _get_equipment_or_404(db, equipment_id)
    obj = db.get(EquipmentRepair, repair_id)
    if not obj or obj.equipment_id != equipment_id:
        raise HTTPException(status_code=404, detail=f"维修记录 {repair_id} 不存在")
    before = model_snapshot(obj)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)
    db.flush()
    # 完成后,若该设备无其他未完成维修,恢复 in_use
    if obj.completion_date is not None and eq.status == "in_repair":
        open_cnt = db.execute(
            select(func.count()).select_from(EquipmentRepair).where(
                EquipmentRepair.equipment_id == equipment_id,
                EquipmentRepair.completion_date.is_(None),
            )
        ).scalar_one()
        if open_cnt == 0:
            eq.status = "in_use"
            eq.updated_by = current.username
    write_audit(
        db, current, "equipment.repair_complete",
        entity_type="equipment_repair", entity_id=obj.repair_id,
        before=before, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    db.refresh(obj)
    return obj


# ---------------------------------------------------------------------------
# 保修信息(一台设备一条,PUT upsert)
# ---------------------------------------------------------------------------
@router.get("/{equipment_id}/warranty", response_model=Optional[WarrantyOut])
def get_warranty(equipment_id: int, db: Session = Depends(get_db)):
    _get_equipment_or_404(db, equipment_id)
    return db.execute(
        select(EquipmentWarranty).where(EquipmentWarranty.equipment_id == equipment_id)
    ).scalar_one_or_none()


@router.put("/{equipment_id}/warranty", response_model=WarrantyOut)
def upsert_warranty(
    equipment_id: int,
    payload: WarrantyUpsert,
    request: Request,
    current: CurrentUser = Depends(require_equipment),
    db: Session = Depends(get_db),
):
    _get_equipment_or_404(db, equipment_id)
    obj = db.execute(
        select(EquipmentWarranty).where(EquipmentWarranty.equipment_id == equipment_id)
    ).scalar_one_or_none()
    if obj:
        before = model_snapshot(obj)
        for k, v in payload.model_dump().items():
            setattr(obj, k, v)
        obj.updated_at = datetime.now()
        action = "equipment.warranty_update"
    else:
        before = None
        obj = EquipmentWarranty(equipment_id=equipment_id, **payload.model_dump())
        db.add(obj)
        action = "equipment.warranty_create"
    db.flush()
    write_audit(
        db, current, action,
        entity_type="equipment_warranty", entity_id=obj.warranty_id,
        before=before, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    db.refresh(obj)
    return obj


# ---------------------------------------------------------------------------
# 附件
# ---------------------------------------------------------------------------
@router.get("/{equipment_id}/attachments", response_model=List[AttachmentOut])
def list_attachments(equipment_id: int, db: Session = Depends(get_db)):
    _get_equipment_or_404(db, equipment_id)
    return list(db.execute(
        select(EquipmentAttachment)
        .where(EquipmentAttachment.equipment_id == equipment_id)
        .order_by(EquipmentAttachment.attachment_id.desc())
    ).scalars().all())


@router.post("/{equipment_id}/attachments", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    equipment_id: int,
    request: Request,
    file: UploadFile = File(...),
    tag: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    current: CurrentUser = Depends(require_equipment),
    db: Session = Depends(get_db),
):
    _get_equipment_or_404(db, equipment_id)
    if tag and tag not in ATTACHMENT_TAG_VALUES:
        raise HTTPException(status_code=400, detail=f"tag 必须是 {sorted(ATTACHMENT_TAG_VALUES)} 之一")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="附件大小不得超过 50MB")

    orig_name = file.filename or "unnamed"
    ext = Path(orig_name).suffix.lower()
    # 物理文件名用 uuid,避免重名/路径穿越;原始名落库
    store_dir = UPLOAD_DIR / str(equipment_id)
    store_dir.mkdir(parents=True, exist_ok=True)
    store_path = store_dir / f"{uuid.uuid4().hex}{ext}"
    store_path.write_bytes(content)

    obj = EquipmentAttachment(
        equipment_id=equipment_id,
        file_name=orig_name,
        file_path=str(store_path),
        file_size=len(content),
        file_type=_EXT_TYPE.get(ext, "other"),
        tag=tag,
        description=description,
        uploaded_by=current.username,
    )
    db.add(obj)
    db.flush()
    write_audit(
        db, current, "equipment.attachment_upload",
        entity_type="equipment_attachment", entity_id=obj.attachment_id,
        before=None, after=model_snapshot(obj),
        source_ip=get_request_ip(request),
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{equipment_id}/attachments/{attachment_id}/download")
def download_attachment(
    equipment_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
):
    obj = db.get(EquipmentAttachment, attachment_id)
    if not obj or obj.equipment_id != equipment_id:
        raise HTTPException(status_code=404, detail=f"附件 {attachment_id} 不存在")
    path = Path(obj.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="附件文件已丢失,请联系管理员")
    media_type = {
        "pdf": "application/pdf",
        "image": "image/*",
    }.get(obj.file_type or "", "application/octet-stream")
    return FileResponse(path, filename=obj.file_name, media_type=media_type)


@router.delete("/{equipment_id}/attachments/{attachment_id}", status_code=204)
def delete_attachment(
    equipment_id: int,
    attachment_id: int,
    request: Request,
    current: CurrentUser = Depends(require_equipment),
    db: Session = Depends(get_db),
):
    obj = db.get(EquipmentAttachment, attachment_id)
    if not obj or obj.equipment_id != equipment_id:
        raise HTTPException(status_code=404, detail=f"附件 {attachment_id} 不存在")
    before = model_snapshot(obj)
    path = Path(obj.file_path)
    db.delete(obj)
    db.flush()
    write_audit(
        db, current, "equipment.attachment_delete",
        entity_type="equipment_attachment", entity_id=attachment_id,
        before=before, after=None,
        source_ip=get_request_ip(request),
    )
    db.commit()
    # 数据库删除成功后再清理物理文件(失败不回滚业务)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    return
