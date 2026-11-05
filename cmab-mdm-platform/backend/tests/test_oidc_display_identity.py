"""Display identity follows PM naming, never business identity or authorization."""
import pytest
from app.domains.auth.oidc.display_identity import identity_presentation


@pytest.mark.parametrize("display,expected", [
    ("Synthetic signer", "Synthetic signer"), ("中文同事", "中文同事"),
    ("  中文同事  ", "中文同事"), ("甲" * 60, "甲" * 50),
    ("", "e2e.signer"), ("   ", "e2e.signer"), (None, "e2e.signer"), (False, "e2e.signer"),
])
def test_display_name_with_username_fallback_matches_pm(display, expected):
    result = identity_presentation("e2e.signer", display)
    assert result == {"identityUsername": "e2e.signer", "displayName": expected}
    assert set(result).isdisjoint({"user_id", "roles", "permissions", "username", "full_name"})


@pytest.mark.parametrize("username", [None, "", " ", 1, "e2e.signer\n"])
def test_unverified_or_malformed_name_cannot_be_invented_from_local_admin(username):
    assert identity_presentation(username, "系统管理员") is None
