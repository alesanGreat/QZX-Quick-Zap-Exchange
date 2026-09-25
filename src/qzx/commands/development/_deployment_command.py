"""Orchestration for an explicit SSH artifact deployment."""

import shutil
import tarfile
from pathlib import Path


def _snapshot(command, values):
    try:
        return command._snapshot_artifact(values["artifact_path"])
    except OSError as exc:
        return command._failure(
            "artifact_read_failed", f"The artifact could not be read completely: {type(exc).__name__}: {exc}",
            artifact_path=str(values["artifact_path"]),
        )


def _details(command, values, snapshot, remote_paths):
    size = command._format_bytes(float(snapshot["bytes"]))
    return {
        "status": "ready" if values["dry_run"] else "preflight",
        "dry_run": values["dry_run"], "transport": "ssh_tar",
        "target_host": values["target_host"], "port": values["port"],
        "artifact": {
            "path": str(values["artifact_path"]), "files": snapshot["files_count"],
            "directories": snapshot["directories_count"], "bytes": snapshot["bytes"],
            "human_size": size, "sha256": snapshot["artifact_sha256"],
            "symlinks_allowed": False,
        },
        "remote": remote_paths,
        "verification": {
            "archive_transport": "tar.gz over SSH stdin", "file_integrity": "SHA-256 manifest",
            "health_url": values["health_url"],
            "health_expect_configured": values["health_expect"] is not None,
            "health_attempts": values["health_attempts"],
            "health_interval_seconds": values["health_interval"],
            "health_timeout_seconds": values["health_timeout"],
        },
        "steps": [
            "read-only remote preflight", "verified remote backup of the current state",
            "exclusive deployment lock", "upload into a new staging directory",
            "SHA-256 verification of every file", "same-filesystem promotion",
            "HTTP(S) health verification", "automatic rollback if health verification fails",
        ],
        "remote_state_before": "not_checked", "remote_backup": "planned",
        "lock": "planned", "upload": "planned", "integrity_check": "planned",
        "promotion": "planned", "health_check": "planned", "rollback": "not_needed",
        "cleanup": "planned",
        "excluded_actions": ["local build", "remote permission changes", "arbitrary remote commands", "service restart or reload", "deletion of unrelated remote files"],
        "retention": "Remote backup, previous, and failed-release paths are never pruned automatically; manage the returned paths explicitly.",
    }


def _preview(command, snapshot, details):
    size = command._format_bytes(float(snapshot["bytes"]))
    return {"success": True, "message": f"Deployment plan is ready for {snapshot['files_count']} files ({size}). No network connection or mutation was performed.", "details": details}


def _remote_start(command, values, paths, details):
    if not values["health_url"]:
        details["status"] = "blocked_before_connection"
        return None, command._failure("health_url_required", "A live deployment requires health_url so QZX can verify the promoted release and roll it back automatically.", **details)
    executable = shutil.which("ssh")
    if not executable:
        return None, command._failure("ssh_unavailable", "The SSH client was not found. Install OpenSSH Client and retry; the remote target was not contacted.", **details)
    ssh_argv = command._ssh_command(executable, values["target_host"], values["port"], values["ssh_key"], values["known_hosts"])
    preflight = command._remote_preflight(ssh_argv, paths, timeout=max(10.0, values["health_timeout"]))
    if not preflight["success"]:
        details.update(status="failed_before_mutation", remote_state_before=preflight["state"])
        return None, command._failure(preflight["error_code"], preflight["message"], **details)
    details["remote_state_before"] = preflight["state"]
    return (ssh_argv, preflight["state"]), None


def _backup_and_stage(command, ssh_argv, paths, deployment_id, state, details):
    backup = command._create_remote_backup(ssh_argv, paths, state)
    if not backup["success"]:
        details.update(status="failed_before_target_mutation", remote_backup=backup["status"])
        message = "The remote state was not changed because its restorable backup could not be verified: " + backup["message"]
        return command._failure("remote_backup_failed", message, **details)
    details["remote_backup"] = backup["status"]
    prepared = command._prepare_remote_stage(ssh_argv, paths, deployment_id)
    if not prepared["success"]:
        details.update(status="failed_before_upload", lock=prepared["lock"], cleanup=prepared["cleanup"])
        return command._failure(prepared["error_code"], prepared["message"], **details)
    details["lock"] = "acquired"
    return None


