"""Real deployProject integration against an ephemeral localhost SSH target.

This module is intentionally executed by its dedicated GitHub Actions
workflow. It is not a simulated unit test: sshd, ssh, rsync, tar, an HTTP
server, filesystem mutations, backup creation, and rollback are all real.
"""

import os
from pathlib import Path
import base64
import shlex
import socket
import subprocess
import sys
import tarfile
import time
import uuid

import pytest

from qzx.commands.development.deploy_project import DeployProjectCommand


def _required_environment(name):
    value = os.environ.get(name)
    if not value:
        pytest.fail(
            f"{name} is required; run this module through its dedicated "
            "real-deployment workflow."
        )
    return value


def _run_ssh(config, remote_command, check=True):
    return subprocess.run(
        [
            "ssh",
            "-p",
            config["port"],
            "-i",
            str(config["ssh_key"]),
            config["host"],
            remote_command,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=check,
    )


def _write_remote_file(config, path, content):
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    _run_ssh(
        config,
        (
            f"printf %s {shlex.quote(encoded)} | base64 -d > "
            f"{shlex.quote(str(path))}"
        ),
    )


@pytest.fixture
def deployment_environment(tmp_path, monkeypatch):
    host = _required_environment("QZX_REAL_DEPLOY_HOST")
    port = _required_environment("QZX_REAL_DEPLOY_PORT")
    ssh_key = Path(_required_environment("QZX_REAL_DEPLOY_SSH_KEY"))
    target_root = Path(_required_environment("QZX_REAL_DEPLOY_TARGET_ROOT"))
    target = target_root / uuid.uuid4().hex

    backup_directory = tmp_path / "qzx-safety-backups"
    monkeypatch.delenv("QZX_SAFETY", raising=False)
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backup_directory))
    monkeypatch.setenv("QZX_BACKUPS_FORMAT", "ZIP")

    config = {
        "host": host,
        "port": port,
        "ssh_key": ssh_key,
        "target": target,
        "backup_directory": backup_directory,
    }
    _run_ssh(config, f"mkdir -p {shlex.quote(str(target))}")
    try:
        yield config
    finally:
        pid_path = target / ".http-server.pid"
        if pid_path.exists():
            _run_ssh(
                config,
                (
                    f"kill $(cat {shlex.quote(str(pid_path))}) "
                    "2>/dev/null || true"
                ),
                check=False,
            )
        _run_ssh(
            config,
            f"rm -rf -- {shlex.quote(str(target))}",
            check=False,
        )
        _run_ssh(
            config,
            "rm -f -- /tmp/backup_*.tar.gz",
            check=False,
        )


def _command_arguments(config, source, health_url, restart_cmd=None):
    arguments = [
        "--target_host",
        config["host"],
        "--target_path",
        str(config["target"]),
        "--path",
        str(source),
        "--port",
        config["port"],
        "--ssh_key",
        str(config["ssh_key"]),
        "--health_url",
        health_url,
        "--skip_build",
        "true",
        "--dry_run",
        "false",
    ]
    if restart_cmd:
        arguments.extend(["--restart_cmd", restart_cmd])
    return arguments


def _unused_local_port():
    with socket.socket() as reserved_socket:
        reserved_socket.bind(("127.0.0.1", 0))
        return reserved_socket.getsockname()[1]


def _wait_until_listening(port):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    pytest.fail(f"real deployed HTTP service did not listen on port {port}")


def test_real_ssh_deployment_backup_sync_restart_and_health_check(
    tmp_path,
    deployment_environment,
):
    config = deployment_environment
    source = tmp_path / "project"
    dist = source / "dist"
    dist.mkdir(parents=True)
    (dist / "release.txt").write_text(
        "real QZX deployment\n",
        encoding="utf-8",
    )
    _write_remote_file(
        config,
        config["target"] / "old-release.txt",
        "previous deployment\n",
    )

    health_port = _unused_local_port()
    pid_path = config["target"] / ".http-server.pid"
    log_path = config["target"].parent / f"{config['target'].name}.http.log"
    restart_cmd = (
        f"nohup {shlex.quote(sys.executable)} -m http.server {health_port} "
        f"--bind 127.0.0.1 --directory "
        f"{shlex.quote(str(config['target']))} </dev/null "
        f">{shlex.quote(str(log_path))} 2>&1 & "
        f"echo $! > {shlex.quote(str(pid_path))}"
    )

    result = DeployProjectCommand().invoke(
        _command_arguments(
            config,
            source,
            f"http://127.0.0.1:{health_port}/release.txt",
            restart_cmd,
        )
    )

    assert result["success"] is True, result
    assert result["details"]["backup_taken"].startswith("success:")
    assert result["details"]["synced"] == "success"
    assert result["details"]["permissions_set"] == "success"
    assert result["details"]["service_restarted"] == "success"
    assert result["details"]["health_check"].startswith("passed on attempt")
    assert result["details"]["rollback_executed"] == "skipped"
    assert (config["target"] / "release.txt").read_text(
        encoding="utf-8"
    ) == "real QZX deployment\n"
    assert not (config["target"] / "old-release.txt").exists()
    assert Path(result["meta"]["safety_backup"]["path"]).exists()

    remote_backup = Path(result["details"]["remote_backup_path"])
    assert remote_backup.exists()
    with tarfile.open(remote_backup, "r:gz") as archive:
        assert archive.extractfile("./old-release.txt").read() == (
            b"previous deployment\n"
        )
    _wait_until_listening(health_port)


def test_real_failed_health_check_restores_every_previous_remote_file(
    tmp_path,
    deployment_environment,
):
    config = deployment_environment
    source = tmp_path / "broken-project"
    dist = source / "dist"
    dist.mkdir(parents=True)
    (dist / "broken-release.txt").write_text(
        "must be rolled back\n",
        encoding="utf-8",
    )
    _write_remote_file(
        config,
        config["target"] / "stable-release.txt",
        "known good deployment\n",
    )
    _write_remote_file(
        config,
        config["target"] / ".stable-hidden",
        "hidden state\n",
    )
    closed_port = _unused_local_port()

    result = DeployProjectCommand().invoke(
        _command_arguments(
            config,
            source,
            f"http://127.0.0.1:{closed_port}/health",
        )
    )

    assert result["success"] is False, result
    assert result["details"]["synced"] == "success"
    assert result["details"]["health_check"] == "failed"
    assert result["details"]["rollback_executed"] == "success"
    assert "previous deployment was restored" in result["message"]
    assert not (config["target"] / "broken-release.txt").exists()
    assert (config["target"] / "stable-release.txt").read_text(
        encoding="utf-8"
    ) == "known good deployment\n"
    assert (config["target"] / ".stable-hidden").read_text(
        encoding="utf-8"
    ) == "hidden state\n"
