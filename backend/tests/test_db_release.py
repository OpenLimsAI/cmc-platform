"""Release safeguards, with failure paths mocked; never mutate a business DB."""
import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core import database, db_release
from app.scripts import db_release as cli
from sqlalchemy import Date, Float, Integer, String


def scripts(heads=("new",)):
    return SimpleNamespace(
        get_heads=lambda: list(heads),
        walk_revisions=lambda: [SimpleNamespace(revision=r) for r in ("new", "old")],
    )


@pytest.mark.parametrize(("current", "expected"), [
    (["new"], "ready"), (["old"], "pending_migrations"),
    ([], "invalid_revision"), (["future"], "invalid_revision"),
    (["old", "new"], "invalid_revision"),
])
def test_revision_status(current, expected):
    assert db_release.revision_status(current, scripts()) == (expected, "new")


@pytest.mark.parametrize("heads", [(), ("a", "b")])
def test_release_requires_single_head(heads):
    with pytest.raises(ValueError, match="exactly one"):
        db_release.revision_status(["old"], scripts(heads))


def columns():
    return [
        {"name": "status", "type": String(), "nullable": False},
        {"name": "equipment_status", "type": String(), "nullable": False},
        {"name": "manufacture_date", "type": Date(), "nullable": True},
        {"name": "total_weight", "type": Float(), "nullable": True},
    ]


def test_correct_equipment_columns():
    assert db_release.equipment_column_issues(columns()) == []


@pytest.mark.parametrize("change", ["missing", "type", "nullable"])
def test_weight_column_drift(change):
    actual = columns()
    if change == "missing":
        actual.pop()
    elif change == "type":
        actual[-1]["type"] = Integer()
    else:
        actual[-1]["nullable"] = False
    assert "total_weight" in db_release.equipment_column_issues(actual)[0]


def test_current_revision_does_not_hide_missing_column(monkeypatch):
    monkeypatch.setattr(db_release, "migration_scripts", lambda: scripts())
    monkeypatch.setattr(db_release.MigrationContext, "configure", lambda *a, **k:
                        SimpleNamespace(get_current_heads=lambda: ("new",)))
    inspector = SimpleNamespace(has_table=lambda *a, **k: True,
                                get_columns=lambda *a, **k: columns()[:-1])
    monkeypatch.setattr(db_release, "inspect", lambda conn: inspector)
    connection = MagicMock()
    connection.execute.return_value.scalar_one.return_value = "cmab_test"
    assert db_release.inspect_database(connection)["status"] == "schema_mismatch"


def test_target_does_not_expose_credentials():
    assert db_release.database_target("postgresql://secret_user:secret_pass@postgres/cmab_test") == (
        "postgres", 5432, "cmab_test"
    )


def test_cli_wrong_database_stops_before_connect(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["db_release", "--environment", "test",
        "--expected-host", "postgres", "--expected-port", "5432",
        "--expected-database", "wrong_database"])
    connect = MagicMock(side_effect=AssertionError("must not connect"))
    monkeypatch.setattr(cli, "create_engine", connect)
    assert cli.main() == 1
    connect.assert_not_called()
    assert json.loads(capsys.readouterr().out)["status"] == "target_mismatch"


@pytest.mark.parametrize("state", ["pending_migrations", "schema_mismatch", "unavailable"])
async def test_startup_rejects_unready_database(monkeypatch, state):
    monkeypatch.setattr(database, "database_readiness", AsyncMock(return_value={"status": state}))
    with pytest.raises(RuntimeError, match="Database release mismatch"):
        await database.init_db()


async def test_startup_accepts_ready_database(monkeypatch):
    monkeypatch.setattr(database, "database_readiness", AsyncMock(return_value={"status": "ready"}))
    await database.init_db()


@pytest.mark.parametrize(("state", "http_status"), [("ready", 200), ("pending_migrations", 503),
                                                     ("unavailable", 503), ("schema_mismatch", 503)])
async def test_health_reports_readiness(monkeypatch, state, http_status):
    from app import main
    monkeypatch.setattr(main, "database_readiness", AsyncMock(return_value={"status": state}))
    response = await main._health_payload()
    assert response.status_code == http_status
    assert json.loads(response.body)["database"]["status"] == state


async def test_connection_failure_is_sanitized(monkeypatch):
    monkeypatch.setattr(database, "engine", SimpleNamespace(
        connect=MagicMock(side_effect=RuntimeError("secret_password"))
    ))
    report = await database.database_readiness()
    assert report == {"status": "unavailable"}
    assert "secret_password" not in str(report)
