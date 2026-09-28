"""Cross-platform administrative-status probes for isAdmin."""

from __future__ import annotations


WINDOWS_ADMINISTRATORS_SID = "S-1-5-32-544"


def inspect_admin_status(
    system_name,
    *,
    run_command,
    username_provider,
    uid_provider,
    windows_admin_provider,
):
    """Collect platform admin evidence and build the public result."""
    result = {
        "is_admin": False,
        "os_type": system_name,
        "details": {},
        "success": True,
    }
    os_type = system_name.lower()
    if os_type == "windows":
        _inspect_windows(
            result,
            run_command,
            windows_admin_provider,
        )
    elif os_type == "linux":
        _inspect_linux(result, run_command, uid_provider)
    elif os_type == "darwin":
        _inspect_darwin(result, run_command)
    else:
        result["details"]["status"] = "unsupported_os"
        result["details"]["description"] = (
            f"Admin check not implemented for OS: {os_type}"
        )

    username = username_provider()
    result["message"] = _admin_message(result, os_type, username)
    return result


def _inspect_windows(
    result,
    run_command,
    windows_admin_provider,
):
    try:
        is_admin = windows_admin_provider()
        result["is_admin"] = is_admin
        if is_admin:
            result["details"]["status"] = "full_admin"
            result["details"]["description"] = (
                "User has full administrative rights"
            )
            return
        _inspect_windows_group(result, run_command)
    except Exception as exc:
        result["details"]["error"] = str(exc)
        _windows_fallback(result, run_command)


def _inspect_windows_group(result, run_command):
    try:
        group_check = run_command(
            ["whoami", "/groups", "/fo", "csv", "/nh"],
            capture_output=True,
            encoding="ascii",
            errors="ignore",
            check=False,
        )
    except Exception:
        _set_unknown_windows_group(result)
        return

    if group_check.returncode != 0:
        _set_unknown_windows_group(result)
        return

    if WINDOWS_ADMINISTRATORS_SID in group_check.stdout:
        result["details"]["status"] = "admin_group_no_elevation"
        result["details"]["description"] = (
            "User is a member of administrators group but not running "
            "with elevated privileges"
        )
        result["details"]["tip"] = (
            "Try running as administrator to gain full privileges"
        )
        return

    result["details"]["status"] = "not_admin"
    result["details"]["description"] = (
        "User is not a member of administrators group"
    )


def _set_unknown_windows_group(result):
    result["details"]["status"] = "unknown_group_membership"
    result["details"]["description"] = (
        "Unable to determine administrators group membership"
    )


def _windows_fallback(result, run_command):
    try:
        process = run_command(
            ["net", "session"],
            capture_output=True,
            check=False,
        )
        result["is_admin"] = process.returncode == 0
        result["details"]["method"] = "fallback"
    except Exception:
        result["details"]["status"] = "check_failed"
        result["details"]["description"] = (
            "Unable to determine administrative status"
        )


def _inspect_linux(result, run_command, uid_provider):
    try:
        uid = uid_provider()
        result["is_admin"] = uid == 0
        result["details"]["uid"] = uid
        if uid == 0:
            result["details"]["status"] = "root"
            result["details"]["description"] = "User has full root permissions"
            return
        _inspect_linux_groups(result, run_command)
    except Exception as exc:
        result["details"]["error"] = str(exc)


def _inspect_linux_groups(result, run_command):
    try:
        sudo_test = run_command(
            ["sudo", "-n", "true"],
            capture_output=True,
            text=True,
            check=False,
        )
        result["details"]["has_passwordless_sudo"] = (
            sudo_test.returncode == 0
        )
        groups_output = run_command(
            ["groups"],
            capture_output=True,
            text=True,
            check=False,
        )
        groups = groups_output.stdout.strip().split()
        membership = [
            group
            for group in groups
            if group in {"sudo", "wheel", "admin"}
        ]
        if membership:
            result["details"]["admin_groups"] = membership
            result["details"]["status"] = "admin_group_member"
            result["details"]["description"] = (
                f"Member of admin groups: {', '.join(membership)}"
            )
            result["is_admin"] = True
        else:
            result["details"]["status"] = "not_admin"
            result["details"]["description"] = (
                "Not a member of any known admin groups"
            )
    except Exception:
        result["details"]["status"] = "check_failed"
        result["details"]["description"] = (
            "Unable to determine sudo capabilities"
        )


def _inspect_darwin(result, run_command):
    try:
        groups_output = run_command(
            ["groups"],
            capture_output=True,
            text=True,
            check=False,
        )
        groups = groups_output.stdout.strip().split()
        result["is_admin"] = "admin" in groups
        if result["is_admin"]:
            result["details"]["status"] = "admin_group_member"
            result["details"]["description"] = (
                "User is a member of admin group"
            )
        else:
            result["details"]["status"] = "not_admin"
            result["details"]["description"] = (
                "User is not a member of admin group"
            )
        _inspect_darwin_sudo(result, run_command)
    except Exception as exc:
        result["details"]["error"] = str(exc)


def _inspect_darwin_sudo(result, run_command):
    try:
        sudo_test = run_command(
            ["sudo", "-n", "true"],
            capture_output=True,
            text=True,
            check=False,
        )
        result["details"]["has_passwordless_sudo"] = (
            sudo_test.returncode == 0
        )
    except Exception:
        result["details"]["sudo_check"] = "failed"


def _admin_message(result, os_type, username):
    status_msg = (
        "has administrative privileges"
        if result["is_admin"]
        else "does not have administrative privileges"
    )
    action_tip = ""
    if result["is_admin"]:
        status_msg = _admin_status_message(result, os_type, status_msg)
    elif (
        os_type == "windows"
        and result["details"].get("status") == "admin_group_no_elevation"
    ):
        status_msg = (
            "is a member of the administrators group but is not running "
            "with elevated privileges"
        )
        action_tip = (
            " Run as administrator to gain full administrative access."
        )
    if not result["is_admin"] and not action_tip:
        action_tip = (
            " Administrative operations will require elevation or "
            "administrator credentials."
        )
    return (
        f"User '{username}' {status_msg} on "
        f"{result['os_type']}.{action_tip}"
    )


def _admin_status_message(result, os_type, default):
    details = result["details"]
    if os_type == "windows" and details.get("status") == "full_admin":
        return "has full administrative privileges (elevated)"
    if os_type == "linux" and details.get("status") == "root":
        return "is running as root (UID 0)"
    if os_type == "linux" and details.get("status") == "admin_group_member":
        groups = ", ".join(details.get("admin_groups", []))
        suffix = (
            " with passwordless sudo access"
            if details.get("has_passwordless_sudo")
            else " requiring password for sudo"
        )
        return (
            f"has administrative capabilities (member of {groups}){suffix}"
        )
    if os_type == "darwin":
        message = "has administrative rights (member of admin group)"
        if details.get("has_passwordless_sudo"):
            message += " with passwordless sudo access"
        return message
    return default
