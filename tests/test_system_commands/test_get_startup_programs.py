#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the GetStartupPrograms command
"""

import sys
import os
from unittest.mock import patch, MagicMock
from qzx.commands.system.get_startup_programs import GetStartupProgramsCommand

class TestGetStartupProgramsCommand:
    """
    Tests for the GetStartupPrograms command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = GetStartupProgramsCommand()
        
    @patch("platform.system")
    @patch("os.path.exists")
    @patch("os.path.isdir")
    @patch("os.path.isfile")
    @patch("os.listdir")
    def test_windows_startup_programs(self, mock_listdir, mock_isfile, mock_isdir, mock_exists, mock_system):
        """Test retrieving startup items on Windows including Registry mock and Startup directory scanning"""
        mock_system.return_value = "Windows"
        mock_isdir.return_value = True
        mock_isfile.return_value = True
        
        # 1. Setup mock directories
        # os.path.exists will return True for the directories we look for, False for others
        def side_effect_exists(path):
            return "Startup" in path
        mock_exists.side_effect = side_effect_exists
        
        # listdir returns one mock shortcut file
        mock_listdir.return_value = ["shortcut.lnk"]
        
        # 2. Mock winreg
        mock_winreg = MagicMock()
        mock_key = MagicMock()
        
        # OpenKey returns the mock key
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        # QueryInfoKey returns (num_subkeys, num_values, last_modified)
        mock_winreg.QueryInfoKey.return_value = (0, 1, 0)
        # EnumValue returns (name, value, type)
        mock_winreg.EnumValue.return_value = ("OneDrive", "C:\\OneDrive.exe /background", 1)
        
        # Inject mock winreg into sys.modules
        with patch.dict(sys.modules, {"winreg": mock_winreg}):
            result = self.command.execute()
            
        assert result["success"] is True
        assert result["os"] == "Windows"
        assert result["total_startup_programs"] == 5  # 3 Registry keys + 2 Startup Folders
        
        # Verify details
        items = result["startup_programs"]
        reg_item = [i for i in items if i["type"] == "registry"][0]
        assert reg_item["name"] == "OneDrive"
        assert "OneDrive.exe" in reg_item["command"]
        
        dir_item = [i for i in items if i["type"] == "directory"][0]
        assert dir_item["name"] == "shortcut.lnk"
        
    @patch("platform.system")
    @patch("os.path.exists")
    @patch("os.path.isdir")
    @patch("os.path.isfile")
    @patch("os.listdir")
    @patch("builtins.open")
    def test_unix_autostart_programs(self, mock_open, mock_listdir, mock_isfile, mock_isdir, mock_exists, mock_system):
        """Test autostart parsing on Linux/Unix systems including .desktop file scanning"""
        mock_system.return_value = "Linux"
        mock_isdir.return_value = True
        mock_isfile.return_value = True
        
        # Directories exist
        def side_effect_exists(path):
            return "autostart" in path
        mock_exists.side_effect = side_effect_exists
        
        mock_listdir.return_value = ["app.desktop"]
        
        # Mock file read for .desktop parser
        mock_file = MagicMock()
        mock_file.__enter__.return_value = [
            "Name=My App",
            "Exec=my-app --run"
        ]
        mock_open.return_value = mock_file
        
        with patch.dict(os.environ, {"HOME": "/home/user"}):
            result = self.command.execute()
        
        assert result["success"] is True
        assert result["os"] == "Linux"
        # 2 locations scanned (User autostart + System autostart), both have app.desktop
        assert result["total_startup_programs"] == 2
        
        item = result["startup_programs"][0]
        assert item["name"] == "My App"
        assert item["command"] == "my-app --run"
        assert item["type"] == "desktop_file"
