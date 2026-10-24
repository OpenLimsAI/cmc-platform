"""Add water final-result plotting metadata; preserve every source value."""
from alembic import op
import sqlalchemy as sa

revision = 'analytics_water_final_20261009'
down_revision = 'analytics_qc_login_20261009'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.exec_driver_sql('SELECT current_database()').scalar() not in ('cmc_analytics','cmc_analytics_training'):
        raise RuntimeError('Unexpected water staging migration database')
    bind.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    for name, kind in [('plot_value',sa.Numeric()),('result_kind',sa.Text()),
                       ('result_operator',sa.Text()),('result_bound',sa.Numeric()),
                       ('plot_value_rule',sa.Text()),('result_role',sa.Text())]:
        op.add_column('stg_lv_test_result_wide',sa.Column(name,kind,nullable=True),schema='staging')
    bind.exec_driver_sql("COMMENT ON COLUMN staging.stg_lv_test_result_wide.plot_value IS 'Derived plotting coordinate; censored zero is not an exact measurement; source fields unchanged'")
    bind.exec_driver_sql("COMMENT ON COLUMN staging.stg_lv_test_result_wide.plot_value_rule IS 'Versioned plot-only rule; not a statistical substitution rule'")


def downgrade():
    raise RuntimeError('Keep source and derived evidence; rollback applications without dropping water metadata')
