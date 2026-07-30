#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the formatCode command
"""

import shutil
import zipfile
from qzx.commands.development.format_code import FormatCodeCommand


class DeterministicFormatCodeCommand(FormatCodeCommand):
    """Use a deterministic local formatter boundary for the safety contract."""

    def _is_tool_available(self, _tool):
        return True

    def _run_formatter(self, _args, file_path, dry_run):
        if not dry_run:
            with open(file_path, "w", encoding="utf-8") as source_file:
                source_file.write("x = 1\n")
        return {"ok": True, "would_change": True}


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

    def test_python_formatter_boundary_reports_the_real_result(self, tmp_path):
        """Never turn an unavailable real formatter into a false success."""
        file_path = tmp_path / "script.py"
        original = "def greet( name:str)->str:\n return 'hello '+name\n"
        file_path.write_text(original)

        result = self.command.execute(str(file_path))

        assert result["success"] is True
        assert result["total_files"] == 1
        if shutil.which("black"):
            assert result["all_succeeded"] is True
            assert result["formatted_count"] == 1
            assert result["failed_count"] == 0
            assert result["unavailable_tools"] == []
            assert file_path.read_text() != original
        else:
            assert result["all_succeeded"] is False
            assert result["formatted_count"] == 0
            assert result["failed_count"] == 1
            assert result["unavailable_tools"] == ["black"]
            assert result["failed"][0]["language"] == "python"
            assert "not installed or not on PATH" in (
                result["failed"][0]["reason"]
            )
            assert file_path.read_text() == original

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

    def test_public_format_backs_up_target_before_writing(
        self,
        tmp_path,
        monkeypatch,
    ):
        file_path = tmp_path / "script.py"
        backups = tmp_path / "backups"
        original = b"x=1\n"
        file_path.write_bytes(original)
        monkeypatch.setenv("QZX_BACKUPS_PATH", str(backups))

        result = DeterministicFormatCodeCommand().invoke([str(file_path)])

        assert result["success"] is True
        assert file_path.read_text(encoding="utf-8") == "x = 1\n"
        backup_path = result["meta"]["safety_backup"]["path"]
        with zipfile.ZipFile(backup_path) as archive:
            assert archive.read("script.py") == original

    def test_public_dry_run_does_not_create_backup(
        self,
        tmp_path,
        monkeypatch,
    ):
        file_path = tmp_path / "script.py"
        backups = tmp_path / "backups"
        original = "x=1\n"
        file_path.write_text(original, encoding="utf-8")
        monkeypatch.setenv("QZX_BACKUPS_PATH", str(backups))

        result = DeterministicFormatCodeCommand().invoke(
            [str(file_path), "--dry-run"]
        )

        assert result["success"] is True
        assert file_path.read_text(encoding="utf-8") == original
        assert "safety_backup" not in result["meta"]
        assert not backups.exists()
