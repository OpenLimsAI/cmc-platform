"""Remove the locally generated water-point history after verified backup.

The Oracle current mirror and staging mappings remain. A private verifier file
is optional only for catching Mac up across the earlier password revision while
preserving its existing login credential in the same migration transaction.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat

from alembic import context, op
from psycopg2 import sql

revision = "gmp_qc_point_nohist_20261008"
down_revision = "gmp_qc_meta_seq_20261008"
branch_labels = None
depends_on = None

SCHEMA = "raw_gmp_lims_labvantage"
HISTORY = f"{SCHEMA}.s_samplepoint_history"


def _private_text(variable: str) -> str:
    name = os.environ.get(variable)
    if not name:
        raise RuntimeError(f"{variable} must identify the reviewed private backup")
    fd = os.open(Path(name), os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.geteuid() or info.st_size > 65536):
            raise RuntimeError("Backup manifest/verifier must be executor-owned regular file, mode 0600")
        return stream.read()


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError("History removal requires an online verified backup")
    bind = op.get_bind()
    if bind.exec_driver_sql("SELECT current_database()").scalar() != "cmc_gmp":
        raise RuntimeError("Expected cmc_gmp")
    manifest = json.loads(_private_text("QC_POINT_HISTORY_BACKUP_MANIFEST"))
    if manifest.get("database") != "cmc_gmp" or manifest.get("table") != HISTORY:
        raise RuntimeError("History backup target does not match")
    dump = Path(manifest["dump_path"])
    digest = hashlib.sha256(dump.read_bytes()).hexdigest()
    if digest != manifest["dump_sha256"] or not manifest.get("restore_verified"):
        raise RuntimeError("History backup checksum/restore verification is missing or differs")

    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '30s'")
    op.execute("SET LOCAL TimeZone = 'UTC'")
    # Freeze both objects before comparing the reviewed snapshot with live data.
    op.execute(f"LOCK TABLE {SCHEMA}.s_samplepoint, {HISTORY} IN ACCESS EXCLUSIVE MODE")
    count, record_digest = bind.exec_driver_sql(
        f"SELECT count(*),md5(COALESCE(string_agg(to_jsonb(h)::text, '' ORDER BY history_id),'')) FROM {HISTORY} h"
    ).one()
    if count != manifest["history_rows"] or record_digest != manifest["history_record_md5"]:
        raise RuntimeError("History changed after backup; take and verify a fresh backup")

    op.execute(f"DROP TRIGGER samplepoint_history ON {SCHEMA}.s_samplepoint")
    # RESTRICT protects any consumer not identified in the release inventory.
    op.execute(f"DROP TABLE {HISTORY} RESTRICT")
    op.execute(f"DROP FUNCTION {SCHEMA}.record_samplepoint_history() RESTRICT")
    op.execute(f"DROP FUNCTION {SCHEMA}.reject_samplepoint_history_change() RESTRICT")

    if os.environ.get("QC_KEEP_GMP_ETL_VERIFIER_FILE"):
        verifier = _private_text("QC_KEEP_GMP_ETL_VERIFIER_FILE").rstrip("\n")
        if not re.fullmatch(
            r"(?:md5[0-9a-f]{32}|SCRAM-SHA-256\$[0-9]+:[A-Za-z0-9+/=]+\$[A-Za-z0-9+/=]+:[A-Za-z0-9+/=]+)",
            verifier,
        ):
            raise RuntimeError("Catch-up preservation requires the original gmp_etl verifier")
        try:
            with bind.connection.driver_connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("ALTER ROLE {} PASSWORD %s").format(sql.Identifier("gmp_etl")),
                    (verifier,),
                )
        except Exception:
            raise RuntimeError("Could not preserve the existing Mac gmp_etl verifier") from None


def downgrade():
    raise RuntimeError("History removal needs reviewed backup restoration and a new recovery migration; no empty-table downgrade")
