from sqlalchemy import Column, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase


class MetaBase(DeclarativeBase):
    pass


class DimMethod(MetaBase):
    __tablename__ = "dim_method"
    __table_args__ = {"schema": "meta"}

    method_code = Column(String, primary_key=True)
    method_name = Column(String)
    std_minutes = Column(Numeric(6, 2))
    target_days = Column(Integer)


class DimEmployee(MetaBase):
    __tablename__ = "dim_employee"
    __table_args__ = {"schema": "meta"}

    employee_id = Column(String, primary_key=True)
    employee_name = Column(String)
    department = Column(String)
