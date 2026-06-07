#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the formatCode command
"""

import os
from qzx.commands.development.format_code import FormatCodeCommand


class TestFormatCodeCommand:
    """
    Tests for the FormatCodeCommand class
    """

    def setup_method(self):
        """Setup for each test"""
        self.command = FormatCodeCommand()

    def test_nonexistent_path(self):
        """Test with a path that does not exist"""
        result = self.command.execute("non_existent_dir_abc_123")
        assert result["success"] is False
        assert "does not exist" in result["error"]

    def test_unsupported_language(self):
        """Test with an unsupported language override"""
        result = self.command.execute(".", language="cobol")
        assert result["success"] is False
        assert "Unsupported language" in result["error"]

    def test_unsupported_file_extension(self, tmp_path):
        """Test with a file that has an unsupported extension"""
        file_path = tmp_path / "notes.txt"
        file_path.write_text("hello world")
        result = self.command.execute(str(file_path))
        assert result["success"] is False
        assert "Unsupported file type" in result["error"]

    def test_language_mismatch(self, tmp_path):
        """Test when requested language doesn't match file extension"""
        file_path = tmp_path / "script.py"
        file_path.write_text("x=1\n")
        result = self.command.execute(str(file_path), language="rust")
        assert result["success"] is False
        assert "Language mismatch" in result["error"]

    def test_no_supported_files_in_directory(self, tmp_path):
        """Test with a directory containing no supported files"""
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "data.json").write_text('{"a": 1}')
        result = self.command.execute(str(tmp_path))
        assert result["success"] is True
        assert result["total_files"] == 0
        assert "No supported source files" in result["message"]

    def test_detect_python_file(self, tmp_path):
        """Test formatting a single Python file is attempted"""
        file_path = tmp_path / "script.py"
        file_path.write_text("x=1\n")
        result = self.command.execute(str(file_path))
        assert result["success"] is True
        assert result["total_files"] == 1
        # The file should be recognized as Python
        if result["formatted_count"] == 0 and result["failed_count"] == 1:
            # black may not be installed; that's an acceptable environment gap
            assert result["failed"][0]["language"] == "python"
        else:
            assert result["formatted_count"] == 1

    def test_detect_multiple_languages_in_directory(self, tmp_path):
        """Test collecting files of multiple languages in a directory"""
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.js").write_text("const x = 1;\n")
        (tmp_path / "c.rs").write_text("fn main() {}\n")
        (tmp_path / "d.txt").write_text("ignore me")
        result = self.command.execute(str(tmp_path))
        assert result["success"] is True
        assert result["total_files"] == 3
        languages = set(item["language"] for item in result["formatted"] + result["failed"])
        assert "python" in languages
        assert "javascript" in languages
        assert "rust" in languages

    def test_dry_run_python_file(self, tmp_path):
        """Test dry-run on a Python file"""
        file_path = tmp_path / "script.py"
        file_path.write_text("x = 1\n")
        result = self.command.execute(str(file_path), dry_run="true")
        assert result["success"] is True
        assert result["total_files"] == 1
        assert result["dry_run"] is True

    def test_filter_by_language_in_directory(self, tmp_path):
        """Test filtering only Python files when language is forced"""
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.js").write_text("const x = 1;\n")
        (tmp_path / "c.rs").write_text("fn main() {}\n")
        result = self.command.execute(str(tmp_path), language="python")
        assert result["success"] is True
        assert result["total_files"] == 1
        all_items = result["formatted"] + result["failed"]
        assert all_items[0]["language"] == "python"
