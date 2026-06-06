#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the QZXVersion command
"""

import platform
from unittest.mock import patch, MagicMock
from qzx.commands.system.version import QZXVersionCommand

class TestQZXVersionCommand:
    """
    Tests for the QZXVersion command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = QZXVersionCommand()
        
    def test_execute_success(self):
        """Test successful execution of qzxVersion"""
        # Mock platform functions to have stable/predictable values
        with patch("platform.system", return_value="Windows"), \
             patch("platform.version", return_value="10.0.19045"), \
             patch("platform.release", return_value="10"), \
             patch("platform.machine", return_value="AMD64"), \
             patch("platform.processor", return_value="Intel64 Family 6"), \
             patch("platform.python_version", return_value="3.13.12"), \
             patch("platform.python_implementation", return_value="CPython"), \
             patch("qzx.core.command_loader.CommandLoader.discover_commands") as mock_discover:
             
            # Mock CommandLoader to return 3 dummy commands
            mock_discover.return_value = {
                "cmd1": MagicMock(__name__="CommandOne"),
                "cmd2": MagicMock(__name__="CommandTwo"),
                "cmd3": MagicMock(__name__="CommandThree")
            }
            
            result = self.command.execute()
            
            # Verify the result structure
            assert result["success"] is True
            assert "version" in result
            assert result["system_info"]["os"] == "Windows"
            assert result["system_info"]["os_version"] == "10.0.19045"
            assert result["system_info"]["python_version"] == "3.13.12"
            assert result["qzx_info"]["command_count"] == 3
            assert "QZX Version" in result["message"]
            assert "running on Windows" in result["message"]
            assert "3 commands available" in result["message"]

    @patch("platform.system")
    def test_execute_exception_handling(self, mock_system):
        """Test how the command handles unexpected errors during execution"""
        # Force platform.system() to raise an exception
        mock_system.side_effect = Exception("Simulated platform error")
        
        result = self.command.execute()
        
        # Verify the exception is gracefully caught and returned
        assert result["success"] is False
        assert "error" in result
        assert "Simulated platform error" in result["error"]
        assert "Failed to retrieve QZX version information" in result["message"]
