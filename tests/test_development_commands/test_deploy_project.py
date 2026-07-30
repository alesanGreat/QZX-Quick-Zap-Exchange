"""Safe contract tests for deployProject's explicit deployment plan."""

import tarfile

from qzx.commands.development.deploy_project import DeployProjectCommand


class TestDeployProjectCommand:
    def setup_method(self):
        self.command = DeployProjectCommand()

    def test_nonexistent_artifact_is_rejected(self):
        result = self.command.execute(
            target_host="deploy@example.invalid",
            target_path="/srv/example/current",
            path="nonexistent_folder_xyz",
        )

        assert result["success"] is False
        assert result["error_code"] == "artifact_not_found"

    def test_preview_hashes_explicit_artifact_without_external_tools(
        self,
        tmp_path,
        monkeypatch,
    ):
        """A preview must neither build nor connect to the target."""

        artifact = tmp_path / "dist"
        (artifact / "assets").mkdir(parents=True)
        (artifact / "index.html").write_text("QZX\n", encoding="utf-8")
        (artifact / "assets" / "app.js").write_text(
            "console.log('ready');\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PATH", "")

        result = self.command.execute(
            target_host="deploy@example.invalid",
            target_path="/srv/example/current",
            path=str(artifact),
            dry_run=True,
            health_url="https://example.invalid/health",
            deployment_id="test-preview-001",
        )

        assert result["success"] is True
        details = result["details"]
        assert details["status"] == "ready"
        assert details["dry_run"] is True
        assert details["artifact"]["path"] == str(artifact)
        assert details["artifact"]["files"] == 2
        assert details["artifact"]["directories"] == 1
        assert len(details["artifact"]["sha256"]) == 64
        assert details["remote"]["active"] == "/srv/example/current"
        assert details["remote"]["stage"].endswith(
            ".qzx-stage-test-preview-001"
        )
        assert "local build" in details["excluded_actions"]
        assert "arbitrary remote commands" in details["excluded_actions"]

    def test_live_deployment_requires_health_verification(self, tmp_path):
        artifact = tmp_path / "artifact"
        artifact.mkdir()
        (artifact / "release.txt").write_text("ready", encoding="utf-8")

        result = self.command.execute(
            target_host="deploy@example.invalid",
            target_path="/srv/example/current",
            path=str(artifact),
            dry_run=False,
        )

        assert result["success"] is False
        assert result["error_code"] == "health_url_required"
        assert result["details"]["status"] == "blocked_before_connection"

    def test_invoke_rejects_unverified_live_request_before_backup(
        self,
        tmp_path,
        monkeypatch,
    ):
        artifact = tmp_path / "artifact"
        artifact.mkdir()
        (artifact / "release.txt").write_text("ready", encoding="utf-8")
        backup_root = tmp_path / "backups"
        monkeypatch.setenv("QZX_BACKUPS_PATH", str(backup_root))

        result = self.command.invoke(
            [
                "--target-host",
                "deploy@example.invalid",
                "--target-path",
                "/srv/example/current",
                "--path",
                str(artifact),
                "--dry-run",
                "false",
            ]
        )

        assert result["success"] is False
        assert result["error_code"] == "health_url_required"
        assert "safety_backup" not in result["meta"]
        assert not backup_root.exists()

    def test_empty_artifact_cannot_replace_remote_release(self, tmp_path):
        artifact = tmp_path / "empty"
        artifact.mkdir()

        result = self.command.execute(
            target_host="deploy@example.invalid",
            target_path="/srv/example/current",
            path=str(artifact),
        )

        assert result["success"] is False
        assert result["error_code"] == "empty_artifact"

    def test_unsafe_remote_destination_and_host_are_rejected(self, tmp_path):
        artifact = tmp_path / "artifact"
        artifact.mkdir()
        (artifact / "release.txt").write_text("ready", encoding="utf-8")

        root_result = self.command.execute(
            target_host="deploy@example.invalid",
            target_path="/",
            path=str(artifact),
        )
        option_result = self.command.execute(
            target_host="-Fmalicious-config",
            target_path="/srv/example/current",
            path=str(artifact),
        )

        assert root_result["error_code"] == "unsafe_target_path"
        assert option_result["error_code"] == "invalid_target_host"

    def test_malformed_health_url_port_is_rejected(self, tmp_path):
        artifact = tmp_path / "artifact"
        artifact.mkdir()
        (artifact / "release.txt").write_text("ready", encoding="utf-8")

        result = self.command.execute(
            target_host="deploy@example.invalid",
            target_path="/srv/example/current",
            path=str(artifact),
            health_url="https://example.invalid:not-a-port/health",
        )

        assert result["success"] is False
        assert result["error_code"] == "invalid_health_url"
        assert "secret" not in str(result)

    def test_health_url_query_is_rejected_to_avoid_token_disclosure(
        self,
        tmp_path,
    ):
        artifact = tmp_path / "artifact"
        artifact.mkdir()
        (artifact / "release.txt").write_text("ready", encoding="utf-8")

        result = self.command.execute(
            target_host="deploy@example.invalid",
            target_path="/srv/example/current",
            path=str(artifact),
            health_url="https://example.invalid/health?token=secret",
        )

        assert result["success"] is False
        assert result["error_code"] == "invalid_health_url"

    def test_preview_does_not_echo_expected_health_text(self, tmp_path):
        artifact = tmp_path / "artifact"
        artifact.mkdir()
        (artifact / "release.txt").write_text("ready", encoding="utf-8")

        result = self.command.execute(
            target_host="deploy@example.invalid",
            target_path="/srv/example/current",
            path=str(artifact),
            health_url="https://example.invalid/health",
            health_expect="sensitive marker",
        )

        verification = result["details"]["verification"]
        assert verification["health_expect_configured"] is True
        assert "sensitive marker" not in str(result)

    def test_missing_explicit_known_hosts_file_is_rejected(self, tmp_path):
        artifact = tmp_path / "artifact"
        artifact.mkdir()
        (artifact / "release.txt").write_text("ready", encoding="utf-8")

        result = self.command.execute(
            target_host="deploy@example.invalid",
            target_path="/srv/example/current",
            path=str(artifact),
            known_hosts=str(tmp_path / "missing-known-hosts"),
        )

        assert result["success"] is False
        assert result["error_code"] == "known_hosts_not_found"

    def test_ssh_transport_requires_known_server_identity(self, tmp_path):
        key = tmp_path / "deploy-key"
        known_hosts = tmp_path / "known-hosts"
        key.write_text("test key", encoding="utf-8")
        known_hosts.write_text("example.invalid test-key", encoding="utf-8")

        command = self.command._ssh_command(
            "ssh",
            "deploy@example.invalid",
            2237,
            key,
            known_hosts,
        )

        assert "StrictHostKeyChecking=yes" in command
        assert "IdentitiesOnly=yes" in command
        assert f"UserKnownHostsFile={known_hosts}" in command

    def test_legacy_implicit_build_and_remote_command_options_are_rejected(self):
        result = self.command.invoke(
            [
                "--target-host",
                "deploy@example.invalid",
                "--target-path",
                "/srv/example/current",
                "--skip-build",
                "true",
            ]
        )

        assert result["success"] is False
        assert result["error_code"] == "usage_error"
        assert "Unknown option '--skip-build'" in result["message"]

    def test_archive_contains_only_snapshot_and_sha256_manifest(self, tmp_path):
        artifact = tmp_path / "artifact"
        (artifact / "assets").mkdir(parents=True)
        (artifact / "index.html").write_text("QZX", encoding="utf-8")
        (artifact / "assets" / "app.js").write_bytes(b"ready\n")
        snapshot = self.command._snapshot_artifact(artifact)

        archive_path = self.command._create_local_archive(artifact, snapshot)
        try:
            with tarfile.open(archive_path, "r:gz") as archive:
                names = set(archive.getnames())
                manifest = archive.extractfile(
                    self.command._manifest_name
                ).read().decode("utf-8")
        finally:
            archive_path.unlink()

        assert names == {
            "assets",
            "assets/app.js",
            "index.html",
            ".qzx-manifest-sha256",
        }
        assert "  index.html\n" in manifest
        assert "  assets/app.js\n" in manifest

    def test_reserved_manifest_directory_is_rejected(self, tmp_path):
        artifact = tmp_path / "artifact"
        artifact.mkdir()
        (artifact / "release.txt").write_text("ready", encoding="utf-8")
        (artifact / self.command._manifest_name).mkdir()

        result = self.command.execute(
            target_host="deploy@example.invalid",
            target_path="/srv/example/current",
            path=str(artifact),
        )

        assert result["success"] is False
        assert result["error_code"] == "unsafe_artifact_entry"
