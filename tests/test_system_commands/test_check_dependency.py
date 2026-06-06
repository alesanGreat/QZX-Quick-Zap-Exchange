#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the CheckDependency command
"""

import os
import subprocess
from unittest.mock import patch, MagicMock
from qzx.commands.system.check_dependency import CheckDependencyCommand

class TestCheckDependencyCommand:
    """
    Tests for the CheckDependency command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = CheckDependencyCommand()
        
    def test_empty_dependency_name(self):
        """Test with an empty dependency name"""
        result = self.command.execute("")
        assert result["success"] is False
        assert "cannot be empty" in result["error"]
        
    @patch("shutil.which", return_value=None)
    def test_dependency_not_installed(self, mock_which):
        """Test when dependency is not in PATH"""
        result = self.command.execute("nonexistent_tool_abc")
        assert result["success"] is True
        assert result["installed"] is False
        assert "is not installed" in result["message"]
        
    @patch("shutil.which", return_value="/usr/bin/git")
    @patch("subprocess.run")
    def test_dependency_installed_with_version(self, mock_run, mock_which):
        """Test when dependency is installed and successfully returns version"""
        # Configure subprocess mock
        mock_result = MagicMock()
        mock_result.stdout = "git version 2.40.1.windows.1"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = self.command.execute("git")
        assert result["success"] is True
        assert result["installed"] is True
        assert result["version"] == "2.40.1"
        assert result["executable_path"] == os.path.abspath("/usr/bin/git")
        assert "Version: 2.40.1" in result["message"]
        
    @patch("shutil.which", return_value="/usr/bin/node")
    @patch("subprocess.run")
    def test_dependency_installed_unknown_version(self, mock_run, mock_which):
        """Test when dependency is installed but version cannot be parsed"""
        # Configure subprocess mock to return empty/junk output
        mock_result = MagicMock()
        mock_result.stdout = "junk output without version number"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = self.command.execute("node")
        assert result["success"] is True
        assert result["installed"] is True
        assert result["version"] is None
        assert "version could not be determined" in result["message"]
        
    @patch("shutil.which")
    def test_execute_exception_handling(self, mock_which):
        """Test how the command handles unexpected errors during execution"""
        mock_which.side_effect = Exception("Simulated check error")
        
        result = self.command.execute("python")
        assert result["success"] is False
        assert "Simulated check error" in result["error"]
        assert "Failed to check dependency status" in result["message"]
