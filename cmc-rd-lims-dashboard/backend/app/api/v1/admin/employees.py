import io

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.auth import verify_admin
from app.core.auth import CurrentUser
from app.core.database import get_mdm_db
from app.models.mdm.masters import EmployeeMaster as DimEmployee

router = APIRouter()


class EmployeeItem(BaseModel):
    employee_id: str
    employee_name: str | None
    department: str | None


class EmployeeCreate(BaseModel):
    employee_id: str
    employee_name: str | None = None
    department: str | None = None


class EmployeeUpdate(BaseModel):
    employee_name: str | None = None
    department: str | None = None


@router.get("", response_model=list[EmployeeItem], dependencies=[Depends(verify_admin)])
async def list_employees(db: AsyncSession = Depends(get_mdm_db)):
    result = await db.execute(
        select(DimEmployee)
        .where(DimEmployee.deleted_at.is_(None))
        .order_by(DimEmployee.employee_id)
    )
    return [EmployeeItem(
        employee_id=r.employee_id,
        employee_name=r.employee_name,
        department=r.department,
    ) for r in result.scalars()]


@router.post("", response_model=EmployeeItem)
async def create_employee(
    body: EmployeeCreate,
    db: AsyncSession = Depends(get_mdm_db),
    user: CurrentUser = Depends(verify_admin),
):
    existing = await db.execute(select(DimEmployee).where(DimEmployee.employee_id == body.employee_id))
    row = existing.scalar_one_or_none()
    if row is not None:
        if row.deleted_at is None:
            raise HTTPException(status_code=409, detail="该员工 ID 已存在")
        # 已软删除：复活并覆盖名称 / 部门
        row.employee_name = body.employee_name or row.employee_name
        if body.department is not None:
            row.department = body.department
        row.deleted_at = None
        row.deleted_by = None
        row.updated_by = user.username
    else:
        row = DimEmployee(
            employee_id=body.employee_id,
            employee_name=body.employee_name,
            department=body.department or "药学及技术转移部",
            created_by=user.username,
            updated_by=user.username,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return EmployeeItem(employee_id=row.employee_id, employee_name=row.employee_name, department=row.department)


@router.put("/{employee_id}", response_model=EmployeeItem)
async def update_employee(
    employee_id: str,
    body: EmployeeUpdate,
    db: AsyncSession = Depends(get_mdm_db),
    user: CurrentUser = Depends(verify_admin),
):
    result = await db.execute(
        select(DimEmployee)
        .where(DimEmployee.employee_id == employee_id, DimEmployee.deleted_at.is_(None))
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="未找到该员工")
    if body.employee_name is not None:
        row.employee_name = body.employee_name
    if body.department is not None:
        row.department = body.department
    row.updated_by = user.username
    await db.commit()
    await db.refresh(row)
    return EmployeeItem(employee_id=row.employee_id, employee_name=row.employee_name, department=row.department)


@router.post("/upload")
async def upload_employees(
    file: UploadFile,
    db: AsyncSession = Depends(get_mdm_db),
    user: CurrentUser = Depends(verify_admin),
):
    content = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)

    sheet_name = "testers" if "testers" in wb.sheetnames else wb.sheetnames[0]
    ws = wb[sheet_name]

    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    try:
        col_id = next(i + 1 for i, h in enumerate(headers) if h and "employee_id" in str(h).lower())
        col_name = next(i + 1 for i, h in enumerate(headers) if h and "employee_name" in str(h).lower())
    except StopIteration as e:
        raise HTTPException(status_code=422, detail=f"Excel 列名无法识别: {e}")

    col_dept = next(
        (i + 1 for i, h in enumerate(headers) if h and "department" in str(h).lower()), None
    )

    # 按 employee_id 去重（同号取最后一行）：同一 VALUES 里重复主键会让
    # ON CONFLICT DO UPDATE 报 "cannot affect row a second time" 整体 500
    rows: dict[str, dict] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        eid = row[col_id - 1]
        ename = row[col_name - 1]
        if not eid or not ename:
            continue
        dept = row[col_dept - 1] if col_dept else None
        rows[str(eid)] = {
            "employee_id": str(eid),
            "employee_name": str(ename),
            "department": str(dept) if dept else "药学及技术转移部",
            "created_by": user.username,
            "updated_by": user.username,
        }

    if not rows:
        raise HTTPException(status_code=422, detail="Excel 中无有效数据行")

    stmt = insert(DimEmployee).values(list(rows.values()))
    stmt = stmt.on_conflict_do_update(
        index_elements=["employee_id"],
        set_={
            "employee_name": stmt.excluded.employee_name,
            "department": stmt.excluded.department,
            "deleted_at": None,
            "deleted_by": None,
            # ON CONFLICT 不触发 ORM onupdate，审计字段要显式写
            "updated_at": func.now(),
            "updated_by": user.username,
        },
    )
    await db.execute(stmt)
    await db.commit()
    return {"upserted": len(rows)}
