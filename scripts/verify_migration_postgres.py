#!/usr/bin/env python3
"""Apply only this revision in a newly created disposable Mac PostgreSQL database."""
import importlib.util
import os
from pathlib import Path
from datetime import datetime
from dotenv import dotenv_values
from sqlalchemy import create_engine,text,URL
from alembic.migration import MigrationContext
from alembic.operations import Operations

ROOT=Path(__file__).resolve().parents[2]/'cmc-schema-migrations'
cfg=dotenv_values(ROOT/'.env')
url=URL.create('postgresql+psycopg2',username=cfg['PG_USER'],password=cfg['PG_PASSWORD'],host=cfg.get('PG_HOST','127.0.0.1'),port=int(cfg.get('PG_PORT_RD','5432')),database='postgres')
name='ops_monitor_migration_test_'+datetime.now().strftime('%Y%m%d%H%M%S')
admin=create_engine(url,isolation_level='AUTOCOMMIT')
created=False
try:
    with admin.connect() as c:
        print('test host/port:',url.host,url.port,'new isolated database:',name)
        c.execute(text(f'CREATE DATABASE "{name}"'));created=True
    engine=create_engine(url.set(database=name))
    spec=importlib.util.spec_from_file_location('revision',ROOT/'alembic/versions/cmc_analytics/20261010_ops_monitor_v1.py')
    revision=importlib.util.module_from_spec(spec);spec.loader.exec_module(revision)
    with engine.begin() as c:
        with Operations.context(MigrationContext.configure(c)):revision.upgrade()
        names=c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='ops_monitor' ORDER BY 1")).scalars().all()
        assert names==['access_audit_log','collection_batch','run_reference','update_event']
        c.execute(text("INSERT INTO ops_monitor.collection_batch (id,at,payload) VALUES ('test',now(),'{\"mode\":\"isolated_test\"}')"))
        assert c.execute(text('SELECT count(*) FROM ops_monitor.collection_batch')).scalar_one()==1
    engine.dispose();print('PASS: actual PostgreSQL migration and isolated JSONB write/read')
finally:
    if created:
        with admin.connect() as c:c.execute(text(f'DROP DATABASE "{name}"'))
    admin.dispose()
