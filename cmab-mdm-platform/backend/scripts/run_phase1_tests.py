"""Portable wrapper for the existing isolated DB runner (Windows checkouts use CRLF).

Only for deploy/docker-compose.phase1-test.yml's disposable PostgreSQL instance.
This is contract/database regression, not real Casdoor/browser E2E acceptance.
"""
import os
import subprocess
import sys
from pathlib import Path

if os.environ.get("TEST_DB") != "cmab_test" or os.environ.get("TEST_DB_HOST") != "postgres":
    raise SystemExit("Refusing unknown test database; use disposable phase1-test Compose")

target = Path("/tmp/mdm-phase1-run-tests.sh")
target.write_text(Path("scripts/run_tests.sh").read_text())
sources = ["app/domains/prs/pm_reference.py", "app/domains/prs/pm_links.py", "app/api/v1/pm_links.py"]
subprocess.run(["ruff", "check", "--no-cache", *sources, "tests/test_pm_reference.py", "tests/test_project_pm_link.py"], check=True)
subprocess.run(["mypy", "--cache-dir=/tmp/mypy-cache", "--follow-imports=silent", *sources], check=True)
checks = [
    "tests/test_pm_reference.py", "tests/test_project_pm_link.py",
    "tests/test_project_crud.py", "tests/test_project_relationship_audit.py",
    "tests/test_project_milestone_team.py", "tests/test_project_state_machine.py",
    "tests/test_db_release.py",
]
sys.exit(subprocess.call(["bash", str(target), *(sys.argv[1:] or checks), "-o", "cache_dir=/tmp/pytest-cache"]))
