"""Tests for addPythonDocstrings safety and observable behavior."""

import ast
from pathlib import Path

from qzx.commands.development.add_python_docstrings import (
    AddPythonDocstringsCommand,
)


SOURCE_WITHOUT_DOCSTRINGS = """\
def greet(name: str) -> str:
    return f"Hello, {name}"
"""


class TestAddPythonDocstringsCommand:
    def setup_method(self):
        self.command = AddPythonDocstringsCommand()

    def test_default_is_preview_and_does_not_rewrite(self, tmp_path):
        source = tmp_path / "example.py"
        source.write_text(SOURCE_WITHOUT_DOCSTRINGS, encoding="utf-8")

        result = self.command.execute(str(source))

        assert result["success"] is True
        assert result["status"] == "preview"
        assert result["changes_detected"] is True
        assert result["changes_applied"] is False
        assert result["changes_made"] is False
        assert source.read_text(encoding="utf-8") == SOURCE_WITHOUT_DOCSTRINGS

    def test_public_live_mode_creates_backup_and_updates_atomically(
        self,
        tmp_path,
        monkeypatch,
    ):
        source = tmp_path / "example.py"
        source.write_text(SOURCE_WITHOUT_DOCSTRINGS, encoding="utf-8")
        backups = tmp_path / "backups"
        monkeypatch.setenv("QZX_BACKUPS_PATH", str(backups))

        result = self.command.invoke([
            str(source),
            "--dry-run",
            "false",
        ])

        assert result["success"] is True
        assert result["status"] == "updated"
        assert result["changes_detected"] is True
        assert result["changes_applied"] is True
        assert result["changes_made"] is True
        updated_source = source.read_text(encoding="utf-8")
        tree = ast.parse(updated_source)
        assert ast.get_docstring(tree.body[0]).startswith("greet")
        backup = result["meta"]["safety_backup"]
        assert backup["status"] == "created"
        assert backup["source_path"] == str(source.resolve())
        assert Path(backup["path"]).exists()
        assert not list(tmp_path.glob(".example.py.qzx-*.tmp"))

    def test_existing_complete_file_is_not_rewritten(self, tmp_path):
        source = tmp_path / "documented.py"
        original = 'def greet():\n    """Return a greeting."""\n    return "hi"\n'
        source.write_text(original, encoding="utf-8")

        result = self.command.execute(str(source), dry_run=False)

        assert result["success"] is True
        assert result["status"] == "unchanged"
        assert result["changes_detected"] is False
        assert result["changes_applied"] is False
        assert source.read_text(encoding="utf-8") == original

    def test_invalid_values_fail_closed(self, tmp_path):
        source = tmp_path / "example.py"
        source.write_text(SOURCE_WITHOUT_DOCSTRINGS, encoding="utf-8")

        overwrite = self.command.execute(str(source), overwrite="sometimes")
        dry_run = self.command.execute(str(source), dry_run="perhaps")
        style = self.command.execute(str(source), style="custom")

        assert overwrite["error_code"] == "invalid_overwrite"
        assert dry_run["error_code"] == "invalid_dry_run"
        assert style["error_code"] == "invalid_style"
        assert source.read_text(encoding="utf-8") == SOURCE_WITHOUT_DOCSTRINGS

    def test_syntax_error_is_structured_and_does_not_rewrite(self, tmp_path):
        source = tmp_path / "broken.py"
        original = "def broken(:\n"
        source.write_text(original, encoding="utf-8")

        result = self.command.execute(str(source), dry_run=False)

        assert result["success"] is False
        assert result["error_code"] == "invalid_python_syntax"
        assert result["details"]["line"] == 1
        assert source.read_text(encoding="utf-8") == original

    def test_crlf_and_terminal_newline_are_preserved(self, tmp_path):
        source = tmp_path / "windows.py"
        original = SOURCE_WITHOUT_DOCSTRINGS.replace("\n", "\r\n")
        source.write_bytes(original.encode("utf-8"))

        result = self.command.execute(str(source), dry_run=False)

        updated = source.read_bytes()
        assert result["success"] is True
        assert result["changes_applied"] is True
        assert b"\r\n" in updated
        assert updated.endswith(b"\r\n")
        assert b"\n" not in updated.replace(b"\r\n", b"")
