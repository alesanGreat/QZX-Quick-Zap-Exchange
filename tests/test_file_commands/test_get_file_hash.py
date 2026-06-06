#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the GetFileHash command
"""

import os
import hashlib
from qzx.commands.file.get_file_hash import GetFileHashCommand

class TestGetFileHashCommand:
    """
    Tests for the GetFileHash command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = GetFileHashCommand()
        
    def test_format_bytes(self):
        """Test formatting bytes to human-readable size"""
        assert self.command._format_bytes(500) == "500.00 B"
        assert self.command._format_bytes(1024) == "1.00 KB"
        
    def test_nonexistent_file(self):
        """Test with a file path that does not exist"""
        result = self.command.execute("non_existent_file_abc.txt")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_directory_path(self, tmp_path):
        """Test with a directory instead of a file"""
        dir_path = tmp_path / "test_dir"
        dir_path.mkdir()
        
        result = self.command.execute(str(dir_path))
        assert result["success"] is False
        assert "is not a file" in result["error"]
        
    def test_unsupported_algorithm(self, tmp_path):
        """Test using an unsupported hash algorithm"""
        file_path = tmp_path / "test.txt"
        file_path.touch()
        
        result = self.command.execute(str(file_path), algorithm="crc32")
        assert result["success"] is False
        assert "Unsupported hash algorithm" in result["error"]
        
    def test_calculate_hashes(self, tmp_path):
        """Test calculating standard hashes (SHA-256, SHA-1, MD5) on a file"""
        file_path = tmp_path / "test.txt"
        content = "QZX - Verbose is Gold"
        file_path.write_text(content, encoding="utf-8")
        
        # Calculate expected hashes
        expected_md5 = hashlib.md5(content.encode('utf-8')).hexdigest()
        expected_sha1 = hashlib.sha1(content.encode('utf-8')).hexdigest()
        expected_sha256 = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        # Test default (SHA-256)
        result = self.command.execute(str(file_path))
        assert result["success"] is True
        assert result["algorithm"] == "sha256"
        assert result["hash"] == expected_sha256
        assert result["file_size"] == len(content)
        
        # Test SHA-1
        result = self.command.execute(str(file_path), algorithm="sha1")
        assert result["success"] is True
        assert result["algorithm"] == "sha1"
        assert result["hash"] == expected_sha1
        
        # Test MD5
        result = self.command.execute(str(file_path), algorithm="md5")
        assert result["success"] is True
        assert result["algorithm"] == "md5"
        assert result["hash"] == expected_md5
