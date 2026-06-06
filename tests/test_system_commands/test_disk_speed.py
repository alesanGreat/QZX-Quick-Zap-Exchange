#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the TestDiskSpeed command
"""

import os
from qzx.commands.system.test_disk_speed import TestDiskSpeedCommand

class TestDiskSpeedCommandSuite:
    """
    Tests for the TestDiskSpeed command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = TestDiskSpeedCommand()
        
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
        
    def test_speed_benchmark_success(self, tmp_path):
        """Test executing disk read/write speed test benchmark successfully"""
        # Run benchmark with a small 2MB file to keep tests fast
        result = self.command.execute(str(tmp_path), size_mb=2)
        
        assert result["success"] is True
        assert result["test_directory"] == os.path.abspath(str(tmp_path))
        assert result["test_file_size_mb"] == 2
        
        assert result["write_speed_mbs"] > 0
        assert result["read_speed_mbs"] > 0
        assert result["write_duration_seconds"] > 0
        assert result["read_duration_seconds"] > 0
        
        # Verify cleanup
        temp_file = tmp_path / "qzx_speedtest_temp.bin"
        assert not temp_file.exists()
        assert "Sequential Write" in result["message"]
