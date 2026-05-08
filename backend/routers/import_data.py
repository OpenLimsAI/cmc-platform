"""
文件: backend/routers/import_data.py
用途: Excel 物料主数据导入 API
流程:
    /api/import/materials/dry-run  ── 上传 Excel,返回字段映射、校验结果(不写库)
    /api/import/materials/commit   ── 拿干跑后的逐行清洗结果,执行 UPSERT,记录 import_log
    /api/import/logs               ── 查看历史导入

关键点:
    - pd.read_excel(dtype={'代码': str}) 严格保留前导 0
    - N/A、空字符串、NaN 统一转 NULL
    - 自动从文件提取新分类入库;新单位可选自动加入或拒绝
    - 干跑结果按行返回,前端可直接展示
"""
from __future__ import annotations

import io
import math
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import select

import crud
from database import get_db
from models import Material, ImportLog, UnitDict, CategoryDict
from schemas import (
    ImportPreviewResult,
    ImportPreviewRow,
    ImportCommitRequest,
    ImportCommitResult,
    ImportLogOut,
)

router = APIRouter(prefix="/api/import", tags=["import"])


# Excel 中文表头 → 数据库字段
HEADER_MAP: Dict[str, str] = {
    "分类": "category",
    "代码": "material_code",
    "物料名称": "name_cn",
    "级别": "grade",
    "生产商": "manufacturer",
    "规格/型号": "spec_model",
    "规格": "spec_model",          # 兼容写法
    "型号": "spec_model",          # 兼容写法
    "货号": "catalog_no",
    "单位": "unit",
    "包装规格": "package_spec",
    "备注": "remark",
}

NULL_LIKE = {"", "n/a", "na", "nan", "none", "null", "-", "—"}


def _clean(v: Any) -> Optional[str]:
    """把 N/A / 空白 / NaN 统一转 NULL,其余 strip 后返回字符串。"""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    s = str(v).strip()
    if s == "" or s.lower() in NULL_LIKE:
        return None
    return s


def _normalize_row(raw: dict) -> dict:
    """把表头中文 → 字段名,N/A → None。"""
    out: Dict[str, Any] = {}
    for k, v in raw.items():
        key = HEADER_MAP.get(str(k).strip())
        if not key:
            continue  # 忽略 序号 等非业务字段
        out[key] = _clean(v)
    return out


def _read_excel_bytes(content: bytes) -> pd.DataFrame:
    """读取 Excel,强制把"代码"列当字符串读,保留前导 0。"""
    # 用 dtype=str 全部当字符串读最安全;Excel 数字会自动 round-trip 成字符串
    df = pd.read_excel(io.BytesIO(content), dtype=str, keep_default_na=False)
    # 列名 strip
    df.columns = [str(c).strip() for c in df.columns]
    return df


