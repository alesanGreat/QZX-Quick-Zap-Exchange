#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the GetGitStatus command
"""

import os
import subprocess
from unittest.mock import MagicMock, patch
from qzx.commands.development.get_git_status import GetGitStatusCommand

class TestGetGitStatusCommand:
    """
    Tests for the GetGitStatus command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = GetGitStatusCommand()
        
    def test_nonexistent_directory(self):
        """Test with a directory that does not exist"""
        result = self.command.execute("non_existent_dir_xyz_123")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_file_instead_of_directory(self, tmp_path):
        """Test with a file path instead of a directory"""
        file_path = tmp_path / "test.txt"
        file_path.touch()
        
        result = self.command.execute(str(file_path))
        assert result["success"] is False
        assert "is not a directory" in result["error"]
        
    @patch("subprocess.run")
    def test_git_not_installed(self, mock_run):
        """Test behavior when git command is not available"""
        # Mock git --version to raise FileNotFoundError
        mock_run.side_effect = FileNotFoundError()
        
        result = self.command.execute(".")
        assert result["success"] is False
        assert "Git is not installed" in result["error"]
        
    @patch("subprocess.run")
    def test_not_git_repository(self, mock_run, tmp_path):
        """Test directory that is not a git repository"""
        # Git is installed (first call succeeds)
        version_mock = MagicMock()
        version_mock.returncode = 0
        
        # Inside worktree check fails (second call)
        worktree_mock = MagicMock()
        worktree_mock.returncode = 1
        worktree_mock.stdout = "false"
        
        mock_run.side_effect = [version_mock, worktree_mock]
        
        result = self.command.execute(str(tmp_path))
        assert result["success"] is True
        assert result["is_git_repository"] is False
        assert "not a Git repository" in result["message"]
        
    @patch("subprocess.run")
    def test_git_repository_full_status(self, mock_run, tmp_path):
        """Test successful parsing of a Git repository status with mock stdout"""
        # 1. version check
        version_mock = MagicMock(returncode=0)
        # 2. is worktree check
        worktree_mock = MagicMock(returncode=0, stdout="true\n")
        # 3. branch name check
        branch_mock = MagicMock(returncode=0, stdout="main\n")
        # 4. tracking branch check
        tracking_mock = MagicMock(returncode=0, stdout="origin/main\n")
        # 5. ahead/behind check
        counts_mock = MagicMock(returncode=0, stdout="2\t1\n")
        # 6. changes porcelain check (staged, modified, untracked, deleted)
        porcelain_mock = MagicMock(
            returncode=0,
            stdout="M  staged_modified.txt\nA  staged_new.txt\n M unstaged_modified.txt\nD  staged_deleted.txt\n D unstaged_deleted.txt\n?? untracked.txt\n"
        )
        # 7. remote urls
        remotes_mock = MagicMock(
            returncode=0,
            stdout="origin\thttps://github.com/user/repo.git (fetch)\norigin\thttps://github.com/user/repo.git (push)\n"
        )
        # 8. recent commits log
        log_mock = MagicMock(
            returncode=0,
            stdout="abcdef1|John Doe|2026-06-06|Add test file\nabcdef2|Jane Smith|2026-06-05|Fix bug\n"
        )
        
        mock_run.side_effect = [
            version_mock,
            worktree_mock,
            branch_mock,
            tracking_mock,
            counts_mock,
            porcelain_mock,
            remotes_mock,
            log_mock
        ]
        
        result = self.command.execute(str(tmp_path))
        
        assert result["success"] is True
        assert result["is_git_repository"] is True
        assert result["branch"] == "main"
        assert result["tracking_branch"] == "origin/main"
        assert result["sync_status"]["ahead"] == 2
        assert result["sync_status"]["behind"] == 1
        assert result["sync_status"]["in_sync"] is False
        
        # Verify changes structure
        assert result["changes_summary"]["staged_count"] == 3  # M , A , D 
        assert result["changes_summary"]["modified_count"] == 1  #  M
        assert result["changes_summary"]["deleted_count"] == 2  # D ,  D
        assert result["changes_summary"]["untracked_count"] == 1  # ??
        assert result["changes_summary"]["total_changes"] == 7
        
        # Verify remotes
        assert "origin" in result["remotes"]
        assert result["remotes"]["origin"]["fetch"] == "https://github.com/user/repo.git"
        assert result["remotes"]["origin"]["push"] == "https://github.com/user/repo.git"
        
        # Verify recent commits
        assert len(result["recent_commits"]) == 2
        assert result["recent_commits"][0]["hash"] == "abcdef1"
        assert result["recent_commits"][0]["author"] == "John Doe"
        assert result["recent_commits"][0]["date"] == "2026-06-06"
        assert result["recent_commits"][0]["subject"] == "Add test file"
