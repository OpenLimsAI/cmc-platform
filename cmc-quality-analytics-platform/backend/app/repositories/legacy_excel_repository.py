"""旧 Excel 数值长表只读适配；不建表、不猜测单位、不重分类历史记录。"""
import pandas as pd
from fastapi import HTTPException
from sqlalchemy import BigInteger, Date, Float, Text, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.repositories.quality_repository import QualityFilter, StagingQualityRepository


class LegacyBase(DeclarativeBase):
    pass


class LegacyQualityResult(LegacyBase):
    __tablename__ = "quality_data"
    __table_args__ = {"schema": "quality"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    data_source: Mapped[str | None] = mapped_column(Text)
    data_type: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[str | None] = mapped_column(Text)
    production_line_id: Mapped[str | None] = mapped_column(Text)
    group_id: Mapped[str | None] = mapped_column(Text)
    sample_type: Mapped[str | None] = mapped_column(Text)
    batch_number: Mapped[str | None] = mapped_column(Text)
    sub_lot: Mapped[str | None] = mapped_column(Text)
    test_type: Mapped[str | None] = mapped_column(Text)
    placement_status: Mapped[str | None] = mapped_column(Text)
    timepoint: Mapped[float | None] = mapped_column(Float)
    timepoint_unit: Mapped[str | None] = mapped_column(Text)
    sample_submission_date = mapped_column(Date)
    attribute_name: Mapped[str | None] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Float)
    source_file: Mapped[str | None] = mapped_column(Text)


class LegacyExcelRepository(StagingQualityRepository):
    def _execute(self, statement):
        try:
            return self.session.execute(statement)
        except SQLAlchemyError as exc:
            # 不用管理员账号绕过权限，也不把连接信息返回页面。
            raise HTTPException(503, "Excel 历史数据读取未就绪，请核对只读账号及 quality.quality_data 读取权限") from exc

    @staticmethod
    def _conditions():
        q = LegacyQualityResult
        return q.data_source == "QC_LIMS", q.project_id.is_not(None), q.value.is_not(None)

    def fetch_long_table(self, flt: QualityFilter) -> pd.DataFrame:
        q = LegacyQualityResult
        statement = select(q).where(*self._conditions())
        for column, value in ((q.project_id, flt.project_id), (q.sample_type, flt.sample_type)):
            if value is not None:
                statement = statement.where(column == value)
        for column, values in ((q.production_line_id, flt.production_line_ids), (q.data_type, flt.data_types), (q.attribute_name, flt.attribute_names)):
            if values:
                statement = statement.where(column.in_(values))
        records = self._execute(statement.order_by(q.id)).scalars().all()
        rows = [{column.name: getattr(record, column.name) for column in q.__table__.columns} for record in records]
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        df['source_system'] = 'legacy_excel_qc'
        df['source_result_id'] = df['id'].map(str)
        df['attribute_raw'] = df['attribute_name']
        df['attribute_canonical'] = None
        df['is_pct'] = False
        # 时间单位不能当作检测结果单位；源表没有的方法/样品编号不能凭空补值。
        for column in ('unit', 'method_code', 'method_name', 'judgement', 'sample_id', 'source_test_id', 'value_str'):
            df[column] = None
        df['received_dt'] = None
        df['data_type'] = df['data_type'].where(df['data_type'].isin(['Release', 'Stability']), 'Unknown')
        if flt.only_mapped:
            return df.iloc[:0]
        return df

    def list_projects(self, source_systems=None):
        q = LegacyQualityResult
        statement = select(q.project_id, func.count().label('n')).where(*self._conditions()).group_by(q.project_id).order_by(func.count().desc(), q.project_id)
        return [dict(row) for row in self._execute(statement).mappings()]

    def list_lines(self, project_id=None, source_systems=None):
        q = LegacyQualityResult
        statement = select(q.production_line_id).where(*self._conditions(), q.production_line_id.is_not(None)).distinct()
        if project_id is not None:
            statement = statement.where(q.project_id == project_id)
        return list(self._execute(statement.order_by(q.production_line_id)).scalars())
