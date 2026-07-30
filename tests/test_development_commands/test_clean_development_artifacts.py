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
        assert result_dry["status"] == "preview"
        assert result_dry["total_bytes_identified"] == 750
        assert result_dry["total_bytes_saved"] == 0
        
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
        assert result_clean["total_bytes_identified"] == 750
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
