"""Fail-closed boundary for disposable fault/restart fixtures, never business APIs."""
import pytest
from scripts.e2e_control import check_fault_target, unique_process, validate_request


def request(action="snapshot", **fields):
    return {"id": "a" * 32, "action": action, **fields}


def test_control_accepts_only_the_finite_documented_actions():
    for action in ["snapshot", "stop-mdm", "start-mdm", "restart-apps"]:
        assert validate_request(request(action))["action"] == action


@pytest.mark.parametrize("changes", [{"action": "exec"}, {"id": "../secret"}, {"command": "anything"}, {"action": "fault-next-link", "project_code": "1;DROP TABLE prs.project"}])
def test_control_rejects_shell_sql_path_or_extra_fields(changes):
    with pytest.raises(ValueError):
        validate_request(request(**changes))


def test_fault_requires_an_existing_unlinked_project_with_no_create_request():
    assert check_fault_target({"id": 2, "linked": False, "requested": False, "fault_exists": False}) == 2
    for key in ["linked", "requested", "fault_exists"]:
        with pytest.raises(ValueError):
            check_fault_target({"id": 2, "linked": False, "requested": False, "fault_exists": False, key: True})


def test_fault_rejects_missing_or_ambiguous_target():
    for target in [None, {"id": 0}, {"id": "2"}, {"id": 2}]:
        with pytest.raises(ValueError):
            check_fault_target(target)


def test_restart_never_guesses_which_process_to_stop():
    assert unique_process([42]) == 42
    for candidates in [[], [1, 2], [0], ["42"]]:
        with pytest.raises(ValueError):
            unique_process(candidates)
