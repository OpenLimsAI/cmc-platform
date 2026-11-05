"""Pure provisioning/cleanup safety contracts; no Docker or identity substitute."""
import pytest
from scripts.e2e_runtime import RunSpec, validate_fixture, validate_owned_resources


def test_runtime_uses_only_the_four_approved_loopback_ports(tmp_path):
    spec = RunSpec("mdm-e2e-contract", tmp_path)
    assert spec.port_bindings == {"idp": "127.0.0.1:19081", "mdm": "127.0.0.1:19090", "pm": "127.0.0.1:19091", "portal": "127.0.0.1:19092"}
    assert spec.client_names == ("mdm-signing-login", "mdm-signing-proof", "mdm-signing-pm", "mdm-signing-portal", "mdm-signing-pm-delegation")


@pytest.mark.parametrize("run_id", ["", "maibo", "../../maibo", "mdm-e2e-" + "x" * 80])
def test_runtime_refuses_ambiguous_or_escaping_run_names(tmp_path, run_id):
    with pytest.raises(ValueError):
        RunSpec(run_id, tmp_path)


def test_independent_loopback_environment_never_reuses_experience_ports(tmp_path):
    spec = RunSpec("mdm-e2e-independent", tmp_path, 100)
    assert spec.port_bindings == {"idp": "127.0.0.1:19181", "mdm": "127.0.0.1:19190", "pm": "127.0.0.1:19191", "portal": "127.0.0.1:19192"}
    assert spec.origin("mdm") == "http://localhost:19190"
    for value in (-1, 1, 200, 65535):
        with pytest.raises(ValueError):
            RunSpec("mdm-e2e-independent", tmp_path, value)


def test_independent_browser_cookie_host_must_differ_from_retained_localhost(tmp_path):
    spec = RunSpec("mdm-e2e-independent", tmp_path, 100, "127.0.0.1")
    assert spec.origin("mdm") == "http://127.0.0.1:19190"
    assert spec.origin("idp") == "http://127.0.0.1:19181"
    assert all(value.startswith('127.0.0.1:') for value in spec.port_bindings.values())
    for host in ('0.0.0.0', 'maibo', 'example.com'):
        with pytest.raises(ValueError):
            RunSpec("mdm-e2e-independent", tmp_path, 100, host)


def test_artifacts_cannot_escape_the_owned_run_directory(tmp_path):
    spec = RunSpec("mdm-e2e-contract", tmp_path)
    assert spec.output("screenshots/one.jpg") == tmp_path / spec.run_id / "screenshots/one.jpg"
    with pytest.raises(ValueError):
        spec.output("../another-run/credential.json")
    with pytest.raises(ValueError):
        spec.output(str(tmp_path / "outside.json"))


def resources():
    manifest = {"run_id": "mdm-e2e-contract", "containers": {"mdm-e2e-contract-pg": "owned-id"}}
    owned = {"Name": "/mdm-e2e-contract-pg", "Id": "owned-id", "Config": {"Labels": {"mdm.test.run": manifest["run_id"]}}}
    return manifest, owned


def test_cleanup_requires_both_exact_container_id_and_label():
    manifest, owned = resources()
    validate_owned_resources(manifest, [owned], [])
    owned["Id"] = "new-owner-same-name"
    with pytest.raises(ValueError):
        validate_owned_resources(manifest, [owned], [])
    owned["Id"] = "owned-id"
    owned["Config"]["Labels"]["mdm.test.run"] = "another-run"
    with pytest.raises(ValueError):
        validate_owned_resources(manifest, [owned], [])


def test_cleanup_refuses_network_with_an_unowned_member():
    manifest, owned = resources()
    network = {"Name": "mdm-e2e-contract-internal", "Labels": {"mdm.test.run": manifest["run_id"]}, "Containers": {"alien": {"Name": "user-database"}}}
    with pytest.raises(ValueError):
        validate_owned_resources(manifest, [owned], [network])


def test_fixture_is_limited_to_the_explicit_synthetic_identities():
    fixture = {"syntheticOnly": True, "users": {key: {"username": "e2e." + key, "password": "x" * 48} for key in ("signer", "other")}}
    validate_fixture(fixture)
    fixture["users"]["signer"]["username"] = "guo.admin"
    with pytest.raises(ValueError):
        validate_fixture(fixture)
