from subprocess import CompletedProcess

from qzx.commands.system._admin_status import (
    WINDOWS_ADMINISTRATORS_SID,
    inspect_admin_status,
)


def _inspect_windows(run_command, *, elevated=False):
    return inspect_admin_status(
        "Windows",
        run_command=run_command,
        username_provider=lambda: "Ale",
        uid_provider=lambda: 1000,
        windows_admin_provider=lambda: elevated,
    )


def test_windows_elevated_admin_does_not_need_group_probe():
    def unexpected_run(*_args, **_kwargs):
        raise AssertionError("Elevated admin should not require a subprocess.")

    result = _inspect_windows(unexpected_run, elevated=True)

    assert result["success"] is True
    assert result["is_admin"] is True
    assert result["details"]["status"] == "full_admin"
    assert "full administrative privileges" in result["message"]


def test_windows_filtered_admin_uses_stable_group_sid_not_localized_name():
    calls = []

    def run_command(args, **_kwargs):
        calls.append(args)
        stdout = (
            '"BUILTIN\\Administradores","Alias",'
            f'"{WINDOWS_ADMINISTRATORS_SID}",'
            '"Grupo usado solo para denegar"\n'
        )
        return CompletedProcess(args, 0, stdout=stdout, stderr="")

    result = _inspect_windows(run_command)

    assert calls == [["whoami", "/groups", "/fo", "csv", "/nh"]]
    assert result["is_admin"] is False
    assert result["details"]["status"] == "admin_group_no_elevation"
    assert "member of the administrators group" in result["message"]
    assert "not running with elevated privileges" in result["message"]


def test_windows_non_admin_requires_successful_group_inventory_without_sid():
    def run_command(args, **_kwargs):
        return CompletedProcess(
            args,
            0,
            stdout='"BUILTIN\\Usuarios","Alias","S-1-5-32-545","Enabled"\n',
            stderr="",
        )

    result = _inspect_windows(run_command)

    assert result["is_admin"] is False
    assert result["details"]["status"] == "not_admin"


def test_windows_group_probe_failure_is_reported_as_unknown_not_non_admin():
    def run_command(args, **_kwargs):
        return CompletedProcess(args, 1, stdout="", stderr="failure")

    result = _inspect_windows(run_command)

    assert result["is_admin"] is False
    assert result["details"]["status"] == "unknown_group_membership"
    assert "Unable to determine" in result["details"]["description"]
