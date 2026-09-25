"""Constrained SSH deployment operations for ``deployProject``."""

import shlex
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath


def ssh_command(executable, target_host, port, ssh_key, known_hosts):
    command = [executable, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=yes", "-p", str(port)]
    if ssh_key is not None:
        command.extend(["-o", "IdentitiesOnly=yes", "-i", str(ssh_key)])
    if known_hosts is not None:
        command.extend(["-o", f"UserKnownHostsFile={known_hosts}"])
    return [*command, target_host]


def run_ssh(_command, ssh_argv, remote_command, timeout=30, stdin=None):
    try:
        result = subprocess.run(
            [*ssh_argv, remote_command], stdin=subprocess.DEVNULL if stdin is None else stdin,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False,
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"success": False, "returncode": None, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}
    return {
        "success": result.returncode == 0, "returncode": result.returncode,
        "stdout": result.stdout.decode("utf-8", errors="replace").strip(),
        "stderr": result.stderr.decode("utf-8", errors="replace").strip(),
    }


def remote_preflight(command, ssh_argv, paths, timeout):
    active = shlex.quote(paths["active"])
    parent = shlex.quote(str(PurePosixPath(paths["active"]).parent))
    shell = (
        "set -eu; command -v tar >/dev/null; command -v sha256sum >/dev/null; "
        f"test -d {parent}; test -w {parent}; if test -L {active}; then printf symlink; "
        f"elif test -d {active}; then printf directory; elif test -e {active}; "
        "then printf non_directory; else printf absent; fi"
    )
    result = command._run_ssh(ssh_argv, shell, timeout=timeout)
    state = result["stdout"]
    if not result["success"]:
        return {"success": False, "state": "unknown", "error_code": "remote_preflight_failed", "message": "Remote preflight failed without changing the target: " + command._bounded_error(result)}
    if state in {"symlink", "non_directory"}:
        return {"success": False, "state": state, "error_code": "unsafe_remote_target", "message": f"Remote target is a {state.replace('_', ' ')}. QZX only promotes to an absent path or a real directory."}
    if state not in {"directory", "absent"}:
        return {"success": False, "state": "unknown", "error_code": "unexpected_remote_state", "message": "Remote preflight returned an unrecognized state and QZX refused to continue."}
    return {"success": True, "state": state}


def create_remote_backup(command, ssh_argv, paths, state):
    active = shlex.quote(paths["active"])
    if state == "directory":
        archive = shlex.quote(paths["backup_archive"])
        parent = shlex.quote(str(PurePosixPath(paths["active"]).parent))
        name = shlex.quote(PurePosixPath(paths["active"]).name)
        shell = f"set -eu; umask 077; test ! -e {archive}; tar -czf {archive} -C {parent} -- {name}; tar -tzf {archive} >/dev/null"
        success_status = "verified archive created"
    else:
        marker = shlex.quote(paths["absence_marker"])
        shell = f"set -eu; umask 077; test ! -e {marker}; printf '%s\n' 'target was absent' > {marker}; test -s {marker}"
        success_status = "verified absence marker created"
    result = command._run_ssh(ssh_argv, shell, timeout=120)
    return {"success": result["success"], "status": success_status if result["success"] else f"failed: {command._bounded_error(result)}", "message": command._bounded_error(result)}


def prepare_remote_stage(command, ssh_argv, paths, deployment_id):
    lock, owner = shlex.quote(paths["lock"]), shlex.quote(f"{paths['lock']}/owner")
    stage, identifier = shlex.quote(paths["stage"]), shlex.quote(deployment_id)
    shell = (
        f"set -eu; test ! -e {stage}; if ! mkdir -- {lock}; then printf '%s' "
        f"'another deployment owns the lock' >&2; exit 73; fi; if printf '%s' {identifier} > {owner} "
        f"&& mkdir -- {stage}; then :; else rm -f -- {owner}; rmdir -- {lock} 2>/dev/null || true; exit 74; fi"
    )
    result = command._run_ssh(ssh_argv, shell)
    if result["success"]:
        return {"success": True, "lock": "acquired", "cleanup": "pending"}
    locked = result["returncode"] == 73
    return {
        "success": False, "error_code": "deployment_locked" if locked else "remote_stage_failed",
        "message": "Another deployment already owns the remote lock." if locked else "The remote staging directory could not be prepared: " + command._bounded_error(result),
        "lock": "already held" if locked else "not acquired",
        "cleanup": "not needed" if locked else "attempted by remote preflight",
    }


def upload_archive(command, ssh_argv, paths, deployment_id, archive_path):
    owner_check = command._owner_check(paths, deployment_id)
    shell = f"set -eu; {owner_check}; tar -xzf - -C {shlex.quote(paths['stage'])}"
    with Path(archive_path).open("rb") as archive:
        result = command._run_ssh(ssh_argv, shell, timeout=300, stdin=archive)
    return {"success": result["success"], "message": command._bounded_error(result)}


def verify_remote_stage(command, ssh_argv, paths, deployment_id, files_count):
    owner_check = command._owner_check(paths, deployment_id)
    stage, manifest = shlex.quote(paths["stage"]), shlex.quote(command._manifest_name)
    shell = (
        f"set -eu; {owner_check}; cd -- {stage}; test -z \"$(find . -type l -print -quit)\"; "
        "test -z \"$(find . -mindepth 1 ! -type f ! -type d -print -quit)\"; "
        f"test \"$(find . -type f | wc -l)\" -eq {files_count + 1}; "
        f"sha256sum -c -- {manifest} >/dev/null; rm -- {manifest}"
    )
    result = command._run_ssh(ssh_argv, shell, timeout=120)
    return {"success": result["success"], "message": command._bounded_error(result)}


def promote(command, ssh_argv, paths, deployment_id, remote_state):
    owner_check = command._owner_check(paths, deployment_id)
    active, stage, previous = (shlex.quote(paths[name]) for name in ("active", "stage", "previous"))
    if remote_state == "directory":
        shell = f"set -eu; {owner_check}; test -d {active}; test ! -e {previous}; mv -- {active} {previous}; if mv -- {stage} {active}; then :; else mv -- {previous} {active}; exit 75; fi"
    else:
        shell = f"set -eu; {owner_check}; test ! -e {active}; mv -- {stage} {active}"
    result = command._run_ssh(ssh_argv, shell)
    return {"success": result["success"], "message": command._bounded_error(result)}


def _health_attempt(url, expected_text, timeout):
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "QZX-Deploy-Health-Check/1", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            body = response.read(1024 * 1024).decode("utf-8", errors="replace")
        if not 200 <= status < 400:
            return False, status, f"HTTP {status}"
        if expected_text is not None and expected_text not in body:
            return False, status, "expected response text was absent"
        return True, status, None
    except (OSError, urllib.error.URLError, ValueError) as exc:
        return False, None, f"{type(exc).__name__}: {exc}"


def check_health(_command, url, expected_text, attempts, interval, timeout):
    failures = []
    for attempt in range(1, attempts + 1):
        passed, status, error = _health_attempt(url, expected_text, timeout)
        if passed:
            return {"passed": True, "attempt": attempt, "status_code": status, "expected_text_checked": expected_text is not None}
        failures.append(f"attempt {attempt}: {error}")
        if attempt < attempts and interval:
            time.sleep(interval)
    return {"passed": False, "attempts": attempts, "expected_text_checked": expected_text is not None, "last_failure": failures[-1] if failures else "unknown failure"}


def rollback(command, ssh_argv, paths, deployment_id, remote_state):
    owner_check = command._owner_check(paths, deployment_id)
    active, failed, previous = (shlex.quote(paths[name]) for name in ("active", "failed", "previous"))
    cleanup = command._lock_cleanup_shell(paths)
    if remote_state == "directory":
        shell = f"set -eu; {owner_check}; test -d {active}; test -d {previous}; test ! -e {failed}; mv -- {active} {failed}; if mv -- {previous} {active}; then {cleanup}; else mv -- {failed} {active} 2>/dev/null || true; exit 76; fi"
    else:
        shell = f"set -eu; {owner_check}; test -d {active}; test ! -e {failed}; mv -- {active} {failed}; {cleanup}"
    result = command._run_ssh(ssh_argv, shell)
    return {
        "success": result["success"],
        "status": "previous remote state restored" if result["success"] else f"failed: {command._bounded_error(result)}",
        "cleanup": "lock released; failed release retained for inspection" if result["success"] else "lock retained for manual recovery",
    }


def cleanup_unpromoted(command, ssh_argv, paths, deployment_id):
    shell = f"set -eu; {command._owner_check(paths, deployment_id)}; rm -rf -- {shlex.quote(paths['stage'])}; {command._lock_cleanup_shell(paths)}"
    result = command._run_ssh(ssh_argv, shell)
    return "staging removed and lock released" if result["success"] else "failed; staging and lock may require manual cleanup"


def release_lock(command, ssh_argv, paths, deployment_id):
    shell = f"set -eu; {command._owner_check(paths, deployment_id)}; {command._lock_cleanup_shell(paths)}"
    return "completed" if command._run_ssh(ssh_argv, shell)["success"] else "failed"


def owner_check(paths, deployment_id):
    owner, identifier = shlex.quote(f"{paths['lock']}/owner"), shlex.quote(deployment_id)
    return f"test \"$(cat -- {owner})\" = {identifier}"


def lock_cleanup_shell(paths):
    owner, lock = shlex.quote(f"{paths['lock']}/owner"), shlex.quote(paths["lock"])
    return f"rm -- {owner}; rmdir -- {lock}"


def bounded_error(result):
    message = result.get("stderr") or result.get("stdout") or f"exit code {result.get('returncode')}"
    return str(message).strip()[:1_000]
