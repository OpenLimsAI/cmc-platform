"""Rotate existing gmp_etl password from a private environment-specific file.

No role creation, grants, or business data changes. Offline SQL is intentionally
unsupported; password material must never enter generated SQL artifacts.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat

from alembic import context, op
from psycopg2 import sql
from psycopg2.extensions import encrypt_password

revision = "gmp_etl_password_20261008"
down_revision = "gmp_qc_point_raw_20261008"
branch_labels = None
depends_on = None


def _private_value(variable: str) -> str:
    name = os.environ.get(variable)
    if not name:
        raise RuntimeError(f"{variable} must point to a private credential file")
    path = Path(name)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.geteuid() or info.st_size > 4096):
            raise RuntimeError("Credential file must be owned by the executor and have mode 0600")
        value = stream.read().rstrip("\n")
    if not value or "\n" in value or "\r" in value or "\x00" in value:
        raise RuntimeError("Credential file must contain one nonempty value")
    return value


def _connection():
    if context.is_offline_mode():
        raise RuntimeError("Password rotation requires an online migration; offline SQL is forbidden")
    bind = op.get_bind()
    row = bind.exec_driver_sql(
        "SELECT current_database(),rolcanlogin,rolsuper "
        "FROM pg_roles WHERE rolname='gmp_etl'"
    ).fetchone()
    if row is None or tuple(row) != ("cmc_gmp", True, False):
        raise RuntimeError("Expected cmc_gmp and an existing non-superuser gmp_etl login")
    return bind.connection.driver_connection


def _set_verifier(connection, verifier: str) -> None:
    # Use the DBAPI cursor so SQLAlchemy never renders the credential in errors.
    # PostgreSQL receives a verifier, rather than the plaintext password.
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("ALTER ROLE {} PASSWORD %s").format(sql.Identifier("gmp_etl")),
                (verifier,),
            )
    except Exception:
        raise RuntimeError("gmp_etl password operation failed; transaction must be rolled back") from None


def upgrade():
    connection = _connection()
    password = _private_value("GMP_ETL_PASSWORD_FILE")
    if len(password) < 24:
        raise RuntimeError("New password must contain at least 24 characters")
    try:
        verifier = encrypt_password(password, "gmp_etl", connection, algorithm="scram-sha-256")
    except Exception:
        raise RuntimeError("Could not generate a SCRAM verifier") from None
    _set_verifier(connection, verifier)


def downgrade():
    connection = _connection()
    verifier = _private_value("GMP_ETL_ROLLBACK_VERIFIER_FILE")
    if not re.fullmatch(
        r"(?:md5[0-9a-f]{32}|SCRAM-SHA-256\$[0-9]+:[A-Za-z0-9+/=]+\$[A-Za-z0-9+/=]+:[A-Za-z0-9+/=]+)",
        verifier,
    ):
        raise RuntimeError("Rollback requires the previously backed-up gmp_etl verifier")
    _set_verifier(connection, verifier)
