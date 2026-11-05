"""Reproducible opt-in identity/project regression; not real browser acceptance."""
import os
import subprocess
import sys
from pathlib import Path

if os.environ.get("TEST_DB") != "cmab_test" or os.environ.get("TEST_DB_HOST") != "postgres":
    raise SystemExit("Refusing unknown database; use disposable verification Compose")
os.environ.update(LOGURU_LEVEL="WARNING", APP_LOG_LEVEL="WARNING")
sources = ["app/domains/auth/oidc", "app/api/v1/oidc.py", "app/api/v1/auth.py", "app/shared/permissions.py",
           "app/core/auth_mode.py", "app/domains/auth/services.py",
           "app/core/config.py", "app/core/logging.py", "app/main.py", "app/domains/prs/pm_create.py",
           "app/domains/prs/pm_links.py", "app/api/v1/pm_links.py", "app/scripts/oidc_identity.py", "app/scripts/sso_bootstrap.py",
           "scripts/e2e_runtime.py", "scripts/e2e_services.py", "scripts/e2e_evidence.py", "scripts/e2e_control.py", "scripts/e2e_signature_form.py"]
tests = ["tests/test_e2e_identity_profile.py", "tests/test_e2e_signature_form.py", "tests/test_sso_bootstrap.py", "tests/test_sso_bootstrap_cli.py", "tests/test_oidc_only_native_rejection.py", "tests/test_oidc_only_http_rejection.py",
         "tests/test_oidc_fresh_signature.py", "tests/test_oidc_display_identity.py", "tests/test_oidc_signature_hint.py", "tests/test_oidc_signature_business.py", "tests/test_oidc_v4_userinfo.py", "tests/test_e2e_runtime_safety.py", "tests/test_e2e_control.py",
         "tests/test_oidc_protocol.py", "tests/test_oidc_provider.py", "tests/test_oidc_logout.py",
         "tests/test_oidc_sessions.py", "tests/test_oidc_endpoints.py", "tests/test_oidc_recovery_urls.py", "tests/test_pm_create.py"]
subprocess.run(["ruff", "check", "--no-cache", *sources, *tests], check=True)
subprocess.run(["mypy", "--cache-dir=/tmp/mypy-phase2", "--follow-imports=silent",
                "app/domains/auth/oidc", "app/api/v1/oidc.py", "app/domains/prs/pm_create.py"], check=True)
subprocess.run(["mypy", "--cache-dir=/tmp/mypy-bootstrap", "--follow-imports=silent", "--strict",
                "app/scripts/sso_bootstrap.py"], check=True)
subprocess.run(["mypy", "--cache-dir=/tmp/mypy-full-app", "app"], check=True)
checks = [*tests, "tests/test_pm_reference.py", "tests/test_project_pm_link.py", "tests/test_auth_security.py",
          "tests/test_force_password_change_gate.py", "tests/test_password_policy.py", "tests/test_session_policy.py",
          "tests/test_jwt_rs256.py", "tests/test_signature.py", "tests/test_account_audit.py", "tests/test_admin_audit.py",
          "tests/test_project_crud.py", "tests/test_project_relationship_audit.py", "tests/test_project_milestone_team.py",
          "tests/test_project_state_machine.py", "tests/test_db_release.py", "tests/test_signature_audit_link.py",
          "tests/test_asset_crud.py", "tests/test_asset_state_machine.py", "tests/test_asset_substance_link.py",
          "tests/test_check_sameness.py", "tests/test_dashboard.py", "tests/test_global_search.py",
          "tests/test_import_equipment_excel.py", "tests/test_material_batch.py", "tests/test_material_crud.py",
          "tests/test_material_substance_link.py", "tests/test_project_asset_link.py"]
runner = Path("/tmp/mdm-phase2-run-tests.sh")
runner.write_text(Path("scripts/run_tests.sh").read_text())
sys.exit(subprocess.call(["bash", str(runner), *(sys.argv[1:] or checks), "-o", "cache_dir=/tmp/pytest-phase2"]))
