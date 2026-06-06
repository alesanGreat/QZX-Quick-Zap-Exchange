#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the WonderIfFileEmpty command
"""

import os
from qzx.commands.file.is_file_empty import WonderIfFileEmptyCommand

class TestWonderIfFileEmptyCommand:
    """
    Tests for the WonderIfFileEmpty command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = WonderIfFileEmptyCommand()
        
    def test_format_bytes(self):
        """Test formatting bytes to human-readable size"""
        assert self.command._format_bytes(500) == "500.00 B"
        assert self.command._format_bytes(1024) == "1.00 KB"
        assert self.command._format_bytes(1024 * 1024) == "1.00 MB"
        
    def test_nonexistent_file(self):
        """Test with a file path that does not exist"""
        result = self.command.execute("non_existent_file_xyz.txt")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_directory_path(self, tmp_path):
        """Test with a directory instead of a file"""
        dir_path = tmp_path / "test_dir"
        dir_path.mkdir()
        
        result = self.command.execute(str(dir_path))
        assert result["success"] is False
        assert "is not a file" in result["error"]
        
    def test_completely_empty_file(self, tmp_path):
        """Test with a completely empty file (0 bytes)"""
        file_path = tmp_path / "empty.txt"
        file_path.touch()
        
        # Test without considering whitespace
        result = self.command.execute(str(file_path), consider_whitespace=False)
        assert result["success"] is True
        assert result["is_empty"] is True
        assert result["file_size"] == 0
        assert "completely empty" in result["message"]
        
        # Test considering whitespace
        result = self.command.execute(str(file_path), consider_whitespace=True)
        assert result["success"] is True
        assert result["is_empty"] is True
        assert result["file_size"] == 0
        assert "completely empty" in result["message"]
        
    def test_whitespace_only_file(self, tmp_path):
        """Test with a file containing only whitespace"""
        file_path = tmp_path / "whitespace.txt"
        file_path.write_text("   \n  \t  \n", encoding="utf-8")
        
        # Test without considering whitespace (should not be empty by size)
        result = self.command.execute(str(file_path), consider_whitespace=False)
        assert result["success"] is True
        assert result["is_empty"] is False
        assert result["file_size"] > 0
        assert "is not empty" in result["message"]
        
        # Test considering whitespace (should be considered empty)
        result = self.command.execute(str(file_path), consider_whitespace=True)
        assert result["success"] is True
        assert result["is_empty"] is True
        assert result["is_whitespace_only"] is True
        assert "contains only whitespace" in result["message"]
        
    def test_file_with_content(self, tmp_path):
        """Test with a file that has actual text content"""
        file_path = tmp_path / "content.txt"
        file_path.write_text("Hello World", encoding="utf-8")
        
        # Test without considering whitespace
        result = self.command.execute(str(file_path), consider_whitespace=False)
        assert result["success"] is True
        assert result["is_empty"] is False
        assert result["file_size"] == 11
        assert "is not empty" in result["message"]
        
        # Test considering whitespace
        result = self.command.execute(str(file_path), consider_whitespace=True)
        assert result["success"] is True
        assert result["is_empty"] is False
        assert result["is_whitespace_only"] is False
        assert "is not empty" in result["message"]
        
    def test_boolean_string_parsing(self, tmp_path):
        """Test that string representations of boolean parameters are correctly parsed"""
        file_path = tmp_path / "whitespace.txt"
        file_path.write_text("   \n", encoding="utf-8")
        
        # Test with string 'true'
        result = self.command.execute(str(file_path), consider_whitespace="true")
        assert result["success"] is True
        assert result["is_empty"] is True
        
        # Test with string 'yes'
        result = self.command.execute(str(file_path), consider_whitespace="yes")
        assert result["success"] is True
        assert result["is_empty"] is True
        
        # Test with string 'false'
        result = self.command.execute(str(file_path), consider_whitespace="false")
        assert result["success"] is True
        assert result["is_empty"] is False
