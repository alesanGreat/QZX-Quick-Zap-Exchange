#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the CompressZip command
"""

import os
import zipfile
from qzx.commands.file.compress_zip import CompressZipCommand

class TestCompressZipCommand:
    """
    Tests for the CompressZip command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = CompressZipCommand()
        
    def test_missing_parameters(self):
        """Test calling with missing parameters"""
        result = self.command.execute("", "")
        assert result["success"] is False
        assert "required" in result["error"]
        
    def test_nonexistent_source(self):
        """Test compressing a nonexistent source path"""
        result = self.command.execute("archive.zip", "non_existent_folder_abc")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_compress_directory(self, tmp_path):
        """Test compressing a directory recursively with exclusions"""
        # Create structure:
        # source/
        #   file1.txt (100 bytes)
        #   sub/
        #     file2.txt (200 bytes)
        #   .git/ (should be ignored)
        #     config
        
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        with open(source_dir / "file1.txt", "w") as f:
            f.write("A" * 100)
            
        sub_dir = source_dir / "sub"
        sub_dir.mkdir()
        with open(sub_dir / "file2.txt", "w") as f:
            f.write("B" * 200)
            
        git_dir = source_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").touch()
        
        zip_file = tmp_path / "output.zip"
        
        result = self.command.execute(str(zip_file), str(source_dir))
        assert result["success"] is True
        assert zip_file.exists()
        assert result["files_archived"] == 2
        assert result["original_bytes"] == 300
        
        # Verify ZIP contents
        with zipfile.ZipFile(zip_file, "r") as z:
            namelist = z.namelist()
            assert "file1.txt" in namelist
            # Windows/Posix paths normalization inside ZIP uses forward slash /
            assert "sub/file2.txt" in namelist
            assert ".git/config" not in namelist
            
    def test_compress_single_file(self, tmp_path):
        """Test compressing a single file directly"""
        source_file = tmp_path / "single.txt"
        with open(source_file, "w") as f:
            f.write("A" * 50)
            
        zip_file = tmp_path / "single.zip"
        
        result = self.command.execute(str(zip_file), str(source_file))
        assert result["success"] is True
        assert zip_file.exists()
        assert result["files_archived"] == 1
        assert result["original_bytes"] == 50
        
        with zipfile.ZipFile(zip_file, "r") as z:
            assert "single.txt" in z.namelist()
            assert z.read("single.txt") == b"A" * 50

    def test_existing_archive_is_preserved_without_overwrite(self, tmp_path):
        source_file = tmp_path / "source.txt"
        zip_file = tmp_path / "existing.zip"
        source_file.write_text("new", encoding="utf-8")
        zip_file.write_bytes(b"original archive bytes")

        result = self.command.execute(str(zip_file), str(source_file))

        assert result["success"] is False
        assert result["error_code"] == "destination_exists"
        assert zip_file.read_bytes() == b"original archive bytes"

    def test_source_cannot_be_its_own_destination(self, tmp_path):
        source_file = tmp_path / "same.zip"
        source_file.write_bytes(b"keep")

        result = self.command.execute(
            str(source_file),
            str(source_file),
            overwrite=True,
        )

        assert result["success"] is False
        assert result["error_code"] == "source_equals_destination"
        assert source_file.read_bytes() == b"keep"

    def test_public_overwrite_backs_up_existing_archive(
        self,
        tmp_path,
        monkeypatch,
    ):
        source_file = tmp_path / "source.txt"
        zip_file = tmp_path / "existing.zip"
        backups = tmp_path / "backups"
        source_file.write_text("new archive content", encoding="utf-8")
        zip_file.write_bytes(b"original archive bytes")
        monkeypatch.setenv("QZX_BACKUPS_PATH", str(backups))

        result = self.command.invoke(
            [str(zip_file), str(source_file), "--overwrite"]
        )

        assert result["success"] is True
        assert result["meta"]["safety_backup"]["status"] == "created"
        with zipfile.ZipFile(zip_file) as archive:
            assert archive.read("source.txt") == b"new archive content"
        with zipfile.ZipFile(
            result["meta"]["safety_backup"]["path"]
        ) as backup:
            assert backup.read("existing.zip") == b"original archive bytes"
