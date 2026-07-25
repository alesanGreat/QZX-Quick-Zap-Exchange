"""Safe tests for deployProject without inventing a remote deployment."""

from qzx.commands.development.deploy_project import DeployProjectCommand


class TestDeployProjectCommand:
    def setup_method(self):
        self.command = DeployProjectCommand()

    def test_deploy_project_nonexistent_local_path(self):
        result = self.command.execute(
            target_host="deploy@example.invalid",
            target_path="/var/www/html/",
            path="nonexistent_folder_xyz",
        )

        assert result["success"] is False
        assert "does not exist" in result["error"]

    def test_dry_run_needs_no_remote_or_process_executable(
        self,
        tmp_path,
        monkeypatch,
    ):
        """A preview must remain useful without touching local or remote tools."""

        (tmp_path / "dist").mkdir()
        monkeypatch.setenv("PATH", "")

        result = self.command.execute(
            target_host="deploy@example.invalid",
            target_path="/var/www/html/",
            path=str(tmp_path),
            dry_run=True,
            skip_build=True,
            health_url="https://example.invalid/health",
        )

        assert result["success"] is True
        details = result["details"]
        assert details["dry_run_mode"] is True
        assert details["build"] == "skipped"
        assert details["backup_taken"] == "dry_run"
        assert details["synced"] == "dry_run"
        assert details["permissions_set"] == "dry_run"
        assert details["health_check"] == "dry_run"
