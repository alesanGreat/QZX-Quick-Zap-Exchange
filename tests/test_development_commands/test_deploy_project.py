#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the DeployProject command
"""

import os
from unittest.mock import patch, MagicMock
from qzx.commands.development.deploy_project import DeployProjectCommand

class TestDeployProjectCommand:
    """
    Tests for the DeployProject command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = DeployProjectCommand()
        
    def test_deploy_project_nonexistent_local_path(self):
        """Test deploying from non-existent local path"""
        result = self.command.execute(
            target_host="deploy@5.161.246.120",
            target_path="/var/www/html/",
            path="nonexistent_folder_xyz"
        )
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    @patch("subprocess.run")
    def test_deploy_project_dry_run(self, mock_run, tmp_path):
        """Test dry run deployment flow"""
        # Create a mock build file
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        
        result = self.command.execute(
            target_host="deploy@host",
            target_path="/var/www/html/",
            path=str(tmp_path),
            dry_run=True,
            skip_build=True,
            health_url="https://site.com"
        )
        
        assert result["success"] is True
        details = result["details"]
        assert details["dry_run_mode"] is True
        assert details["backup_taken"] == "dry_run"
        assert details["synced"] == "dry_run"
        assert details["permissions_set"] == "dry_run"
        assert details["health_check"] == "dry_run"
        
        # Subprocess shouldn't have been run since dry_run=True and skip_build=True
        mock_run.assert_not_called()
        
    @patch("subprocess.run")
    @patch("urllib.request.urlopen")
    def test_deploy_project_failed_health_check_rollback(self, mock_urlopen, mock_run, tmp_path):
        """Test deployment fails health check and triggers automatic rollback"""
        # Mock subprocess returns success for build and ssh/rsync commands
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "output"
        mock_run.return_value = mock_res
        
        # Mock urlopen to raise Exception (failed health check)
        mock_urlopen.side_effect = Exception("HTTP 500 Internal Server Error")
        
        # Create mock build file
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        
        result = self.command.execute(
            target_host="deploy@host",
            target_path="/var/www/html/",
            path=str(tmp_path),
            dry_run=False,
            skip_build=True,
            health_url="https://site.com",
            restart_cmd="nginx -s reload"
        )
        
        assert result["success"] is False
        assert "Health check failed" in result["error"]
        details = result["details"]
        assert details["health_check"] == "failed"
        assert details["rollback_executed"] == "success"
        
        # Verify subprocess.run was called for rollback and restore
        # It should have called ssh commands
        assert mock_run.call_count >= 3 # Backup, Sync, Perms, Restart, Rollback
