#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Deploy an explicit artifact over SSH with verification and rollback."""

import re

from qzx.core.command_base import CommandBase

from ._deployment_artifact import (
    create_local_archive,
    hash_file,
    new_deployment_id,
    remote_paths,
    snapshot_artifact,
    unsafe_artifact_entry,
)
from ._deployment_command import execute_deployment
from ._deployment_remote import (
    bounded_error,
    check_health,
    cleanup_unpromoted,
    create_remote_backup,
    lock_cleanup_shell,
    owner_check,
    prepare_remote_stage,
    promote,
    release_lock,
    remote_preflight,
    rollback,
    run_ssh,
    ssh_command,
    upload_archive,
    verify_remote_stage,
)
from ._deployment_validation import (
    failure,
    validate_backup_target,
    validate_health_url,
    validate_inputs,
    validate_target_path,
)


class DeployProjectCommand(CommandBase):
    """Promote one reviewed artifact to a remote path over SSH."""

    name = "deployProject"
    description = (
        "Previews or deploys one explicit artifact over SSH using a verified "
        "remote backup, SHA-256 validation, atomic promotion, health checks, "
        "and automatic rollback"
    )
    category = "development"
    requires_explicit_approval = True
    backup_target_parameter = "path"
    parameters = [
        {"name": "target_host", "description": "SSH destination in host or user@host form", "required": True, "type": "str"},
        {"name": "path", "description": "Explicit local artifact directory to deploy; QZX never builds it or falls back to the project root", "required": False, "default": ".", "type": "str"},
        {"name": "target_path", "description": "Absolute remote directory that will become the active release", "required": True, "type": "str"},
        {"name": "port", "description": "SSH port", "required": False, "default": 22, "type": "int"},
        {"name": "ssh_key", "description": "Optional local SSH private-key file", "required": False, "default": None, "type": "str"},
        {"name": "known_hosts", "description": "Optional explicit OpenSSH known_hosts file used to verify the remote server identity", "required": False, "default": None, "type": "str"},
        {"name": "health_url", "description": "HTTP(S) endpoint without credentials, query, or fragment; required for a live deployment and checked after promotion", "required": False, "default": None, "type": "str"},
        {"name": "health_expect", "description": "Optional text that the health response body must contain", "required": False, "default": None, "type": "str"},
        {"name": "health_attempts", "description": "Health-check attempts from 1 to 20", "required": False, "default": 5, "type": "int"},
        {"name": "health_interval", "description": "Seconds between health attempts, from 0 to 30", "required": False, "default": 2.0, "type": "float"},
        {"name": "health_timeout", "description": "Timeout per health attempt, from 0.1 to 30 seconds", "required": False, "default": 5.0, "type": "float"},
        {"name": "deployment_id", "description": "Optional stable identifier for audit and recovery paths", "required": False, "default": None, "type": "str"},
        {"name": "dry_run", "description": "Preview the exact artifact and remote paths without connecting", "required": False, "default": True, "type": "bool"},
    ]
    examples = [
        {"command": "qzx deployProject --target-host deploy@example.test --path ./dist --target-path /srv/example/current", "description": "Inspects the artifact and previews every remote recovery path"},
        {"command": "qzx deployProject --target-host deploy@example.test --path ./dist --target-path /srv/example/current --health-url https://example.test/health --health-expect \"ready\" --dry-run false", "description": "Backs up the artifact, then performs a verified deployment"},
    ]
    _host_pattern = re.compile(r"[A-Za-z0-9_.@:\-\[\]]+\Z")
    _deployment_id_pattern = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
    _manifest_name = ".qzx-manifest-sha256"

    _validate_inputs = validate_inputs
    _validate_target_path = validate_target_path
    _validate_health_url = validate_health_url
    _snapshot_artifact = snapshot_artifact
    _unsafe_artifact_entry = unsafe_artifact_entry
    _hash_file = staticmethod(hash_file)
    _create_local_archive = create_local_archive
    _new_deployment_id = staticmethod(new_deployment_id)
    _remote_paths = staticmethod(remote_paths)
    _ssh_command = staticmethod(ssh_command)
    _run_ssh = run_ssh
    _remote_preflight = remote_preflight
    _create_remote_backup = create_remote_backup
    _prepare_remote_stage = prepare_remote_stage
    _upload_archive = upload_archive
    _verify_remote_stage = verify_remote_stage
    _promote = promote
    _check_health = check_health
    _rollback = rollback
    _cleanup_unpromoted = cleanup_unpromoted
    _release_lock = release_lock
    _owner_check = staticmethod(owner_check)
    _lock_cleanup_shell = staticmethod(lock_cleanup_shell)
    _bounded_error = staticmethod(bounded_error)
    _failure = staticmethod(failure)

    def validate_safety_backup_target(self, target, values):
        return validate_backup_target(self, target, values)

    def execute(self, target_host, target_path, path=".", port=22, ssh_key=None, known_hosts=None, health_url=None, health_expect=None, health_attempts=5, health_interval=2.0, health_timeout=5.0, deployment_id=None, dry_run=True):
        return execute_deployment(
            self, target_host=target_host, target_path=target_path, path=path,
            port=port, ssh_key=ssh_key, known_hosts=known_hosts,
            health_url=health_url, health_expect=health_expect,
            health_attempts=health_attempts, health_interval=health_interval,
            health_timeout=health_timeout, deployment_id=deployment_id,
            dry_run=dry_run,
        )
