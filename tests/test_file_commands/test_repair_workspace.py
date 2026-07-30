#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the RepairWorkspace command
"""

import os
import shutil
import zipfile
from qzx.commands.file.repair_workspace import RepairWorkspaceCommand


class CollidingDigestRepairWorkspaceCommand(RepairWorkspaceCommand):
    """Deterministic boundary fake for the astronomically rare hash collision."""

    def _get_sha256(self, _filepath):
        return "collision"

class TestRepairWorkspaceCommand:
    """
    Tests for the RepairWorkspace command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = RepairWorkspaceCommand()
        
    def test_repair_workspace_dry_run(self, tmp_path):
        """Test dry run mode does not delete anything"""
        # Create mock directories/files
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        
        build_file = dist_dir / "app.js"
        build_file.write_text("console.log('build');")
        
        pyc_file = tmp_path / "helper.pyc"
        pyc_file.write_text("binary-pyc-cache")
        
        temp_file = tmp_path / "debug.log"
        temp_file.write_text("error log entry")
        
        # Run command in dry_run (default)
        result = self.command.execute(path=str(tmp_path), dry_run=True)
        assert result["success"] is True
        details = result["details"]
        assert details["dry_run_mode"] is True
        
        # Build category should have dist and pyc
        build_paths = [b["path"] for b in details["categories"]["build"]]
        assert "dist" in build_paths or "dist\\app.js" in build_paths or "helper.pyc" in build_paths
        
        # Temp category should have debug.log
        temp_paths = [t["path"] for t in details["categories"]["temp"]]
        assert "debug.log" in temp_paths
        
        # Verify files are NOT deleted
        assert os.path.exists(dist_dir)
        assert os.path.exists(pyc_file)
        assert os.path.exists(temp_file)
        
    def test_repair_workspace_apply(self, tmp_path):
        """Test apply mode deletes target directories and files"""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        
        build_file = dist_dir / "app.js"
        build_file.write_text("console.log('build');")
        
        pyc_file = tmp_path / "helper.pyc"
        pyc_file.write_text("binary-pyc-cache")
        
        temp_file = tmp_path / "debug.log"
        temp_file.write_text("error log entry")
        
        # Run command in apply mode (dry_run=False, apply=True)
        result = self.command.execute(path=str(tmp_path), dry_run=False, apply=True)
        assert result["success"] is True
        details = result["details"]
        assert details["dry_run_mode"] is False
        
        # Verify files are actually deleted
        assert not os.path.exists(dist_dir)
        assert not os.path.exists(pyc_file)
        assert not os.path.exists(temp_file)
        
    def test_repair_workspace_duplicates(self, tmp_path):
        """Test duplicate detection by content hash"""
        file1 = tmp_path / "file1.txt"
        file1.write_text("duplicate contents")
        
        file2 = tmp_path / "file2.txt"
        file2.write_text("duplicate contents")
        
        # Run command
        result = self.command.execute(path=str(tmp_path), dry_run=True, categories="duplicates")
        assert result["success"] is True
        details = result["details"]
        
        dups = details["categories"]["duplicates"]
        assert len(dups) >= 1
        dup_names = [d["file"] for d in dups]
        assert "file2.txt" in dup_names or "file1.txt" in dup_names

    def test_duplicate_digest_collision_does_not_propose_deletion(
        self,
        tmp_path,
    ):
        """Different bytes remain safe even if the candidate digest collides."""
        (tmp_path / "first.bin").write_bytes(b"A" * 1024)
        (tmp_path / "second.bin").write_bytes(b"B" * 1024)

        result = CollidingDigestRepairWorkspaceCommand().execute(
            path=str(tmp_path),
            dry_run=True,
            categories="duplicates",
        )

        assert result["success"] is True
        assert result["details"]["categories"]["duplicates"] == []

    def test_public_apply_creates_workspace_backup_before_mutation(
        self,
        monkeypatch,
        tmp_path,
    ):
        """The public invocation must archive the target before deleting files."""
        temp_file = tmp_path / "debug.log"
        temp_file.write_text("retain in backup", encoding="utf-8")
        backup_directory = tmp_path.parent / f"{tmp_path.name}-backups"
        monkeypatch.setenv("QZX_BACKUPS_PATH", str(backup_directory))

        result = self.command.invoke(
            [
                str(tmp_path),
                "--dry-run",
                "false",
                "--categories",
                "temp",
                "--apply",
            ]
        )

        assert result["success"] is True
        assert not temp_file.exists()
        backup = result["meta"]["safety_backup"]
        assert backup["status"] == "created"
        with zipfile.ZipFile(backup["path"]) as archive:
            backed_up_logs = [
                name for name in archive.namelist() if name.endswith("/debug.log")
            ]
            assert len(backed_up_logs) == 1
            assert archive.read(backed_up_logs[0]) == b"retain in backup"

    def test_repair_workspace_reorganizations(self, tmp_path):
        """Test reorganizations detection and execution including reference updates"""
        # Create mock file structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        
        # 1. .env outside root
        env_file = subdir / ".env"
        env_file.write_text("PORT=8000")
        
        # 2. Uppercase extension
        style_file = subdir / "style.CSS"
        style_file.write_text("body {}")
        
        # 3. Spaces in filename
        script_file = subdir / "my script.py"
        script_file.write_text("print('hello')")
        
        # 4. A file referencing the above files
        referrer_file = tmp_path / "referrer.py"
        referrer_file.write_text("import subdir.my script as script\nload_dotenv('subdir/.env')\nlink('subdir/style.CSS')")
        
        # Run dry run first
        result = self.command.execute(path=str(tmp_path), dry_run=True, categories="reorganizations")
        assert result["success"] is True
        details = result["details"]
        
        reorgs = details["categories"]["reorganizations"]
        assert len(reorgs) == 3
        
        types = [r["type"] for r in reorgs]
        assert "move" in types
        assert "rename" in types
        
        # Files should still be in original locations
        assert (subdir / ".env").exists()
        assert (subdir / "style.CSS").exists()
        assert (subdir / "my script.py").exists()
        
        # Run apply mode
        result_apply = self.command.execute(path=str(tmp_path), dry_run=False, apply=True, categories="reorganizations")
        assert result_apply["success"] is True
        
        # Files should be moved/renamed
        assert not (subdir / ".env").exists()
        assert (tmp_path / ".env").exists()  # Moved to root
        
        # In case-insensitive systems (like Windows), we must check the exact casing via listdir
        files_in_subdir = os.listdir(subdir)
        assert "style.css" in files_in_subdir
        assert "style.CSS" not in files_in_subdir
        
        assert "my_script.py" in files_in_subdir
        assert "my script.py" not in files_in_subdir
        
        # References in referrer.py should be updated
        ref_content = referrer_file.read_text()
        assert "my script" not in ref_content
        assert "my_script" in ref_content
        assert "subdir/.env" not in ref_content
        assert ".env" in ref_content  # Note: since .env moved to root, subdir/.env gets updated (either by name or route)
        assert "style.CSS" not in ref_content
        assert "style.css" in ref_content