@router.post("/materials/dry-run", response_model=ImportPreviewResult)
async def dry_run(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """干跑:校验并返回每一行的处理结果(INSERT / UPDATE / ERROR)。"""
    content = await file.read()
    try:
        df = _read_excel_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel 读取失败: {e}")

    # 现存物料代码集合(用于判断 INSERT/UPDATE)
    existing_codes = set(db.execute(select(Material.material_code)).scalars().all())
    existing_units = set(db.execute(select(UnitDict.unit)).scalars().all())
    existing_categories = set(db.execute(select(CategoryDict.category)).scalars().all())

    seen_codes: set = set()
    rows_out: List[ImportPreviewRow] = []
    insert_cnt = update_cnt = error_cnt = 0
    leading_zero: set = set()
    new_categories: set = set()
    new_units: set = set()

    for idx, raw in enumerate(df.to_dict(orient="records"), start=2):  # Excel 第 2 行起为数据
        norm = _normalize_row(raw)
        errors: List[str] = []
        warnings: List[str] = []

        code = norm.get("material_code")
        name = norm.get("name_cn")
        unit = norm.get("unit")
        category = norm.get("category")

        # 必填校验
        if not code:
            errors.append("material_code(代码) 为空")
        if not name:
            errors.append("name_cn(物料名称) 为空")
        if not unit:
            errors.append("unit(单位) 为空")

        # 唯一性(本次文件内)
        if code:
            if code in seen_codes:
                errors.append(f"代码 {code} 在本文件内重复")
            seen_codes.add(code)

        # 前导 0 提示
        if code and code.startswith("0"):
            leading_zero.add(code)
            warnings.append(f"代码 {code} 含前导 0,请确认 Excel 未被自动去 0")

        # 单位字典
        if unit and unit not in existing_units:
            new_units.add(unit)
            warnings.append(f"单位 '{unit}' 不在字典中,提交时将自动加入")

        # 分类字典(自动追加,不算错)
        if category and category not in existing_categories:
            new_categories.add(category)

        if errors:
            action = "ERROR"
            error_cnt += 1
        elif code in existing_codes:
            action = "UPDATE"
            update_cnt += 1
        else:
            action = "INSERT"
            insert_cnt += 1

        rows_out.append(ImportPreviewRow(
            row_index=idx,
            material_code=code,
            name_cn=name,
            action=action,
            errors=errors,
            warnings=warnings,
            raw=norm,
        ))

    return ImportPreviewResult(
        total_rows=len(rows_out),
        insert_count=insert_cnt,
        update_count=update_cnt,
        error_count=error_cnt,
        leading_zero_codes=sorted(leading_zero),
        new_categories=sorted(new_categories),
        new_units=sorted(new_units),
        rows=rows_out,
    )


@router.post("/materials/commit", response_model=ImportCommitResult)
def commit(payload: ImportCommitRequest, db: Session = Depends(get_db)):
    """正式提交:执行 UPSERT 并写入 import_log。
    要求传入干跑后的逐行清洗结果(rows: list of dict),错误行将被忽略并计入 failed_rows。
    """
    # 1) 先建 import_log(占位,后续更新统计)
    log = ImportLog(
        file_name=payload.file_name,
        operator=payload.operator,
        total_rows=len(payload.rows),
    )
    db.add(log)
    db.flush()
    import_id = log.import_id

    # 2) 收集需要的新分类 / 新单位
    new_categories: set = set()
    new_units: set = set()
    for r in payload.rows:
        if c := r.get("category"):
            new_categories.add(c)
        if u := r.get("unit"):
            new_units.add(u)

    # 自动追加分类
    if new_categories:
        crud.upsert_categories(db, list(new_categories))
    # 单位:按配置决定是否自动追加
    if payload.auto_create_units and new_units:
        crud.upsert_units(db, list(new_units))

    # 3) 逐行 UPSERT
    inserted = updated = failed = 0
    errors: List[Dict[str, Any]] = []

    existing_units = set(db.execute(select(UnitDict.unit)).scalars().all())

    for r in payload.rows:
        try:
            code = r.get("material_code")
            name = r.get("name_cn")
            unit = r.get("unit")
            if not code or not name or not unit:
                raise ValueError("代码 / 物料名称 / 单位 为必填")
            if unit not in existing_units:
                raise ValueError(f"单位 '{unit}' 不在字典中")

            obj = db.get(Material, code)
            if obj:
                # UPDATE — 只覆盖文件中提供的字段(safety_stock/is_active 不在导入范围)
                for f in ("category", "name_cn", "grade", "manufacturer",
                          "spec_model", "catalog_no", "unit", "package_spec", "remark"):
                    if f in r:
                        setattr(obj, f, r.get(f))
                obj.import_batch_id = import_id
                updated += 1
            else:
                # INSERT
                obj = Material(
                    material_code=code,
                    category=r.get("category"),
                    name_cn=name,
                    grade=r.get("grade"),
                    manufacturer=r.get("manufacturer"),
                    spec_model=r.get("spec_model"),
                    catalog_no=r.get("catalog_no"),
                    unit=unit,
                    package_spec=r.get("package_spec"),
                    remark=r.get("remark"),
                    safety_stock=Decimal("0"),
                    is_active=True,
                    import_batch_id=import_id,
                )
                db.add(obj)
                inserted += 1
        except Exception as e:
            failed += 1
            errors.append({"row": r, "error": str(e)})

    # 4) 更新 import_log 统计
    log.inserted_rows = inserted
    log.updated_rows = updated
    log.failed_rows = failed
    log.error_detail = {"errors": errors} if errors else None
    db.commit()

    return ImportCommitResult(
        import_id=import_id,
        total_rows=len(payload.rows),
        inserted_rows=inserted,
        updated_rows=updated,
        failed_rows=failed,
    )


@router.get("/logs", response_model=List[ImportLogOut])
def list_logs(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.execute(
        select(ImportLog).order_by(ImportLog.import_id.desc()).limit(limit)
    ).scalars().all()
    return list(rows)
