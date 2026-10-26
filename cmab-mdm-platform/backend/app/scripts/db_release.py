"""Explicit-target, read-only release preflight/postflight. Prints safe JSON."""
import argparse
import json
from datetime import UTC, datetime

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.core.db_release import database_target, inspect_database


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--expected-port", required=True, type=int)
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--expected-revision", help="Pin the migration head recorded at preflight")
    parser.add_argument("--allow-pending", action="store_true",
                        help="Preflight only: allow known older revisions, never unknown/missing ones")
    parser.add_argument("--counts", action="store_true")
    args = parser.parse_args()
    expected = (args.expected_host, args.expected_port, args.expected_database)
    report = {"environment": args.environment, "checked_at": datetime.now(UTC).isoformat(),
              "host": args.expected_host, "port": args.expected_port,
              "database": args.expected_database}
    if any(database_target(url) != expected for url in (
        settings.DATABASE_URL, settings.DATABASE_URL_SYNC
    )):
        report.update(status="target_mismatch", issues=["Application/migration target differs from expected target"])
    else:
        engine = create_engine(settings.DATABASE_URL_SYNC, connect_args={
            "connect_timeout": 5, "options": "-c statement_timeout=10000"
        })
        try:
            with engine.connect() as connection:
                connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                report.update(inspect_database(connection, counts=args.counts))
            if report["database"] != args.expected_database:
                report.update(status="target_mismatch", issues=["Connected to unexpected database"])
            elif args.expected_revision and report["expected_revision"] != args.expected_revision:
                report.update(status="release_changed", issues=["Migration head changed during release"])
        except Exception as exc:
            # Exception strings can contain connection credentials; do not print them.
            report.update(status="check_failed", issues=[type(exc).__name__])
        finally:
            engine.dispose()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    accepted = {"ready", "pending_migrations"} if args.allow_pending else {"ready"}
    return 0 if report["status"] in accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
