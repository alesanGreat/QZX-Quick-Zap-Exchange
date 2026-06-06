#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the CleanDevCaches command
"""

import os
import shutil
from qzx.commands.development.clean_dev_caches import CleanDevCachesCommand

class TestCleanDevCachesCommand:
    """
    Tests for the CleanDevCaches command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = CleanDevCachesCommand()
        
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
        
    def test_scan_and_cleanup(self, tmp_path):
        """Test scanning and cleaning up multiple cache folders"""
        # Create standard layout:
        # root/
        #   package.json
        #   node_modules/
        #     file1.txt (100 bytes)
        #   dist/
        #     file2.txt (200 bytes)
        #   src/
        #     __pycache__/
        #       cache.pyc (50 bytes)
        #     app.py
        #   target/  (Cargo target, but no Cargo.toml, should NOT be deleted)
        #     binary (300 bytes)
        #   rust_app/
        #     Cargo.toml
        #     target/ (Cargo target with Cargo.toml, SHOULD be deleted)
        #       file.o (400 bytes)
        #   custom_folder/
        #     other.txt
        
        # 1. Setup structure
        (tmp_path / "package.json").touch()
        
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        with open(node_modules / "file1.txt", "w") as f:
            f.write("A" * 100)
            
        dist = tmp_path / "dist"
        dist.mkdir()
        with open(dist / "file2.txt", "w") as f:
            f.write("B" * 200)
            
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").touch()
        
        pycache = src / "__pycache__"
        pycache.mkdir()
        with open(pycache / "cache.pyc", "w") as f:
            f.write("C" * 50)
            
        target_no_toml = tmp_path / "target"
        target_no_toml.mkdir()
        with open(target_no_toml / "binary", "w") as f:
            f.write("D" * 300)
            
        rust_app = tmp_path / "rust_app"
        rust_app.mkdir()
        (rust_app / "Cargo.toml").touch()
        
        target_with_toml = rust_app / "target"
        target_with_toml.mkdir()
        with open(target_with_toml / "file.o", "w") as f:
            f.write("E" * 400)
            
        custom_folder = tmp_path / "custom_folder"
        custom_folder.mkdir()
        (custom_folder / "other.txt").touch()
        
        # 2. Run Dry Run scan
        result_dry = self.command.execute(str(tmp_path), dry_run="true")
        assert result_dry["success"] is True
        assert result_dry["dry_run"] is True
        assert result_dry["total_folders_found"] == 4  # node_modules, dist, __pycache__, rust_app/target
        # Size details: 100 (node_modules) + 200 (dist) + 50 (__pycache__) + 400 (rust_app/target) = 750 bytes
        assert result_dry["total_bytes_saved"] == 750
        
        # Ensure files still exist
        assert node_modules.exists()
        assert dist.exists()
        assert pycache.exists()
        assert target_no_toml.exists()  # Kept (no Cargo.toml trigger)
        assert target_with_toml.exists()
        
        # 3. Run Clean operation
        result_clean = self.command.execute(str(tmp_path), dry_run="false")
        assert result_clean["success"] is True
        assert result_clean["dry_run"] is False
        assert result_clean["total_folders_found"] == 4
        assert result_clean["total_bytes_saved"] == 750
        assert len(result_clean["deleted_folders"]) == 4
        
        # Verify correct folders were deleted
        assert not node_modules.exists()
        assert not dist.exists()
        assert not pycache.exists()
        assert not target_with_toml.exists()
        
        # Verify safety boundaries: triggered targets and non-matching targets are preserved
        assert target_no_toml.exists()
        assert custom_folder.exists()
        assert (tmp_path / "package.json").exists()
        assert (tmp_path / "src" / "app.py").exists()
        assert (tmp_path / "rust_app" / "Cargo.toml").exists()
