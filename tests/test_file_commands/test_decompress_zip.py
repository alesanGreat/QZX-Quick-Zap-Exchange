#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the DecompressZip command
"""

import os
import zipfile
from qzx.commands.file.decompress_zip import DecompressZipCommand

class TestDecompressZipCommand:
    """
    Tests for the DecompressZip command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = DecompressZipCommand()
        
    def test_missing_zip_path(self):
        """Test calling with missing ZIP path"""
        result = self.command.execute("")
        assert result["success"] is False
        assert "required" in result["error"]
        
    def test_nonexistent_zip(self):
        """Test decompressing a nonexistent file"""
        result = self.command.execute("non_existent_archive.zip")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_invalid_zip(self, tmp_path):
        """Test with an invalid zip file"""
        bad_zip = tmp_path / "not_a_zip.zip"
        bad_zip.write_text("just text contents")
        
        result = self.command.execute(str(bad_zip))
        assert result["success"] is False
        assert "not a valid ZIP archive" in result["error"]
        
    def test_decompress_success_and_security(self, tmp_path):
        """Test successful decompression and check Zip Slip traversal protection"""
        # Create a mock zip archive
        zip_file = tmp_path / "test.zip"
        target_dir = tmp_path / "extracted"
        
        with zipfile.ZipFile(zip_file, "w") as z:
            z.writestr("file1.txt", "A" * 100)
            z.writestr("sub/file2.txt", "B" * 200)
            # Create a path that attempts directory traversal (Zip Slip vulnerability test)
            # We construct a ZipInfo manually to write the traversal path
            info = zipfile.ZipInfo("../traversal_target.txt")
            z.writestr(info, "MALICIOUS")
            
        result = self.command.execute(str(zip_file), str(target_dir))
        
        assert result["success"] is True
        assert target_dir.exists()
        assert result["files_extracted"] == 2
        assert result["total_bytes_extracted"] == 300
        
        # Verify correct files are extracted
        assert (target_dir / "file1.txt").exists()
        assert (target_dir / "sub" / "file2.txt").exists()
        
        # Verify the traversal file was SKIPPED and not written outside the target directory
        assert not (tmp_path / "traversal_target.txt").exists()
        assert "../traversal_target.txt" in result["skipped_traversals"]
        assert len(result["skipped_traversals"]) == 1
        assert "traversal attempt" in result["message"]
