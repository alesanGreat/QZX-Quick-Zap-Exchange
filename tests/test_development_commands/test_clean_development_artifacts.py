#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the CleanDevelopmentArtifacts command
"""

import shutil
from pathlib import Path

from qzx.commands.development.clean_development_artifacts import (
    CleanDevelopmentArtifactsCommand,
)

def _write_sized_file(path, marker, size):
    path.write_text(marker * size, encoding="utf-8")


def _build_cleanup_tree(root):
    (root / "package.json").touch()
    node_modules = root / "node_modules"
    node_modules.mkdir()
    _write_sized_file(node_modules / "file1.txt", "A", 100)

    dist = root / "dist"
    dist.mkdir()
    _write_sized_file(dist / "file2.txt", "B", 200)

    src = root / "src"
    src.mkdir()
    (src / "app.py").touch()
    pycache = src / "__pycache__"
    pycache.mkdir()
    _write_sized_file(pycache / "cache.pyc", "C", 50)

    target_no_toml = root / "target"
    target_no_toml.mkdir()
    _write_sized_file(target_no_toml / "binary", "D", 300)

    rust_app = root / "rust_app"
    rust_app.mkdir()
    (rust_app / "Cargo.toml").touch()
    target_with_toml = rust_app / "target"
    target_with_toml.mkdir()
    _write_sized_file(target_with_toml / "file.o", "E", 400)

    custom_folder = root / "custom_folder"
    custom_folder.mkdir()
    (custom_folder / "other.txt").touch()
    return {
        "node_modules": node_modules,
        "dist": dist,
        "pycache": pycache,
        "target_no_toml": target_no_toml,
        "target_with_toml": target_with_toml,
        "custom_folder": custom_folder,
    }


def _assert_preview_contract(result, paths):
    assert result["success"] is True
    assert result["dry_run"] is True
    assert result["total_folders_found"] == 4
    assert result["status"] == "preview"
    assert result["total_bytes_identified"] == 750
    assert result["total_bytes_saved"] == 0
    assert paths["node_modules"].exists()
    assert paths["dist"].exists()
    assert paths["pycache"].exists()
    assert paths["target_no_toml"].exists()
    assert paths["target_with_toml"].exists()


def _assert_cleanup_contract(result, paths, root):
    assert result["success"] is True
    assert result["dry_run"] is False
    assert result["total_folders_found"] == 4
    assert result["total_bytes_identified"] == 750
    assert result["total_bytes_saved"] == 750
    assert len(result["deleted_folders"]) == 4
    assert not paths["node_modules"].exists()
    assert not paths["dist"].exists()
    assert not paths["pycache"].exists()
    assert not paths["target_with_toml"].exists()
    assert paths["target_no_toml"].exists()
    assert paths["custom_folder"].exists()
    assert (root / "package.json").exists()
    assert (root / "src" / "app.py").exists()
    assert (root / "rust_app" / "Cargo.toml").exists()


class TestCleanDevelopmentArtifactsCommand:
    """
    Tests for the CleanDevelopmentArtifacts command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = CleanDevelopmentArtifactsCommand()
        
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
        paths = _build_cleanup_tree(tmp_path)

        preview = self.command.execute(str(tmp_path), dry_run="true")
        _assert_preview_contract(preview, paths)

        cleaned = self.command.execute(str(tmp_path), dry_run="false")
        _assert_cleanup_contract(cleaned, paths, tmp_path)

    def test_invalid_depth_fails_instead_of_silently_using_default(self, tmp_path):
        """Invalid depth must not select an operation different from the request."""
        result = self.command.execute(str(tmp_path), max_depth="deep")

        assert result["success"] is False
        assert result["error_code"] == "invalid_max_depth"

        zero = self.command.execute(str(tmp_path), max_depth=0)
        assert zero["success"] is False
        assert zero["error_code"] == "invalid_max_depth"

    def test_partial_deletion_is_a_structured_failure(
        self,
        tmp_path,
    ):
        """A failed deletion cannot be reported as a globally successful clean."""
        first = tmp_path / "__pycache__"
        second = tmp_path / "node_modules"
        first.mkdir()
        second.mkdir()
        (first / "cache.pyc").write_bytes(b"a")
        (second / "dependency.js").write_bytes(b"bb")
        class SelectiveFailureCommand(CleanDevelopmentArtifactsCommand):
            @staticmethod
            def _remove_directory(path):
                if Path(path).name == "node_modules":
                    raise PermissionError("locked")
                shutil.rmtree(path)

        result = SelectiveFailureCommand().execute(
            str(tmp_path),
            dry_run=False,
        )

        assert result["success"] is False
        assert result["status"] == "partial_failure"
        assert result["total_bytes_identified"] == 3
        assert result["total_bytes_saved"] == 1
        assert result["deleted_folders"] == [str(first)]
        assert result["deletion_failures"] == [{
            "path": str(second),
            "error_type": "PermissionError",
            "error": "locked",
        }]
        assert not first.exists()
        assert second.exists()

    def test_public_preview_does_not_create_backup(self, tmp_path, monkeypatch):
        """The safe default remains read-only and avoids unnecessary archives."""
        monkeypatch.setenv("QZX_BACKUPS_PATH", str(tmp_path / "backups"))
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "cache.pyc").write_bytes(b"cache")

        result = self.command.invoke([str(tmp_path)])

        assert result["success"] is True
        assert result["status"] == "preview"
        assert "safety_backup" not in result["meta"]
        assert cache.exists()

    def test_public_clean_creates_backup_before_deletion(
        self,
        tmp_path,
        monkeypatch,
    ):
        """A live clean must archive the selected project before mutation."""
        backups = tmp_path / "backups"
        project = tmp_path / "project"
        cache = project / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "cache.pyc").write_bytes(b"cache")
        monkeypatch.setenv("QZX_BACKUPS_PATH", str(backups))

        result = self.command.invoke([
            str(project),
            "--dry-run",
            "false",
        ])

        assert result["success"] is True
        assert not cache.exists()
        backup = result["meta"]["safety_backup"]
        assert backup["status"] == "created"
        assert backup["source_path"] == str(project.resolve())
        assert Path(backup["path"]).exists()

    def test_filesystem_root_is_refused_for_live_clean(self):
        """A root clean needs the conspicuous explicit bypass."""
        root = Path.cwd().anchor

        result = self.command.validate_safety_backup_target(
            root,
            {"scan_path": root, "dry_run": False},
        )

        assert result["success"] is False
        assert result["error_code"] == "filesystem_root_refused"
