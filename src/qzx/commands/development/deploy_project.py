#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Deploy an explicit artifact over SSH with verification and rollback."""

from __future__ import annotations

import hashlib
import io
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from qzx.core.command_base import CommandBase


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
        {
            "name": "target_host",
            "description": "SSH destination in host or user@host form",
            "required": True,
            "type": "str",
        },
        {
            "name": "path",
            "description": (
                "Explicit local artifact directory to deploy; QZX never "
                "builds it or falls back to the project root"
            ),
            "required": False,
            "default": ".",
            "type": "str",
        },
        {
            "name": "target_path",
            "description": (
                "Absolute remote directory that will become the active release"
            ),
            "required": True,
            "type": "str",
        },
        {
            "name": "port",
            "description": "SSH port",
            "required": False,
            "default": 22,
            "type": "int",
        },
        {
            "name": "ssh_key",
            "description": "Optional local SSH private-key file",
            "required": False,
            "default": None,
            "type": "str",
        },
        {
            "name": "known_hosts",
            "description": (
                "Optional explicit OpenSSH known_hosts file used to verify "
                "the remote server identity"
            ),
            "required": False,
            "default": None,
            "type": "str",
        },
        {
            "name": "health_url",
            "description": (
                "HTTP(S) endpoint without credentials, query, or fragment; "
                "required for a live deployment and checked after promotion"
            ),
            "required": False,
            "default": None,
            "type": "str",
        },
        {
            "name": "health_expect",
            "description": (
                "Optional text that the health response body must contain"
            ),
            "required": False,
            "default": None,
            "type": "str",
        },
        {
            "name": "health_attempts",
            "description": "Health-check attempts from 1 to 20",
            "required": False,
            "default": 5,
            "type": "int",
        },
        {
            "name": "health_interval",
            "description": "Seconds between health attempts, from 0 to 30",
            "required": False,
            "default": 2.0,
            "type": "float",
        },
        {
            "name": "health_timeout",
            "description": "Timeout per health attempt, from 0.1 to 30 seconds",
            "required": False,
            "default": 5.0,
            "type": "float",
        },
        {
            "name": "deployment_id",
            "description": (
                "Optional stable identifier for audit and recovery paths"
            ),
            "required": False,
            "default": None,
            "type": "str",
        },
        {
            "name": "dry_run",
            "description": (
                "Preview the exact artifact and remote paths without connecting"
            ),
            "required": False,
            "default": True,
            "type": "bool",
        },
    ]

    examples = [
        {
            "command": (
                "qzx deployProject --target-host deploy@example.test "
                "--path ./dist --target-path /srv/example/current"
            ),
            "description": (
                "Inspects the artifact and previews every remote recovery path"
            ),
        },
        {
            "command": (
                "qzx deployProject --target-host deploy@example.test "
                "--path ./dist --target-path /srv/example/current "
                "--health-url https://example.test/health "
                '--health-expect "ready" --dry-run false'
            ),
            "description": (
                "Backs up the artifact, then performs a verified deployment"
            ),
        },
    ]

    _host_pattern = re.compile(r"[A-Za-z0-9_.@:\-\[\]]+\Z")
    _deployment_id_pattern = re.compile(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z"
    )
    _manifest_name = ".qzx-manifest-sha256"

    def validate_safety_backup_target(self, target, values):
        """Validate the complete live request before creating a local backup."""
        validation = self._validate_inputs(
            target_host=values.get("target_host"),
            target_path=values.get("target_path"),
            path=target,
            port=values.get("port", 22),
            ssh_key=values.get("ssh_key"),
            known_hosts=values.get("known_hosts"),
            health_url=values.get("health_url"),
            health_expect=values.get("health_expect"),
            health_attempts=values.get("health_attempts", 5),
            health_interval=values.get("health_interval", 2.0),
            health_timeout=values.get("health_timeout", 5.0),
            deployment_id=values.get("deployment_id"),
            dry_run=False,
        )
        if not validation["success"]:
            return validation
        if not validation["values"]["health_url"]:
            return self._failure(
                "health_url_required",
                (
                    "A live deployment requires health_url so QZX can verify "
                    "the promoted release and roll it back automatically."
                ),
            )
        return None

    def execute(
        self,
        target_host,
        target_path,
        path=".",
        port=22,
        ssh_key=None,
        known_hosts=None,
        health_url=None,
        health_expect=None,
        health_attempts=5,
        health_interval=2.0,
        health_timeout=5.0,
        deployment_id=None,
        dry_run=True,
    ):
        """Build a deployment plan and optionally execute it."""
        validation = self._validate_inputs(
            target_host=target_host,
            target_path=target_path,
            path=path,
            port=port,
            ssh_key=ssh_key,
            known_hosts=known_hosts,
            health_url=health_url,
            health_expect=health_expect,
            health_attempts=health_attempts,
            health_interval=health_interval,
            health_timeout=health_timeout,
            deployment_id=deployment_id,
            dry_run=dry_run,
        )
        if not validation["success"]:
            return validation

        values = validation["values"]
        try:
            snapshot = self._snapshot_artifact(values["artifact_path"])
        except OSError as exc:
            return self._failure(
                "artifact_read_failed",
                (
                    "The artifact could not be read completely: "
                    f"{type(exc).__name__}: {exc}"
                ),
                artifact_path=str(values["artifact_path"]),
            )
        if not snapshot["success"]:
            return snapshot

        remote_paths = self._remote_paths(
            values["target_path"],
            values["deployment_id"],
        )
        details = {
            "status": "ready" if values["dry_run"] else "preflight",
            "dry_run": values["dry_run"],
            "transport": "ssh_tar",
            "target_host": values["target_host"],
            "port": values["port"],
            "artifact": {
                "path": str(values["artifact_path"]),
                "files": snapshot["files_count"],
                "directories": snapshot["directories_count"],
                "bytes": snapshot["bytes"],
                "human_size": self._format_bytes(float(snapshot["bytes"])),
                "sha256": snapshot["artifact_sha256"],
                "symlinks_allowed": False,
            },
            "remote": remote_paths,
            "verification": {
                "archive_transport": "tar.gz over SSH stdin",
                "file_integrity": "SHA-256 manifest",
                "health_url": values["health_url"],
                "health_expect_configured": (
                    values["health_expect"] is not None
                ),
                "health_attempts": values["health_attempts"],
                "health_interval_seconds": values["health_interval"],
                "health_timeout_seconds": values["health_timeout"],
            },
            "steps": [
                "read-only remote preflight",
                "verified remote backup of the current state",
                "exclusive deployment lock",
                "upload into a new staging directory",
                "SHA-256 verification of every file",
                "same-filesystem promotion",
                "HTTP(S) health verification",
                "automatic rollback if health verification fails",
            ],
            "remote_state_before": "not_checked",
            "remote_backup": "planned",
            "lock": "planned",
            "upload": "planned",
            "integrity_check": "planned",
            "promotion": "planned",
            "health_check": "planned",
            "rollback": "not_needed",
            "cleanup": "planned",
            "excluded_actions": [
                "local build",
                "remote permission changes",
                "arbitrary remote commands",
                "service restart or reload",
                "deletion of unrelated remote files",
            ],
            "retention": (
                "Remote backup, previous, and failed-release paths are never "
                "pruned automatically; manage the returned paths explicitly."
            ),
        }
        if values["dry_run"]:
            return {
                "success": True,
                "message": (
                    f"Deployment plan is ready for {snapshot['files_count']} "
                    f"files ({self._format_bytes(float(snapshot['bytes']))}). "
                    "No network connection or mutation was performed."
                ),
                "details": details,
            }

        if not values["health_url"]:
            details["status"] = "blocked_before_connection"
            return self._failure(
                "health_url_required",
                (
                    "A live deployment requires health_url so QZX can verify "
                    "the promoted release and roll it back automatically."
                ),
                **details,
            )

        ssh_executable = shutil.which("ssh")
        if not ssh_executable:
            return self._failure(
                "ssh_unavailable",
                (
                    "The SSH client was not found. Install OpenSSH Client and "
                    "retry; the remote target was not contacted."
                ),
                **details,
            )

        ssh_command = self._ssh_command(
            ssh_executable,
            values["target_host"],
            values["port"],
            values["ssh_key"],
            values["known_hosts"],
        )
        preflight = self._remote_preflight(
            ssh_command,
            remote_paths,
            timeout=max(10.0, values["health_timeout"]),
        )
        if not preflight["success"]:
            details["status"] = "failed_before_mutation"
            details["remote_state_before"] = preflight["state"]
            return self._failure(
                preflight["error_code"],
                preflight["message"],
                **details,
            )
        remote_state = preflight["state"]
        details["remote_state_before"] = remote_state

        backup = self._create_remote_backup(
            ssh_command,
            remote_paths,
            remote_state,
        )
        if not backup["success"]:
            details["status"] = "failed_before_target_mutation"
            details["remote_backup"] = backup["status"]
            return self._failure(
                "remote_backup_failed",
                (
                    "The remote state was not changed because its restorable "
                    f"backup could not be verified: {backup['message']}"
                ),
                **details,
            )
        details["remote_backup"] = backup["status"]

        prepared = self._prepare_remote_stage(
            ssh_command,
            remote_paths,
            values["deployment_id"],
        )
        if not prepared["success"]:
            details["status"] = "failed_before_upload"
            details["lock"] = prepared["lock"]
            details["cleanup"] = prepared["cleanup"]
            return self._failure(
                prepared["error_code"],
                prepared["message"],
                **details,
            )
        details["lock"] = "acquired"

        archive_path = None
        try:
            archive_path = self._create_local_archive(
                values["artifact_path"],
                snapshot,
            )
            upload = self._upload_archive(
                ssh_command,
                remote_paths,
                values["deployment_id"],
                archive_path,
            )
        except (OSError, tarfile.TarError) as exc:
            upload = {
                "success": False,
                "message": f"{type(exc).__name__}: {exc}",
            }
        finally:
            if archive_path is not None:
                try:
                    Path(archive_path).unlink()
                except OSError:
                    pass

        if not upload["success"]:
            details["status"] = "failed_during_upload"
            details["upload"] = f"failed: {upload['message']}"
            details["cleanup"] = self._cleanup_unpromoted(
                ssh_command,
                remote_paths,
                values["deployment_id"],
            )
            return self._failure(
                "artifact_upload_failed",
                (
                    "The artifact could not be uploaded. The active remote "
                    "release was not changed."
                ),
                **details,
            )
        details["upload"] = "completed"

        integrity = self._verify_remote_stage(
            ssh_command,
            remote_paths,
            values["deployment_id"],
            snapshot["files_count"],
        )
        if not integrity["success"]:
            details["status"] = "failed_integrity_check"
            details["integrity_check"] = f"failed: {integrity['message']}"
            details["cleanup"] = self._cleanup_unpromoted(
                ssh_command,
                remote_paths,
                values["deployment_id"],
            )
            return self._failure(
                "artifact_integrity_failed",
                (
                    "The uploaded artifact did not match its local SHA-256 "
                    "manifest. The active release was not changed."
                ),
                **details,
            )
        details["integrity_check"] = "passed"

        promotion = self._promote(
            ssh_command,
            remote_paths,
            values["deployment_id"],
            remote_state,
        )
        if not promotion["success"]:
            details["status"] = "promotion_failed"
            details["promotion"] = f"failed: {promotion['message']}"
            details["cleanup"] = "lock retained for manual inspection"
            return self._failure(
                "promotion_failed",
                (
                    "Atomic promotion failed. QZX attempted an immediate "
                    "in-command restoration; inspect the returned recovery "
                    "paths before retrying."
                ),
                **details,
            )
        details["promotion"] = "completed"

        health = self._check_health(
            values["health_url"],
            values["health_expect"],
            values["health_attempts"],
            values["health_interval"],
            values["health_timeout"],
        )
        details["health_check"] = health
        if not health["passed"]:
            rollback = self._rollback(
                ssh_command,
                remote_paths,
                values["deployment_id"],
                remote_state,
            )
            details["rollback"] = rollback["status"]
            details["cleanup"] = rollback["cleanup"]
            details["status"] = (
                "rolled_back" if rollback["success"] else "recovery_required"
            )
            return self._failure(
                "health_check_failed",
                (
                    "The new release failed health verification. "
                    + (
                        "The previous remote state was restored."
                        if rollback["success"]
                        else "Automatic restoration failed; manual recovery is required."
                    )
                ),
                **details,
            )

        cleanup = self._release_lock(
            ssh_command,
            remote_paths,
            values["deployment_id"],
        )
        details["cleanup"] = cleanup
        details["status"] = "deployed"
        warning = ""
        if cleanup != "completed":
            warning = " The deployment lock needs manual cleanup."
        return {
            "success": cleanup == "completed",
            "message": (
                f"Deployed and verified {snapshot['files_count']} files "
                f"({self._format_bytes(float(snapshot['bytes']))}) at "
                f"'{values['target_path']}'.{warning}"
            ),
            "details": details,
        }

    def _validate_inputs(self, **raw):
        artifact_path = Path(os.path.abspath(os.fspath(raw["path"])))
        if not artifact_path.exists():
            return self._failure(
                "artifact_not_found",
                f"Artifact path '{artifact_path}' does not exist.",
                artifact_path=str(artifact_path),
            )
        if artifact_path.is_symlink() or not artifact_path.is_dir():
            return self._failure(
                "artifact_not_directory",
                (
                    f"Artifact path '{artifact_path}' must be a real directory, "
                    "not a file or symbolic link."
                ),
                artifact_path=str(artifact_path),
            )

        dry_run = self._parse_bool(raw["dry_run"])
        if dry_run is None:
            return self._failure(
                "invalid_boolean",
                f"dry_run must be true or false; got {raw['dry_run']!r}.",
            )

        host = str(raw["target_host"]).strip()
        if (
            not host
            or host.startswith("-")
            or not self._host_pattern.fullmatch(host)
        ):
            return self._failure(
                "invalid_target_host",
                (
                    "target_host must use a plain host or user@host value "
                    "without whitespace, options, or shell syntax."
                ),
                target_host=host,
            )

        try:
            port = int(raw["port"])
        except (TypeError, ValueError):
            port = -1
        if not 1 <= port <= 65535:
            return self._failure(
                "invalid_port",
                f"port must be between 1 and 65535; got {raw['port']!r}.",
            )

        target_result = self._validate_target_path(raw["target_path"])
        if not target_result["success"]:
            return target_result

        deployment_id = (
            str(raw["deployment_id"]).strip()
            if raw["deployment_id"] is not None
            else self._new_deployment_id()
        )
        if not self._deployment_id_pattern.fullmatch(deployment_id):
            return self._failure(
                "invalid_deployment_id",
                (
                    "deployment_id must be 1-64 ASCII letters, digits, dots, "
                    "underscores, or hyphens and must start with a letter or digit."
                ),
                deployment_id=deployment_id,
            )

        ssh_key = None
        if raw["ssh_key"] not in {None, ""}:
            ssh_key = Path(os.path.abspath(os.fspath(raw["ssh_key"])))
            if not ssh_key.is_file():
                return self._failure(
                    "ssh_key_not_found",
                    f"SSH key '{ssh_key}' is not a regular file.",
                    ssh_key=str(ssh_key),
                )

        known_hosts = None
        if raw["known_hosts"] not in {None, ""}:
            known_hosts = Path(
                os.path.abspath(os.fspath(raw["known_hosts"]))
            )
            if not known_hosts.is_file():
                return self._failure(
                    "known_hosts_not_found",
                    (
                        f"OpenSSH known_hosts file '{known_hosts}' is not a "
                        "regular file."
                    ),
                    known_hosts=str(known_hosts),
                )

        health_result = self._validate_health_url(raw["health_url"])
        if not health_result["success"]:
            return health_result
        health_expect = (
            str(raw["health_expect"])
            if raw["health_expect"] is not None
            else None
        )
        if health_expect is not None and len(health_expect) > 2_000:
            return self._failure(
                "health_expect_too_large",
                "health_expect must not exceed 2,000 characters.",
                characters=len(health_expect),
            )

        ranges = {
            "health_attempts": (raw["health_attempts"], int, 1, 20),
            "health_interval": (raw["health_interval"], float, 0.0, 30.0),
            "health_timeout": (raw["health_timeout"], float, 0.1, 30.0),
        }
        converted = {}
        for name, (value, converter, minimum, maximum) in ranges.items():
            try:
                converted_value = converter(value)
            except (TypeError, ValueError):
                converted_value = minimum - 1
            if not minimum <= converted_value <= maximum:
                return self._failure(
                    f"invalid_{name}",
                    (
                        f"{name} must be between {minimum} and {maximum}; "
                        f"got {value!r}."
                    ),
                )
            converted[name] = converted_value

        return {
            "success": True,
            "values": {
                "target_host": host,
                "target_path": target_result["path"],
                "artifact_path": artifact_path,
                "port": port,
                "ssh_key": ssh_key,
                "known_hosts": known_hosts,
                "health_url": health_result["url"],
                "health_expect": health_expect,
                "health_attempts": converted["health_attempts"],
                "health_interval": converted["health_interval"],
                "health_timeout": converted["health_timeout"],
                "deployment_id": deployment_id,
                "dry_run": dry_run,
            },
        }

    def _validate_target_path(self, value):
        raw_path = str(value).strip()
        if any(character in raw_path for character in "\r\n\0"):
            return self._failure(
                "invalid_target_path",
                "target_path must not contain control characters.",
            )
        target = PurePosixPath(raw_path)
        normalized = str(target)
        if (
            not raw_path.startswith("/")
            or normalized in {"/", "."}
            or normalized != raw_path.rstrip("/")
            or ".." in target.parts
        ):
            return self._failure(
                "unsafe_target_path",
                (
                    "target_path must be a normalized absolute POSIX path "
                    "below '/', such as /srv/example/current."
                ),
                target_path=raw_path,
            )
        if target.name.startswith(".qzx-"):
            return self._failure(
                "reserved_target_path",
                "target_path basename must not use QZX's .qzx- prefix.",
                target_path=raw_path,
            )
        return {"success": True, "path": normalized}

    def _validate_health_url(self, value):
        if value in {None, ""}:
            return {"success": True, "url": None}
        url = str(value).strip()
        parsed = urllib.parse.urlsplit(url)
        try:
            parsed_port = parsed.port
        except ValueError:
            parsed_port = -1
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed_port == -1
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            return self._failure(
                "invalid_health_url",
                (
                    "health_url must be an HTTP(S) URL without embedded "
                    "credentials, a query string, or a fragment."
                ),
            )
        return {"success": True, "url": url}

    def _snapshot_artifact(self, artifact):
        files = []
        directories = []
        total_bytes = 0
        aggregate = hashlib.sha256()
        for root, directory_names, file_names in os.walk(
            artifact,
            topdown=True,
            followlinks=False,
        ):
            directory_names.sort()
            file_names.sort()
            root_path = Path(root)
            for directory_name in list(directory_names):
                directory_path = root_path / directory_name
                relative = directory_path.relative_to(artifact).as_posix()
                if (
                    "\\" in relative
                    or "\n" in relative
                    or "\r" in relative
                    or relative == self._manifest_name
                ):
                    return self._unsafe_artifact_entry(
                        artifact,
                        directory_path,
                        "unsupported or reserved directory name",
                    )
                if directory_path.is_symlink():
                    return self._unsafe_artifact_entry(
                        artifact,
                        directory_path,
                        "symbolic link",
                    )
                mode = directory_path.stat(follow_symlinks=False).st_mode
                if not stat.S_ISDIR(mode):
                    return self._unsafe_artifact_entry(
                        artifact,
                        directory_path,
                        "non-directory entry",
                    )
                directories.append(directory_path)
            for file_name in file_names:
                file_path = root_path / file_name
                relative = file_path.relative_to(artifact).as_posix()
                if (
                    "\\" in relative
                    or "\n" in relative
                    or "\r" in relative
                    or relative == self._manifest_name
                ):
                    return self._unsafe_artifact_entry(
                        artifact,
                        file_path,
                        "unsupported or reserved file name",
                    )
                if file_path.is_symlink():
                    return self._unsafe_artifact_entry(
                        artifact,
                        file_path,
                        "symbolic link",
                    )
                mode = file_path.stat(follow_symlinks=False).st_mode
                if not stat.S_ISREG(mode):
                    return self._unsafe_artifact_entry(
                        artifact,
                        file_path,
                        "non-regular file",
                    )
                digest = self._hash_file(file_path)
                size = file_path.stat(follow_symlinks=False).st_size
                files.append(
                    {
                        "path": file_path,
                        "relative": relative,
                        "sha256": digest,
                        "bytes": size,
                    }
                )
                total_bytes += size
                aggregate.update(relative.encode("utf-8"))
                aggregate.update(b"\0")
                aggregate.update(str(size).encode("ascii"))
                aggregate.update(b"\0")
                aggregate.update(bytes.fromhex(digest))

        if not files:
            return self._failure(
                "empty_artifact",
                (
                    f"Artifact '{artifact}' contains no regular files. QZX "
                    "will not replace a remote release with an empty artifact."
                ),
                artifact_path=str(artifact),
            )
        return {
            "success": True,
            "files": files,
            "directories": sorted(
                directories,
                key=lambda item: item.relative_to(artifact).as_posix(),
            ),
            "files_count": len(files),
            "directories_count": len(directories),
            "bytes": total_bytes,
            "artifact_sha256": aggregate.hexdigest(),
        }

    def _unsafe_artifact_entry(self, artifact, entry, kind):
        return self._failure(
            "unsafe_artifact_entry",
            (
                f"Artifact entry '{entry.relative_to(artifact)}' is a {kind}. "
                "Deployments accept only real directories and regular files."
            ),
            artifact_path=str(artifact),
            entry=str(entry.relative_to(artifact)),
            entry_kind=kind,
        )

    @staticmethod
    def _hash_file(path):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _create_local_archive(self, artifact, snapshot):
        temporary = tempfile.NamedTemporaryFile(
            prefix="qzx-deploy-",
            suffix=".tar.gz",
            delete=False,
        )
        archive_path = Path(temporary.name)
        temporary.close()
        try:
            with tarfile.open(archive_path, "w:gz") as archive:
                for directory in snapshot["directories"]:
                    info = archive.gettarinfo(
                        str(directory),
                        arcname=directory.relative_to(artifact).as_posix(),
                    )
                    if not info.isdir():
                        raise OSError(
                            f"Artifact directory changed while archiving: {directory}"
                        )
                    archive.addfile(info)
                for file_entry in snapshot["files"]:
                    file_path = file_entry["path"]
                    info = archive.gettarinfo(
                        str(file_path),
                        arcname=file_entry["relative"],
                    )
                    if not info.isfile():
                        raise OSError(
                            f"Artifact file changed while archiving: {file_path}"
                        )
                    with file_path.open("rb") as source:
                        archive.addfile(info, source)
                manifest = "".join(
                    f"{entry['sha256']}  {entry['relative']}\n"
                    for entry in snapshot["files"]
                ).encode("utf-8")
                manifest_info = tarfile.TarInfo(self._manifest_name)
                manifest_info.size = len(manifest)
                manifest_info.mode = 0o600
                manifest_info.mtime = 0
                archive.addfile(manifest_info, io.BytesIO(manifest))
            return archive_path
        except Exception:
            try:
                archive_path.unlink()
            except OSError:
                pass
            raise

    @staticmethod
    def _new_deployment_id():
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{timestamp}-{secrets.token_hex(4)}"

    @staticmethod
    def _remote_paths(target_path, deployment_id):
        return {
            "active": target_path,
            "stage": f"{target_path}.qzx-stage-{deployment_id}",
            "previous": f"{target_path}.qzx-previous-{deployment_id}",
            "failed": f"{target_path}.qzx-failed-{deployment_id}",
            "backup_archive": f"{target_path}.qzx-backup-{deployment_id}.tar.gz",
            "absence_marker": f"{target_path}.qzx-backup-{deployment_id}.absent",
            "lock": f"{target_path}.qzx-deploy-lock",
            "deployment_id": deployment_id,
        }

    @staticmethod
    def _ssh_command(
        executable,
        target_host,
        port,
        ssh_key,
        known_hosts,
    ):
        command = [
            executable,
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "StrictHostKeyChecking=yes",
            "-p",
            str(port),
        ]
        if ssh_key is not None:
            command.extend(
                [
                    "-o",
                    "IdentitiesOnly=yes",
                    "-i",
                    str(ssh_key),
                ]
            )
        if known_hosts is not None:
            command.extend(
                [
                    "-o",
                    f"UserKnownHostsFile={known_hosts}",
                ]
            )
        command.append(target_host)
        return command

    def _run_ssh(self, ssh_command, remote_command, timeout=30, stdin=None):
        try:
            result = subprocess.run(
                [*ssh_command, remote_command],
                stdin=subprocess.DEVNULL if stdin is None else stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return {
                "success": False,
                "returncode": None,
                "stdout": "",
                "stderr": f"{type(exc).__name__}: {exc}",
            }
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.decode("utf-8", errors="replace").strip(),
            "stderr": result.stderr.decode("utf-8", errors="replace").strip(),
        }

    def _remote_preflight(self, ssh_command, paths, timeout):
        active = shlex.quote(paths["active"])
        parent = shlex.quote(str(PurePosixPath(paths["active"]).parent))
        command = (
            "set -eu; "
            "command -v tar >/dev/null; "
            "command -v sha256sum >/dev/null; "
            f"test -d {parent}; test -w {parent}; "
            f"if test -L {active}; then printf symlink; "
            f"elif test -d {active}; then printf directory; "
            f"elif test -e {active}; then printf non_directory; "
            "else printf absent; fi"
        )
        result = self._run_ssh(ssh_command, command, timeout=timeout)
        state = result["stdout"]
        if not result["success"]:
            return {
                "success": False,
                "state": "unknown",
                "error_code": "remote_preflight_failed",
                "message": (
                    "Remote preflight failed without changing the target: "
                    + self._bounded_error(result)
                ),
            }
        if state in {"symlink", "non_directory"}:
            return {
                "success": False,
                "state": state,
                "error_code": "unsafe_remote_target",
                "message": (
                    f"Remote target is a {state.replace('_', ' ')}. QZX only "
                    "promotes to an absent path or a real directory."
                ),
            }
        if state not in {"directory", "absent"}:
            return {
                "success": False,
                "state": "unknown",
                "error_code": "unexpected_remote_state",
                "message": (
                    "Remote preflight returned an unrecognized state and QZX "
                    "refused to continue."
                ),
            }
        return {"success": True, "state": state}

    def _create_remote_backup(self, ssh_command, paths, state):
        active = shlex.quote(paths["active"])
        if state == "directory":
            archive = shlex.quote(paths["backup_archive"])
            parent = shlex.quote(str(PurePosixPath(paths["active"]).parent))
            name = shlex.quote(PurePosixPath(paths["active"]).name)
            command = (
                "set -eu; umask 077; "
                f"test ! -e {archive}; "
                f"tar -czf {archive} -C {parent} -- {name}; "
                f"tar -tzf {archive} >/dev/null"
            )
            success_status = "verified archive created"
        else:
            marker = shlex.quote(paths["absence_marker"])
            command = (
                "set -eu; umask 077; "
                f"test ! -e {marker}; "
                f"printf '%s\\n' 'target was absent' > {marker}; "
                f"test -s {marker}"
            )
            success_status = "verified absence marker created"
        result = self._run_ssh(ssh_command, command, timeout=120)
        return {
            "success": result["success"],
            "status": (
                success_status
                if result["success"]
                else f"failed: {self._bounded_error(result)}"
            ),
            "message": self._bounded_error(result),
        }

    def _prepare_remote_stage(self, ssh_command, paths, deployment_id):
        lock = shlex.quote(paths["lock"])
        owner = shlex.quote(f"{paths['lock']}/owner")
        stage = shlex.quote(paths["stage"])
        identifier = shlex.quote(deployment_id)
        command = (
            "set -eu; "
            f"test ! -e {stage}; "
            f"if ! mkdir -- {lock}; then "
            "printf '%s' 'another deployment owns the lock' >&2; exit 73; fi; "
            f"if printf '%s' {identifier} > {owner} && mkdir -- {stage}; then "
            ":; else "
            f"rm -f -- {owner}; rmdir -- {lock} 2>/dev/null || true; exit 74; fi"
        )
        result = self._run_ssh(ssh_command, command)
        if result["success"]:
            return {"success": True, "lock": "acquired", "cleanup": "pending"}
        is_lock = result["returncode"] == 73
        return {
            "success": False,
            "error_code": (
                "deployment_locked" if is_lock else "remote_stage_failed"
            ),
            "message": (
                "Another deployment already owns the remote lock."
                if is_lock
                else "The remote staging directory could not be prepared: "
                + self._bounded_error(result)
            ),
            "lock": "already held" if is_lock else "not acquired",
            "cleanup": "not needed" if is_lock else "attempted by remote preflight",
        }

    def _upload_archive(
        self,
        ssh_command,
        paths,
        deployment_id,
        archive_path,
    ):
        owner_check = self._owner_check(paths, deployment_id)
        stage = shlex.quote(paths["stage"])
        command = (
            f"set -eu; {owner_check}; "
            f"tar -xzf - -C {stage}"
        )
        with Path(archive_path).open("rb") as archive:
            result = self._run_ssh(
                ssh_command,
                command,
                timeout=300,
                stdin=archive,
            )
        return {
            "success": result["success"],
            "message": self._bounded_error(result),
        }

    def _verify_remote_stage(
        self,
        ssh_command,
        paths,
        deployment_id,
        files_count,
    ):
        owner_check = self._owner_check(paths, deployment_id)
        stage = shlex.quote(paths["stage"])
        manifest = shlex.quote(self._manifest_name)
        command = (
            f"set -eu; {owner_check}; cd -- {stage}; "
            "test -z \"$(find . -type l -print -quit)\"; "
            "test -z \"$(find . -mindepth 1 ! -type f ! -type d -print -quit)\"; "
            f"test \"$(find . -type f | wc -l)\" -eq {files_count + 1}; "
            f"sha256sum -c -- {manifest} >/dev/null; "
            f"rm -- {manifest}"
        )
        result = self._run_ssh(ssh_command, command, timeout=120)
        return {
            "success": result["success"],
            "message": self._bounded_error(result),
        }

    def _promote(
        self,
        ssh_command,
        paths,
        deployment_id,
        remote_state,
    ):
        owner_check = self._owner_check(paths, deployment_id)
        active = shlex.quote(paths["active"])
        stage = shlex.quote(paths["stage"])
        previous = shlex.quote(paths["previous"])
        if remote_state == "directory":
            command = (
                f"set -eu; {owner_check}; "
                f"test -d {active}; test ! -e {previous}; "
                f"mv -- {active} {previous}; "
                f"if mv -- {stage} {active}; then :; "
                f"else mv -- {previous} {active}; exit 75; fi"
            )
        else:
            command = (
                f"set -eu; {owner_check}; "
                f"test ! -e {active}; mv -- {stage} {active}"
            )
        result = self._run_ssh(ssh_command, command)
        return {
            "success": result["success"],
            "message": self._bounded_error(result),
        }

    def _check_health(
        self,
        url,
        expected_text,
        attempts,
        interval,
        timeout,
    ):
        failures = []
        for attempt in range(1, attempts + 1):
            try:
                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "QZX-Deploy-Health-Check/1",
                        "Cache-Control": "no-cache",
                    },
                )
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    status_code = int(response.status)
                    body = response.read(1024 * 1024).decode(
                        "utf-8",
                        errors="replace",
                    )
                if not 200 <= status_code < 400:
                    failures.append(
                        f"attempt {attempt}: HTTP {status_code}"
                    )
                elif expected_text is not None and expected_text not in body:
                    failures.append(
                        f"attempt {attempt}: expected response text was absent"
                    )
                else:
                    return {
                        "passed": True,
                        "attempt": attempt,
                        "status_code": status_code,
                        "expected_text_checked": expected_text is not None,
                    }
            except (OSError, urllib.error.URLError, ValueError) as exc:
                failures.append(
                    f"attempt {attempt}: {type(exc).__name__}: {exc}"
                )
            if attempt < attempts and interval:
                time.sleep(interval)
        return {
            "passed": False,
            "attempts": attempts,
            "expected_text_checked": expected_text is not None,
            "last_failure": failures[-1] if failures else "unknown failure",
        }

    def _rollback(
        self,
        ssh_command,
        paths,
        deployment_id,
        remote_state,
    ):
        owner_check = self._owner_check(paths, deployment_id)
        active = shlex.quote(paths["active"])
        failed = shlex.quote(paths["failed"])
        previous = shlex.quote(paths["previous"])
        lock_cleanup = self._lock_cleanup_shell(paths)
        if remote_state == "directory":
            command = (
                f"set -eu; {owner_check}; "
                f"test -d {active}; test -d {previous}; test ! -e {failed}; "
                f"mv -- {active} {failed}; "
                f"if mv -- {previous} {active}; then {lock_cleanup}; "
                f"else mv -- {failed} {active} 2>/dev/null || true; exit 76; fi"
            )
        else:
            command = (
                f"set -eu; {owner_check}; "
                f"test -d {active}; test ! -e {failed}; "
                f"mv -- {active} {failed}; {lock_cleanup}"
            )
        result = self._run_ssh(ssh_command, command)
        return {
            "success": result["success"],
            "status": (
                "previous remote state restored"
                if result["success"]
                else f"failed: {self._bounded_error(result)}"
            ),
            "cleanup": (
                "lock released; failed release retained for inspection"
                if result["success"]
                else "lock retained for manual recovery"
            ),
        }

    def _cleanup_unpromoted(self, ssh_command, paths, deployment_id):
        owner_check = self._owner_check(paths, deployment_id)
        stage = shlex.quote(paths["stage"])
        lock_cleanup = self._lock_cleanup_shell(paths)
        command = (
            f"set -eu; {owner_check}; "
            f"rm -rf -- {stage}; {lock_cleanup}"
        )
        result = self._run_ssh(ssh_command, command)
        return (
            "staging removed and lock released"
            if result["success"]
            else "failed; staging and lock may require manual cleanup"
        )

    def _release_lock(self, ssh_command, paths, deployment_id):
        command = (
            f"set -eu; {self._owner_check(paths, deployment_id)}; "
            f"{self._lock_cleanup_shell(paths)}"
        )
        result = self._run_ssh(ssh_command, command)
        return "completed" if result["success"] else "failed"

    @staticmethod
    def _owner_check(paths, deployment_id):
        owner = shlex.quote(f"{paths['lock']}/owner")
        identifier = shlex.quote(deployment_id)
        return f"test \"$(cat -- {owner})\" = {identifier}"

    @staticmethod
    def _lock_cleanup_shell(paths):
        owner = shlex.quote(f"{paths['lock']}/owner")
        lock = shlex.quote(paths["lock"])
        return f"rm -- {owner}; rmdir -- {lock}"

    @staticmethod
    def _bounded_error(result):
        message = result.get("stderr") or result.get("stdout") or (
            f"exit code {result.get('returncode')}"
        )
        return str(message).strip()[:1_000]

    @staticmethod
    def _failure(error_code, message, **details):
        return {
            "success": False,
            "error_code": error_code,
            "error": message,
            "message": message,
            "details": details,
        }
