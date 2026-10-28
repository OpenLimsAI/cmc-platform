"""Bootstrap target/identity contract. Real-DB CLI tests follow this first red."""
import copy

import pytest
from app.scripts.sso_bootstrap import BootstrapPlan, ensure_runtime_target
from pydantic import ValidationError


def plan_dict():
    return {
        "database_host": "postgres", "database_port": 5432, "database": "cmab_test_bootstrap",
        "issuer": "https://identity.example.com", "organization": "isolated",
        "operator_subject": "explicit-subject-one", "operator_ref": "ssh:isolated-operator / approved test",
        "reason": "Explicitly approved new isolated administrator bootstrap",
        "accounts": [
            {"username": "isolated.one", "subject": "explicit-subject-one", "email": "one@example.com", "full_name": "Isolated One"},
            {"username": "isolated.two", "subject": "explicit-subject-two", "email": "two@example.com", "full_name": "Isolated Two"},
        ],
    }


def check(plan, **changes):
    runtime = {"database_url": "postgresql+asyncpg://fixture@postgres:5432/cmab_test_bootstrap",
               "issuer": plan.issuer, "organization": plan.organization,
               "native_enabled": False, "oidc_enabled": True}
    runtime.update(changes)
    return ensure_runtime_target(plan, **runtime)


def test_accepts_explicit_target_without_fetching_or_matching_external_profiles():
    plan = BootstrapPlan.model_validate(plan_dict())
    check(plan)
    assert [a.subject for a in plan.accounts] == ["explicit-subject-one", "explicit-subject-two"]


def test_accepts_only_the_single_explicitly_authorized_administrator():
    raw = plan_dict()
    raw["accounts"] = raw["accounts"][:1]
    plan = BootstrapPlan.model_validate(raw)
    check(plan)
    assert len(plan.accounts) == 1
    assert plan.accounts[0].subject == "explicit-subject-one"


@pytest.mark.parametrize("field,value", [
    ("subject", "explicit-subject-one"), ("username", "ISOLATED.ONE"), ("email", "ONE@example.com"),
])
def test_rejects_duplicate_identity_name_or_contact(field, value):
    raw = plan_dict()
    raw["accounts"][1][field] = value
    with pytest.raises(ValidationError):
        BootstrapPlan.model_validate(raw)


@pytest.mark.parametrize("change", [
    {"operator_subject": "unlisted-operator"}, {"issuer": "https://identity.example.com/?token=bad"},
    {"accounts": []}, {"unexpected_grant": "admin"},
    {"reason": "      "}, {"operator_ref": "      "},
])
def test_rejects_ambiguous_or_broadened_plan(change):
    raw = plan_dict()
    raw.update(change)
    with pytest.raises(ValidationError):
        BootstrapPlan.model_validate(raw)


def test_requires_real_contact_instead_of_inventing_placeholder():
    raw = copy.deepcopy(plan_dict())
    raw["accounts"][0]["email"] = ""
    with pytest.raises(ValidationError):
        BootstrapPlan.model_validate(raw)


@pytest.mark.parametrize("runtime", [
    {"database_url": "postgresql://fixture@other-db:5432/cmab_test_bootstrap"},
    {"database_url": "postgresql://fixture@postgres:5432/unknown_shared_db"},
    {"database_url": "postgresql://fixture@postgres:5433/cmab_test_bootstrap"},
    {"issuer": "https://other-issuer.example.com"}, {"organization": "other-org"},
    {"native_enabled": True}, {"oidc_enabled": False},
    {"database_url": "postgresql://fixture@postgres:5432/cmab_test_bootstrap?hostaddr=192.0.2.1"},
    {"database_url": "postgresql://fixture@postgres:5432/cmab_test_bootstrap?service=other-target"},
    {"database_url": "postgresql://fixture@postgres:5432/cmab_test_bootstrap?sslmode=require"},
])
def test_refuses_wrong_target_or_native_fallback(runtime):
    with pytest.raises(ValueError):
        check(BootstrapPlan.model_validate(plan_dict()), **runtime)
