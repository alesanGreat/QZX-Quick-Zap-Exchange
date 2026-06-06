#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the GetCurrentUser command
"""

from unittest.mock import patch, MagicMock
from qzx.commands.system.get_current_user import GetCurrentUserCommand

class TestGetCurrentUserCommand:
    """
    Tests for the GetCurrentUser command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = GetCurrentUserCommand()
        
    def test_format_bytes(self):
        """Test formatting bytes to human-readable size"""
        assert self.command._format_bytes(500) == "500.00 B"
        assert self.command._format_bytes(1024) == "1.00 KB"
        assert self.command._format_bytes(1024 * 1024) == "1.00 MB"
        assert self.command._format_bytes(1024 * 1024 * 1024) == "1.00 GB"
        
    @patch.dict("os.environ", {
        "USER": "testuser",
        "HOME": "/home/testuser",
        "SHELL": "/bin/bash"
    })
    @patch("getpass.getuser")
    @patch("os.path.expanduser")
    @patch("psutil.Process")
    @patch("psutil.process_iter")
    def test_execute_success(self, mock_process_iter, mock_process_class, mock_expanduser, mock_getuser):
        """Test successful execution of getCurrentUser"""
        # Configure mocks
        mock_getuser.return_value = "testuser"
        mock_expanduser.return_value = "/home/testuser"
        
        # Mock current process username
        mock_proc_instance = MagicMock()
        mock_proc_instance.username.return_value = "testuser"
        mock_process_class.return_value = mock_proc_instance
        
        # Mock process iteration
        mock_p1 = MagicMock()
        mock_p1.info = {"username": "testuser", "memory_info": MagicMock(rss=1024 * 1024)}
        mock_p2 = MagicMock()
        mock_p2.info = {"username": "otheruser", "memory_info": MagicMock(rss=2048 * 1024)}
        mock_process_iter.return_value = [mock_p1, mock_p2]
        
        result = self.command.execute()
        
        # Verify the result structure
        assert result["success"] is True
        assert result["username"] == "testuser"
        assert result["home_directory"] == "/home/testuser"
        assert result["environment_variables"]["USER"] == "testuser"
        assert result["environment_variables"]["HOME"] == "/home/testuser"
        assert result["shell"] == "/bin/bash"
        assert result["user_id"] == "testuser"
        
        # Verify mocked processes stats
        assert result["processes"]["count"] == 1
        assert result["processes"]["total_memory_usage"] == 1024 * 1024
        assert result["processes"]["total_memory_usage_readable"] == "1.00 MB"
        assert "Current user: testuser" in result["message"]
        assert "User has 1 running processes" in result["message"]

    @patch("os.path.expanduser")
    def test_execute_exception_handling(self, mock_expanduser):
        """Test how the command handles unexpected errors during execution"""
        # Force os.path.expanduser to raise an exception to trigger the outer try-except
        mock_expanduser.side_effect = Exception("Simulated user error")
        
        result = self.command.execute()
        
        # Verify the exception is caught and returned gracefully
        assert result["success"] is False
        assert "error" in result
        assert "Simulated user error" in result["error"]
        assert "Failed to retrieve current user information" in result["message"]
