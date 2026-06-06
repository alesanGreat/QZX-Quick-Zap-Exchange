#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the CheckSystemPath command
"""

import os
import platform
from unittest.mock import patch
from qzx.commands.system.check_system_path import CheckSystemPathCommand

class TestCheckSystemPathCommand:
    """
    Tests for the CheckSystemPath command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = CheckSystemPathCommand()
        
    def test_empty_path_env(self):
        """Test with empty or unset PATH environment variable"""
        with patch.dict(os.environ, {"PATH": ""}):
            result = self.command.execute()
            assert result["success"] is False
            assert "empty" in result["error"]
            
    def test_path_health_analysis(self, tmp_path):
        """Test analysis classification of valid, broken, and duplicate entries in PATH"""
        # Create valid directories
        dir1 = tmp_path / "valid1"
        dir1.mkdir()
        dir2 = tmp_path / "valid2"
        dir2.mkdir()
        
        # Nonexistent directories (broken)
        broken1 = tmp_path / "broken1"
        broken2 = tmp_path / "broken2"
        
        # Create a file to trigger "exists but is file" case
        some_file = tmp_path / "some_file"
        some_file.touch()
        
        # Assemble fake PATH environment
        is_windows = platform.system().lower() == "windows"
        path_sep = ";" if is_windows else ":"
        
        # Layout: dir1, duplicate dir1, broken1, dir2, some_file (broken), duplicate dir2
        fake_path = path_sep.join([
            str(dir1),
            str(dir1),
            str(broken1),
            str(dir2),
            str(some_file),
            str(dir2)
        ])
        
        with patch.dict(os.environ, {"PATH": fake_path}):
            result = self.command.execute()
            
        assert result["success"] is True
        summary = result["path_summary"]
        
        # Valid dirs: dir1, dir2 (count = 2)
        assert summary["valid_count"] == 2
        # Duplicates: duplicate dir1, duplicate dir2 (count = 2)
        assert summary["duplicate_count"] == 2
        # Broken: broken1, some_file (count = 2)
        assert summary["broken_count"] == 2
        assert summary["total_entries"] == 6
        
        # Verify specific reasons
        broken_paths = {b["raw_path"]: b for b in result["broken_paths"]}
        assert str(broken1) in broken_paths
        assert "does not exist" in broken_paths[str(broken1)]["reason"]
        assert str(some_file) in broken_paths
        assert "is a file" in broken_paths[str(some_file)]["reason"]
        
    def test_binary_resolution_search(self, tmp_path):
        """Test locating binary executables on the PATH in order of precedence"""
        is_windows = platform.system().lower() == "windows"
        path_sep = ";" if is_windows else ":"
        
        # Create two valid directories
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        dir2 = tmp_path / "dir2"
        dir2.mkdir()
        
        # Place test binary executable in both folders (shadowing scenario)
        ext = ".exe" if is_windows else ""
        bin_name = "test_run"
        file_name = bin_name + ext
        
        bin1 = dir1 / file_name
        bin1.touch()
        
        bin2 = dir2 / file_name
        bin2.touch()
        
        fake_path = path_sep.join([str(dir1), str(dir2)])
        
        with patch.dict(os.environ, {"PATH": fake_path}):
            result = self.command.execute(binary_name=bin_name)
            
        assert result["success"] is True
        assert result["binary_searched"] == bin_name
        
        matches = result["binary_matches"]
        # Both locations should be found
        assert len(matches) == 2
        
        # Precedence check: first path in PATH resolves first
        assert matches[0]["full_path"] == os.path.normpath(str(bin1))
        assert matches[1]["full_path"] == os.path.normpath(str(bin2))
        
        # Check output contains choices logs
        assert "First choice" in result["message"]
        assert "Shadowed" in result["message"]
        
    def test_binary_not_found(self, tmp_path):
        """Test search when binary is not present in PATH"""
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        
        with patch.dict(os.environ, {"PATH": str(dir1)}):
            result = self.command.execute(binary_name="nonexistent_binary_abc")
            
        assert result["success"] is True
        assert len(result["binary_matches"]) == 0
        assert "No executables named" in result["message"]
