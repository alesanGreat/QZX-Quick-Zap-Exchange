#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the ReleaseProject command
"""

import os
import json
from qzx.commands.development.release_project import ReleaseProjectCommand

class TestReleaseProjectCommand:
    """
    Tests for the ReleaseProject command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = ReleaseProjectCommand()
        
    def test_release_project_semver_bumping(self):
        """Test semantic version calculations"""
        assert self.command._bump_semver("1.2.3", "patch") == "1.2.4"
        assert self.command._bump_semver("1.2.3", "minor") == "1.3.0"
        assert self.command._bump_semver("1.2.3", "major") == "2.0.0"
        
    def test_release_project_dry_run_npm(self, tmp_path):
        """Test releaseProject dry_run mode in a mock NPM project"""
        pkg_json = tmp_path / "package.json"
        pkg_json.write_text(json.dumps({"name": "test-pkg", "version": "1.0.0"}))
        
        result = self.command.execute(bump="minor", path=str(tmp_path), dry_run=True)
        assert result["success"] is True
        details = result["details"]
        assert details["old_version"] == "1.0.0"
        assert details["new_version"] == "1.1.0"
        assert details["dry_run_mode"] is True
        
        # Manifest shouldn't have changed in dry_run
        with open(pkg_json, 'r') as f:
            data = json.load(f)
            assert data["version"] == "1.0.0"
            
    def test_release_project_apply_python(self, tmp_path):
        """Test releaseProject actually writing version changes to pyproject.toml"""
        pyproj = tmp_path / "pyproject.toml"
        pyproj.write_text("[project]\nname = 'test'\nversion = \"2.4.1\"\n")
        
        result = self.command.execute(bump="patch", path=str(tmp_path), dry_run=False)
        assert result["success"] is True
        details = result["details"]
        assert details["old_version"] == "2.4.1"
        assert details["new_version"] == "2.4.2"
        assert details["dry_run_mode"] is False
        
        # Read the file and verify it changed
        content = pyproj.read_text()
        assert 'version = "2.4.2"' in content
        
        # Verify CHANGELOG.md was created
        changelog = tmp_path / "CHANGELOG.md"
        assert os.path.exists(changelog)
        assert "## [2.4.2]" in changelog.read_text()
