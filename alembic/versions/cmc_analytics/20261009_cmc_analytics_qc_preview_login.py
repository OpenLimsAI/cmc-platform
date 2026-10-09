"""Create a dedicated NOINHERIT preview login from a private password file."""
from alembic import context, op
import os
import stat
from psycopg2 import sql
from psycopg2.extensions import encrypt_password

revision = 'analytics_qc_login_20261009'
down_revision = 'analytics_qc_catalog_20261009'
branch_labels = None
depends_on = None
LOGIN = 'qc_report_preview_login'
ROLE = 'qc_report_preview_writer'
VARIABLE = 'QC_REPORT_ANALYTICS_PASSWORD_FILE'
DATABASES = ('cmc_analytics', 'cmc_analytics_training')


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError("Preview login creation requires an online verified target")
    bind = op.get_bind()
    database = bind.exec_driver_sql("SELECT current_database()").scalar()
    if database not in DATABASES:
        raise RuntimeError("Unexpected preview login database")
    existing = bind.exec_driver_sql(
        "SELECT rolsuper,rolcanlogin,rolinherit,rolcreaterole,rolcreatedb,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='" + LOGIN + "'"
    ).fetchone()
    if existing is not None and tuple(existing) != (False,True,False,False,False,False,False):
        raise RuntimeError("Existing preview login attributes differ; do not change a shared account")
    connection = bind.connection.driver_connection
    if existing is None:
        path = os.environ.get(VARIABLE)
        if not path:
            raise RuntimeError(VARIABLE + " must name a private credential file")
        fd = os.open(path,os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd,"r") as f:
            info = os.fstat(f.fileno())
            if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o600
                    or info.st_uid!=os.geteuid() or info.st_size>4096):
                raise RuntimeError("Credential file must be executor-owned regular mode 0600")
            password = f.read().rstrip("\n")
        if len(password)<32 or any(c in password for c in "\n\r\x00"):
            raise RuntimeError("Password must be a single value of at least 32 characters")
        try:
            verifier = encrypt_password(password,LOGIN,connection,algorithm="scram-sha-256")
            with connection.cursor() as cur:
                cur.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %s").format(sql.Identifier(LOGIN)),(verifier,))
        except Exception:
            raise RuntimeError("Preview login creation failed; credentials suppressed") from None
    with connection.cursor() as cur:
        cur.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(ROLE),sql.Identifier(LOGIN)))
        cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database),sql.Identifier(LOGIN)))
        if LOGIN == "qc_report_snapshot_login":
            cur.execute(sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(sql.Identifier(LOGIN)))


def downgrade():
    raise RuntimeError("Do not remove runtime accounts or revoke snapshot access without release review")