def _upload(command, ssh_argv, paths, values, snapshot, details):
    archive_path = None
    try:
        archive_path = command._create_local_archive(values["artifact_path"], snapshot)
        upload = command._upload_archive(ssh_argv, paths, values["deployment_id"], archive_path)
    except (OSError, tarfile.TarError) as exc:
        upload = {"success": False, "message": f"{type(exc).__name__}: {exc}"}
    finally:
        if archive_path is not None:
            try:
                Path(archive_path).unlink()
            except OSError:
                pass
    if upload["success"]:
        details["upload"] = "completed"
        return None
    details.update(status="failed_during_upload", upload=f"failed: {upload['message']}")
    details["cleanup"] = command._cleanup_unpromoted(ssh_argv, paths, values["deployment_id"])
    return command._failure("artifact_upload_failed", "The artifact could not be uploaded. The active remote release was not changed.", **details)


def _integrity(command, ssh_argv, paths, values, snapshot, details):
    result = command._verify_remote_stage(ssh_argv, paths, values["deployment_id"], snapshot["files_count"])
    if result["success"]:
        details["integrity_check"] = "passed"
        return None
    details.update(status="failed_integrity_check", integrity_check=f"failed: {result['message']}")
    details["cleanup"] = command._cleanup_unpromoted(ssh_argv, paths, values["deployment_id"])
    return command._failure("artifact_integrity_failed", "The uploaded artifact did not match its local SHA-256 manifest. The active release was not changed.", **details)


def _promote_and_verify(command, ssh_argv, paths, values, state, details):
    promotion = command._promote(ssh_argv, paths, values["deployment_id"], state)
    if not promotion["success"]:
        details.update(status="promotion_failed", promotion=f"failed: {promotion['message']}", cleanup="lock retained for manual inspection")
        return command._failure("promotion_failed", "Atomic promotion failed. QZX attempted an immediate in-command restoration; inspect the returned recovery paths before retrying.", **details)
    details["promotion"] = "completed"
    health = command._check_health(values["health_url"], values["health_expect"], values["health_attempts"], values["health_interval"], values["health_timeout"])
    details["health_check"] = health
    if health["passed"]:
        return None
    rollback = command._rollback(ssh_argv, paths, values["deployment_id"], state)
    details.update(rollback=rollback["status"], cleanup=rollback["cleanup"], status="rolled_back" if rollback["success"] else "recovery_required")
    ending = "The previous remote state was restored." if rollback["success"] else "Automatic restoration failed; manual recovery is required."
    return command._failure("health_check_failed", "The new release failed health verification. " + ending, **details)


def _finish(command, ssh_argv, paths, values, snapshot, details):
    cleanup = command._release_lock(ssh_argv, paths, values["deployment_id"])
    details.update(cleanup=cleanup, status="deployed")
    warning = "" if cleanup == "completed" else " The deployment lock needs manual cleanup."
    size = command._format_bytes(float(snapshot["bytes"]))
    return {"success": cleanup == "completed", "message": f"Deployed and verified {snapshot['files_count']} files ({size}) at '{values['target_path']}'.{warning}", "details": details}


def execute_deployment(command, **raw):
    validation = command._validate_inputs(**raw)
    if not validation["success"]:
        return validation
    values = validation["values"]
    snapshot = _snapshot(command, values)
    if not snapshot["success"]:
        return snapshot
    paths = command._remote_paths(values["target_path"], values["deployment_id"])
    details = _details(command, values, snapshot, paths)
    if values["dry_run"]:
        return _preview(command, snapshot, details)
    remote, failure = _remote_start(command, values, paths, details)
    if failure:
        return failure
    ssh_argv, state = remote
    failure = _backup_and_stage(command, ssh_argv, paths, values["deployment_id"], state, details)
    if failure:
        return failure
    failure = _upload(command, ssh_argv, paths, values, snapshot, details)
    if failure:
        return failure
    failure = _integrity(command, ssh_argv, paths, values, snapshot, details)
    if failure:
        return failure
    failure = _promote_and_verify(command, ssh_argv, paths, values, state, details)
    if failure:
        return failure
    return _finish(command, ssh_argv, paths, values, snapshot, details)
