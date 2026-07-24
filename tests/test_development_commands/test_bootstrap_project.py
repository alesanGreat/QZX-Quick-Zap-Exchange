#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the BootstrapProject command
"""

import os
from qzx.commands.development.bootstrap_project import BootstrapProjectCommand

class TestBootstrapProjectCommand:
    """
    Tests for the BootstrapProject command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = BootstrapProjectCommand()
        
    def test_bootstrap_project_dry_run(self, tmp_path):
        """Test bootstrap in dry-run mode"""
        result = self.command.execute(path=str(tmp_path), tech="python", dry_run=True)
        assert result["success"] is True
        details = result["details"]
        assert details["detected_tech"] == "python"
        assert details["dry_run_mode"] is True
        
        # Verify directories are NOT created in dry_run if they didn't exist
        assert not os.path.exists(tmp_path / "src")
        assert not os.path.exists(tmp_path / "venv")
        
    def test_bootstrap_project_directory_creation(self, tmp_path):
        """Test bootstrap directories are successfully created"""
        # Run with dry_run=False but minimal steps
        result = self.command.execute(path=str(tmp_path), tech="python", dry_run=False)
        assert result["success"] is True
        details = result["details"]
        assert details["detected_tech"] == "python"
        
        # Verify directories were created
        assert os.path.exists(tmp_path / "src")
        assert os.path.exists(tmp_path / "tests")
        
    def test_bootstrap_project_env_creation(self, tmp_path):
        """Test bootstrap copies .env.example to .env"""
        env_ex = tmp_path / ".env.example"
        env_ex.write_text("API_URL=http://localhost\n")
        
        result = self.command.execute(path=str(tmp_path), tech="node", dry_run=False)
        assert result["success"] is True
        
        # Verify .env exists
        assert os.path.exists(tmp_path / ".env")
        assert (tmp_path / ".env").read_text() == "API_URL=http://localhost\n"
