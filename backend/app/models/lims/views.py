# ORM 映射：app_rd schema 下的只读视图，不做任何写操作
from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class TestTaskMonitor(Base):
    """映射 app_rd.v_test_task_monitor 视图（37129行，主查询来源）"""
    __tablename__ = "v_test_task_monitor"
    __table_args__ = {"schema": "app_rd"}

    # 主键（视图无真实主键，用 test_id 作为映射主键）
    test_id = Column(String, primary_key=True)
    sample_id = Column(String)
    sample_name = Column(Text)
    batch_number = Column(String)
    project_id = Column(String)
    group_id = Column(String)
    tester = Column(String)
    method_code = Column(String)
    method_name = Column(Text)
    sample_status = Column(String)
    test_status = Column(String)
    sample_received_dt = Column(DateTime)
    test_started_dt = Column(DateTime)
    test_completed_dt = Column(DateTime)
    test_authorised_dt = Column(DateTime)
    groupleader_received_dt = Column(DateTime)
    assigned_dt = Column(DateTime)
    request_dt = Column(DateTime)


class SampleOverview(Base):
    """映射 app_rd.v_sample_overview 视图（16573行）"""
    __tablename__ = "v_sample_overview"
    __table_args__ = {"schema": "app_rd"}

    sample_id = Column(String, primary_key=True)
    project_id = Column(String)
    sample_name = Column(Text)
    batch_number = Column(String)
    sample_type = Column(String)
    test_type = Column(String)
    request_dt = Column(DateTime)
    request_person = Column(String)
    sampled_dt = Column(DateTime)
    received_dt = Column(DateTime)
    started_dt = Column(DateTime)
    completed_dt = Column(DateTime)
    authorised_dt = Column(DateTime)
    tester = Column(String)
    completer = Column(String)
    authoriser = Column(String)
    group_id = Column(String)
    status = Column(String)
