"""运维看板自有历史；正式/培训同结构，培训复制排除ops_monitor数据。

只新增对象，不创建账号或授权；降级保留历史，拒绝自动删除。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '20261010_ops_monitor_v1'
down_revision = 'analytics_water_mart_perf_1009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE SCHEMA ops_monitor')
    op.create_table(
        'collection_batch',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('payload',JSONB,nullable=False),
        schema='ops_monitor',
    )
    op.create_index('ix_ops_monitor_collection_batch_at','collection_batch',['at'],schema='ops_monitor')
    op.create_table(
        'run_reference',
        sa.Column('id',sa.String(240),primary_key=True),
        sa.Column('observed_at',sa.DateTime(timezone=True),primary_key=True),
        sa.Column('task_key',sa.String(64),nullable=False),
        sa.Column('at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('payload',JSONB,nullable=False),
        schema='ops_monitor',
    )
    op.create_index('ix_ops_monitor_run_reference_task_key','run_reference',['task_key'],schema='ops_monitor')
    op.create_index('ix_ops_monitor_run_reference_at','run_reference',['at'],schema='ops_monitor')
    op.create_table(
        'access_audit_log',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('payload',JSONB,nullable=False),
        schema='ops_monitor',
    )
    op.create_index('ix_ops_monitor_access_audit_log_at','access_audit_log',['at'],schema='ops_monitor')
    op.create_table(
        'update_event',
        sa.Column('id',sa.String(240),primary_key=True),
        sa.Column('at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('status',sa.String(20),nullable=False),
        sa.Column('lease_at',sa.DateTime(timezone=True)),
        sa.Column('payload',JSONB,nullable=False),
        sa.Column('snapshot_id',sa.String(36)),
        schema='ops_monitor',
    )
    op.create_index('ix_ops_monitor_update_event_at','update_event',['at'],schema='ops_monitor')
    op.create_index('ix_ops_monitor_update_event_status','update_event',['status'],schema='ops_monitor')

def downgrade() -> None:
    raise RuntimeError('History is retained. Stop services and review a non-destructive rollback instead.')
