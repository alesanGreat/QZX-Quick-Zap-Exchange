#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Behavioral tests for the canonical projectLanguages command."""

from qzx.commands.development.project_languages import ProjectLanguagesCommand
from qzx.core.command_loader import CommandLoader


class TestProjectLanguagesCommand:
    def setup_method(self):
        self.command = ProjectLanguagesCommand()

    def test_nonexistent_directory(self, tmp_path):
        result = self.command.execute(str(tmp_path / "missing"))

        assert result["success"] is False
        assert result["error_code"] == "path_not_found"
        assert "does not exist" in result["error"]

    def test_empty_directory(self, tmp_path):
        result = self.command.execute(str(tmp_path))

        assert result["success"] is True
        assert result["scan_complete"] is True
        assert result["total_files"] == 0
        assert result["languages"] == []
        assert result["supporting_formats"] == []

    def test_reports_php_python_and_css_without_dropping_css(self, tmp_path):
        for index in range(90):
            (tmp_path / f"page_{index}.php").write_text(
                "<?php echo 'QZX';\n",
                encoding="utf-8",
            )
        for index in range(5):
            (tmp_path / f"tool_{index}.py").write_text(
                "print('QZX')\n",
                encoding="utf-8",
            )
        for index in range(5):
            (tmp_path / f"style_{index}.css").write_text(
                ".qzx { color: green; }\n",
                encoding="utf-8",
            )

        result = self.command.execute(str(tmp_path))
        composition = {
            entry["language"]: entry["composition_percentage"]
            for entry in result["languages"]
        }

        assert result["success"] is True
        assert result["composition_basis"] == "source_code_lines"
        assert result["total_files"] == 100
        assert composition == {
            "PHP": 90.0,
            "Python": 5.0,
            "CSS": 5.0,
        }
        assert result["languages_found"] == {
            "PHP": 90,
            "Python": 5,
            "CSS": 5,
        }

    def test_respects_gitignore_and_builtin_dependency_directories(self, tmp_path):
        (tmp_path / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
        (tmp_path / "kept.py").write_text("print('kept')\n", encoding="utf-8")
        (tmp_path / "ignored.py").write_text("print('ignored')\n", encoding="utf-8")
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "dependency.js").write_text(
            "console.log('dependency');\n",
            encoding="utf-8",
        )

        result = self.command.execute(str(tmp_path))

        assert result["languages_found"] == {"Python": 1}
        assert result["summary"]["ignored_files"] == 1
        assert result["summary"]["ignored_directories"] == 1
        assert result["exclusions"]["respected_ignore_files"] == [".gitignore"]

    def test_nested_gitignore_can_reinclude_a_file(self, tmp_path):
        source_dir = tmp_path / "src"
        source_dir.mkdir()
        (source_dir / ".gitignore").write_text(
            "*.py\n!keep.py\n",
            encoding="utf-8",
        )
        (source_dir / "drop.py").write_text("print('drop')\n", encoding="utf-8")
        (source_dir / "keep.py").write_text("print('keep')\n", encoding="utf-8")

        result = self.command.execute(str(tmp_path))

        assert result["languages_found"] == {"Python": 1}
        assert result["summary"]["ignored_files"] == 1
        assert result["languages"][0]["example_files"] == ["src/keep.py"]

    def test_reports_unknown_generated_binary_and_supporting_files(self, tmp_path):
        (tmp_path / "README.md").write_text("# QZX\n", encoding="utf-8")
        (tmp_path / "mystery.qzxunknown").write_text("QZX\n", encoding="utf-8")
        (tmp_path / "generated.js").write_text(
            "// @generated - do not edit\nconsole.log('generated');\n",
            encoding="utf-8",
        )
        (tmp_path / "binary.py").write_bytes(b"\x00\x01\x02")

        result = self.command.execute(str(tmp_path))

        assert result["success"] is True
        assert result["summary"]["generated_files"] == 1
        assert result["summary"]["binary_files"] == 1
        assert result["unclassified"]["file_count"] == 1
        assert result["unclassified"]["extensions"] == [
            {"extension": ".qzxunknown", "file_count": 1}
        ]
        assert any(
            entry["language"] == "Markdown" and entry["kind"] == "prose"
            for entry in result["supporting_formats"]
        )

    def test_counts_all_scan_errors_while_bounding_reported_details(self, tmp_path):
        for index in range(25):
            directory = tmp_path / f"source-{index}"
            directory.mkdir()
            (directory / ".gitignore").write_bytes(b"\xff")

        result = self.command.execute(str(tmp_path))

        assert result["success"] is True
        assert result["scan_complete"] is False
        assert result["summary"]["scan_error_count"] == 25
        assert len(result["scan_errors"]) == self.command.MAX_REPORTED_ERRORS
        assert result["scan_errors_truncated"] is True
        assert "25 access or read errors" in result["message"]

    def test_retired_alias_is_not_available(self):
        loader = CommandLoader()

        canonical = loader.get_command("projectLanguages")
        retired_alias = loader.get_command("auditLanguages")
        retired_duplicate = loader.get_command("getProgrammingLanguageStats")

        assert canonical is not None
        assert retired_alias is None
        assert retired_duplicate is None
        assert canonical.name == "projectLanguages"
