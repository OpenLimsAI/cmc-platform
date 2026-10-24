#!/usr/bin/env python3
"""用记录型Alembic操作对照实际ORM；不连接或修改数据库。"""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'cmc-platform-monitor/backend'))
from app.store import Base


class RecordedOperations:
    def __init__(self):
        self.metadata = sa.MetaData()
        self.statements = []

    def execute(self, text):
        self.statements.append(text)

    def create_table(self, name, *columns, schema):
        return sa.Table(name, self.metadata, *columns, schema=schema)

    def create_index(self, name, table, columns, schema):
        target = self.metadata.tables[f'{schema}.{table}']
        sa.Index(name, *(target.c[c] for c in columns))


recorder = RecordedOperations()
module = ModuleType('alembic')
module.op = recorder
sys.modules['alembic'] = module
path = ROOT / 'cmc-schema-migrations/alembic/versions/cmc_analytics/20261010_ops_monitor_v1.py'
spec = importlib.util.spec_from_file_location('monitor_migration', path)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)
assert migration.down_revision == 'analytics_water_mart_perf_1009'
assert len(migration.revision) <= 32
migration.upgrade()
assert recorder.statements == ['CREATE SCHEMA ops_monitor']
assert set(recorder.metadata.tables) == set(Base.metadata.tables)


def signature(table):
    return (
        [(c.name, str(c.type), c.nullable, c.primary_key,
          getattr(c.type, 'timezone', None)) for c in table.columns],
        sorted((i.name, tuple(c.name for c in i.columns), i.unique) for i in table.indexes),
    )


for name, table in Base.metadata.tables.items():
    assert signature(table) == signature(recorder.metadata.tables[name]), name
try:
    migration.downgrade()
except RuntimeError:
    pass
else:
    raise AssertionError('Downgrade must retain history')
print('PASS: 4 tables, columns/types/nullability/keys/indexes match ORM; downgrade retains history; no database connection')
