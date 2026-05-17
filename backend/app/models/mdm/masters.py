# ORM 映射：cmc_mdm 主数据表（v0.1 单一事实源）
#   - mdm_quality.method_master：检验方法主数据
#   - mdm_core.employee_master：员工主数据
# 这些表的 DDL 应由 cmc_mdm owner 维护；本 app 仅做读写消费，不在此持有 alembic 迁移。
from sqlalchemy import Column, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase


class MdmBase(DeclarativeBase):
    pass


class MethodMaster(MdmBase):
    """cmc_mdm.mdm_quality.method_master"""
    __tablename__ = "method_master"
    __table_args__ = {"schema": "mdm_quality"}

    method_code = Column(String, primary_key=True)
    method_name = Column(String)
    std_minutes = Column(Numeric(6, 2))
    target_days = Column(Integer)


class EmployeeMaster(MdmBase):
    """cmc_mdm.mdm_core.employee_master"""
    __tablename__ = "employee_master"
    __table_args__ = {"schema": "mdm_core"}

    employee_id = Column(String, primary_key=True)
    employee_name = Column(String)
    department = Column(String)
    group_id = Column(String)
    status = Column(String)
