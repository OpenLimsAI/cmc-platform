"""Phase-1 Excel quality dashboard: dedicated application tables and DB roles.

Only schema is migrated; source workbooks and passwords are environment-local.
IF NOT EXISTS permits adopting the Mac pilot tables without removing its data.
No RD/raw/staging tables or MDM identities are changed.
"""
from alembic import op

revision = "cmc_analytics_qad_phase1"
down_revision = "cmc_analytics_manual_metric_gluc"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qad_reader') THEN
            CREATE ROLE qad_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qad_importer') THEN
            CREATE ROLE qad_importer LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
          END IF;
          EXECUTE format('GRANT CONNECT ON DATABASE %I TO qad_reader, qad_importer', current_database());
        END $$;
    """)
    op.execute("""
        CREATE SCHEMA IF NOT EXISTS quality;
        CREATE TABLE IF NOT EXISTS quality.quality_data (
            id BIGSERIAL PRIMARY KEY,
            data_source TEXT NOT NULL,
            data_type TEXT NOT NULL,
            project_id TEXT,
            production_line_id TEXT,
            group_id TEXT,
            sample_type TEXT,
            batch_number TEXT,
            sub_lot TEXT,
            test_type TEXT,
            placement_status TEXT,
            timepoint DOUBLE PRECISION,
            timepoint_unit TEXT,
            sample_submission_date DATE,
            attribute_name TEXT NOT NULL,
            value DOUBLE PRECISION NOT NULL,
            source_file TEXT,
            update_time TIMESTAMP DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_qad_project ON quality.quality_data(project_id);
        CREATE INDEX IF NOT EXISTS idx_qad_attribute ON quality.quality_data(attribute_name);
        CREATE INDEX IF NOT EXISTS idx_qad_batch ON quality.quality_data(batch_number);
        CREATE INDEX IF NOT EXISTS idx_qad_source_file ON quality.quality_data(data_source, source_file);
        CREATE TABLE IF NOT EXISTS quality.import_history (
            id BIGSERIAL PRIMARY KEY,
            source_file TEXT NOT NULL,
            file_sha256 TEXT NOT NULL,
            row_count BIGINT NOT NULL,
            imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            database_user TEXT NOT NULL DEFAULT current_user
        );
        CREATE INDEX IF NOT EXISTS idx_qad_import_file ON quality.import_history(source_file, id DESC);
        GRANT USAGE ON SCHEMA quality TO qad_reader, qad_importer;
        GRANT SELECT ON quality.quality_data, quality.import_history TO qad_reader;
        GRANT SELECT, INSERT, DELETE ON quality.quality_data TO qad_importer;
        GRANT SELECT, INSERT ON quality.import_history TO qad_importer;
        GRANT USAGE, SELECT ON SEQUENCE quality.quality_data_id_seq, quality.import_history_id_seq TO qad_importer;
    """)


def downgrade():
    raise RuntimeError("Quality data and import history are retained. Back up and arrange an explicit rollback; no automatic DROP.")
