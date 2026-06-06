#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the FindBrokenSymlinks command
"""

import os
from unittest.mock import patch, MagicMock
from qzx.commands.file.find_broken_symlinks import FindBrokenSymlinksCommand

class TestFindBrokenSymlinksCommand:
    """
    Tests for the FindBrokenSymlinks command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = FindBrokenSymlinksCommand()
        
    def test_nonexistent_directory(self):
        """Test with a directory that does not exist"""
        result = self.command.execute("non_existent_folder_abc")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_file_instead_of_directory(self, tmp_path):
        """Test with a file path instead of a directory"""
        file_path = tmp_path / "test.txt"
        file_path.touch()
        
        result = self.command.execute(str(file_path))
        assert result["success"] is False
        assert "is not a directory" in result["error"]
        
    @patch("os.walk")
    @patch("os.path.islink")
    @patch("os.path.exists")
    @patch("os.path.isdir")
    @patch("os.readlink")
    def test_broken_symlinks_scanning(self, mock_readlink, mock_isdir, mock_exists, mock_islink, mock_walk):
        """Test scanning and identifying broken symlinks with mocked file layouts"""
        mock_isdir.return_value = True
        # Configure walk mock to return:
        # root/
        #   valid_link.txt
        #   broken_link.txt
        #   normal_file.txt
        root_dir = os.path.abspath("/mock_project")
        mock_walk.return_value = [
            (root_dir, ["subdir"], ["valid_link.txt", "broken_link.txt", "normal_file.txt"])
        ]
        
        # Determine path outputs
        valid_path = os.path.join(root_dir, "valid_link.txt")
        broken_path = os.path.join(root_dir, "broken_link.txt")
        normal_path = os.path.join(root_dir, "normal_file.txt")
        
        # Mock checks
        # islink returns: True for valid_link and broken_link, False for normal_file
        def side_effect_islink(path):
            return path in (valid_path, broken_path)
        mock_islink.side_effect = side_effect_islink
        
        # exists returns: True for valid_link and normal_file, False for broken_link (since it's broken)
        # Note: os.path.exists of the directory itself (/mock_project) is also called inside execute.
        # Let's handle it.
        def side_effect_exists(path):
            if path == root_dir:
                return True
            return path in (valid_path, normal_path)
        mock_exists.side_effect = side_effect_exists
        
        # readlink return
        mock_readlink.return_value = "/mock_project/missing_target.txt"
        
        result = self.command.execute(root_dir)
        
        assert result["success"] is True
        assert result["broken_symlinks_count"] == 1
        
        broken = result["broken_symlinks"][0]
        assert broken["path"] == broken_path
        assert broken["target"] == "/mock_project/missing_target.txt"
        assert "broken_link.txt" in result["message"]
