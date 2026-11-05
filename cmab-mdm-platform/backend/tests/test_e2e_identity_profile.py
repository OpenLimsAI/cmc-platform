"""Profile selection changes only newly-owned local fixtures, never an existing IdP."""
import pytest


def test_default_profile_keeps_official_comparison_mode():
    from scripts.e2e_runtime import identity_profile

    assert identity_profile("official-v4") == {}


def test_restricted_profile_has_only_the_approved_clients_and_fixed_image():
    from scripts.e2e_runtime import identity_profile

    profile = identity_profile("restricted-v11")
    assert profile["approved_own_policy_v9"] is True
    assert profile["dcr_self_logout_clients"] == ("mdm-signing-login", "mdm-signing-portal", "mdm-signing-pm")
    assert profile["idp_image"] == "sha256:56e11171cfb2022215a46e2c55b15c9c5734162bdd2f058892cde29e356d42ca"


def test_unknown_profile_is_rejected():
    from scripts.e2e_runtime import identity_profile

    with pytest.raises(ValueError):
        identity_profile("production")
