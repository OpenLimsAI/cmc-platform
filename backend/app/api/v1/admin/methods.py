import io

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.auth import verify_admin
from app.core.database import get_mdm_db
from app.models.meta.dims import DimMethod

router = APIRouter()


class MethodItem(BaseModel):
    method_code: str
    method_name: str | None
    std_minutes: float | None
    target_days: int | None


class MethodCreate(BaseModel):
    method_code: str
    method_name: str | None = None
    std_minutes: float | None = None
    target_days: int | None = None


class MethodUpdate(BaseModel):
    method_name: str | None = None
    std_minutes: float | None = None
    target_days: int | None = None


@router.get("", response_model=list[MethodItem], dependencies=[Depends(verify_admin)])
async def list_methods(db: AsyncSession = Depends(get_mdm_db)):
    result = await db.execute(select(DimMethod).order_by(DimMethod.method_code))
    return [MethodItem(
        method_code=r.method_code,
        method_name=r.method_name,
        std_minutes=r.std_minutes,
        target_days=r.target_days,
    ) for r in result.scalars()]


@router.post("", response_model=MethodItem, dependencies=[Depends(verify_admin)])
async def create_method(body: MethodCreate, db: AsyncSession = Depends(get_mdm_db)):
    existing = await db.execute(select(DimMethod).where(DimMethod.method_code == body.method_code))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="该方法编码已存在")
    row = DimMethod(method_code=body.method_code, method_name=body.method_name, std_minutes=body.std_minutes, target_days=body.target_days)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return MethodItem(method_code=row.method_code, method_name=row.method_name, std_minutes=row.std_minutes, target_days=row.target_days)


@router.put("/{method_code}", response_model=MethodItem, dependencies=[Depends(verify_admin)])
async def update_method(
    method_code: str,
    body: MethodUpdate,
    db: AsyncSession = Depends(get_mdm_db),
):
    result = await db.execute(select(DimMethod).where(DimMethod.method_code == method_code))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="未找到该检验方法")
    if body.method_name is not None:
        row.method_name = body.method_name
    if body.std_minutes is not None:
        row.std_minutes = body.std_minutes
    if body.target_days is not None:
        row.target_days = body.target_days
    await db.commit()
    await db.refresh(row)
    return MethodItem(method_code=row.method_code, method_name=row.method_name, std_minutes=row.std_minutes, target_days=row.target_days)


@router.post("/upload", dependencies=[Depends(verify_admin)])
async def upload_methods(file: UploadFile, db: AsyncSession = Depends(get_mdm_db)):
    content = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)

    sheet_name = "method_hours" if "method_hours" in wb.sheetnames else wb.sheetnames[0]
    ws = wb[sheet_name]

    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    try:
        col_code = headers.index("method_code") + 1
        col_name = next(
            i + 1 for i, h in enumerate(headers)
            if h and ("ANALDESC" in str(h) or "method_name" in str(h))
        )
        col_min = next(
            i + 1 for i, h in enumerate(headers)
            if h and ("std_" in str(h).lower() or "min" in str(h).lower())
            and i != (col_name - 1)
        )
    except (ValueError, StopIteration) as e:
        raise HTTPException(status_code=422, detail=f"Excel 列名无法识别: {e}")

    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        code = row[col_code - 1]
        name = row[col_name - 1]
        mins_raw = row[col_min - 1]
        if not code:
            continue
        mins = round(float(mins_raw), 2) if mins_raw is not None else None
        rows.append({"method_code": str(code), "method_name": str(name) if name else None, "std_minutes": mins})

    if not rows:
        raise HTTPException(status_code=422, detail="Excel 中无有效数据行")

    stmt = insert(DimMethod).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["method_code"],
        set_={"method_name": stmt.excluded.method_name, "std_minutes": stmt.excluded.std_minutes},
    )
    await db.execute(stmt)
    await db.commit()
    return {"upserted": len(rows)}
