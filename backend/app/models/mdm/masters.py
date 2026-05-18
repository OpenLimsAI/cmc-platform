# ORM 映射：cmc_analytics.mdm 主数据表（v0.1 单一事实源，2026-05-18 从已删除的 cmc_mdm 库迁入）
#   - mdm.test_method：检验方法主数据（PK=method_code，79 行）
#   - mdm.personnel：员工主数据（PK=employee_id，29 行）
# 软删除：mart.dim_method / mart.dim_employee 视图带 WHERE deleted_at IS NULL；admin 端读写需与之对齐。
# 表 DDL 由数据侧维护；本 app 仅做读写消费，不持有 alembic 迁移。
from sqlalchemy import Column, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase


class MdmBase(DeclarativeBase):
    pass


class MethodMaster(MdmBase):
    """cmc_analytics.mdm.test_method"""
    __tablename__ = "test_method"
    __table_args__ = {"schema": "mdm"}

    method_code = Column(String, primary_key=True)
    method_name = Column(String, nullable=False)
    std_minutes = Column(Numeric(6, 2))
    target_days = Column(Integer)
    description = Column(Text)
    status = Column(String, nullable=False, server_default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(String)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by = Column(String)
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(String)


class EmployeeMaster(MdmBase):
    """cmc_analytics.mdm.personnel"""
    __tablename__ = "personnel"
    __table_args__ = {"schema": "mdm"}

    employee_id = Column(String, primary_key=True)
    employee_name = Column(String, nullable=False)
    department = Column(String, nullable=False, server_default="药学及技术转移部")
    group_id = Column(String)
    status = Column(String, nullable=False, server_default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(String)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by = Column(String)
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(String)
