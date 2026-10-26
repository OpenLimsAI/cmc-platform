"""Read-only checks tying one application release to one database migration head.

This module never migrates or stamps a database. Deployment runs migrations with
explicit authority; application startup and health checks only verify readiness.
"""
from functools import lru_cache
from pathlib import Path

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Date, Float, String, inspect, text
from sqlalchemy.engine import Connection, make_url

# Columns introduced/changed by the equipment release. Checking actual columns
# also catches an incorrectly stamped database, not just a missing migration.
EQUIPMENT_COLUMNS = {
    "status": (String, False),
    "equipment_status": (String, False),
    "manufacture_date": (Date, True),
    "total_weight": (Float, True),
}
COUNT_TABLES = ("eqp.equipment", "mm.material", "srs.substance", "prs.project",
                "ars.asset", "tgt.target")


@lru_cache(maxsize=1)
def migration_scripts() -> ScriptDirectory:
    return ScriptDirectory(str(Path(__file__).resolve().parents[2] / "alembic"))


def database_target(url: str) -> tuple[str | None, int, str | None]:
    """No usernames/passwords in diagnostic output."""
    parsed = make_url(url)
    return parsed.host, parsed.port or 5432, parsed.database


def revision_status(current: list[str], scripts: ScriptDirectory) -> tuple[str, str]:
    heads = scripts.get_heads()
    if len(heads) != 1:
        raise ValueError("Release must have exactly one migration head")
    expected = heads[0]
    if current == [expected]:
        return "ready", expected
    # Missing metadata, multiple heads, or unknown/newer revisions must not be
    # treated as permission to upgrade an arbitrary database.
    if len(current) != 1:
        return "invalid_revision", expected
    ancestors = {rev.revision for rev in scripts.walk_revisions()}
    if current[0] in ancestors:
        return "pending_migrations", expected
    return "invalid_revision", expected


def equipment_column_issues(columns: list[dict]) -> list[str]:
    actual = {column["name"]: column for column in columns}
    issues = []
    for name, (column_type, nullable) in EQUIPMENT_COLUMNS.items():
        column = actual.get(name)
        if column is None:
            issues.append(f"eqp.equipment.{name}: missing")
        elif not isinstance(column["type"], column_type) or column["nullable"] != nullable:
            issues.append(f"eqp.equipment.{name}: type/nullability mismatch")
    return issues


def inspect_database(connection: Connection, *, counts: bool = False) -> dict:
    """Caller supplies a read-only transaction, including for startup checks."""
    current = sorted(MigrationContext.configure(
        connection, opts={"version_table_schema": "public"}
    ).get_current_heads())
    status, expected = revision_status(current, migration_scripts())
    result = {
        "database": connection.execute(text("SELECT current_database()")).scalar_one(),
        "current_revisions": current,
        "expected_revision": expected,
        "status": status,
        "issues": [],
    }
    inspector = inspect(connection)
    if status == "ready":
        columns = inspector.get_columns("equipment", schema="eqp") if inspector.has_table(
            "equipment", schema="eqp"
        ) else []
        result["issues"] = equipment_column_issues(columns)
        if result["issues"]:
            result["status"] = "schema_mismatch"
    if counts:
        result["counts"] = {}
        for table in COUNT_TABLES:
            schema, name = table.split(".")
            result["counts"][table] = connection.execute(
                text(f'SELECT count(*) FROM "{schema}"."{name}"')
            ).scalar_one() if inspector.has_table(name, schema=schema) else None
    return result
