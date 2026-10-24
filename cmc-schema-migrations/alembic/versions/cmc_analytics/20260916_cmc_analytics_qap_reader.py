"""Dedicated QAP reader; no business data or table changes.

Training shares table migrations but must not inherit the production application's
login grants. Its own identity/permissions require a separately reviewed migration.
Passwords are provisioned outside version control and never embedded here.
"""
from alembic import op

revision = 'cmc_analytics_qap_reader'
down_revision = 'cmc_analytics_qad_phase1'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    DO $$ BEGIN
      IF current_database() = 'cmc_analytics_training' THEN
        RETURN;
      END IF;
      IF current_database() <> 'cmc_analytics' THEN
        RAISE EXCEPTION 'QAP reader migration targets cmc_analytics only';
      END IF;
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qap_reader') THEN
        RAISE EXCEPTION 'qap_reader already exists; review ownership and grants before migration';
      END IF;
      CREATE ROLE qap_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
        NOINHERIT NOREPLICATION NOBYPASSRLS;
      ALTER ROLE qap_reader SET default_transaction_read_only = on;
      GRANT CONNECT ON DATABASE cmc_analytics TO qap_reader;
      GRANT USAGE ON SCHEMA staging, quality TO qap_reader;
      GRANT SELECT ON TABLE staging.stg_sample, staging.stg_test,
        staging.stg_result, quality.quality_data TO qap_reader;
    END $$;
    """)


def downgrade():
    # Fail closed: active configuration/password handling is an operator action.
    # Never DROP OWNED/CASCADE or silently invalidate another application's login.
    raise RuntimeError('Restore QAP configuration, review and revoke the four SELECT grants, '
                       'two schema USAGE grants and CONNECT, then disable qap_reader login. '
                       'Arrange an explicit reviewed rollback; no automatic role/data deletion.')
