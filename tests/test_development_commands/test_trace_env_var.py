#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the traceEnvVar command
"""

import os
from qzx.commands.development.trace_env_var import TraceEnvVarCommand

class TestTraceEnvVarCommand:
    """
    Tests for the TraceEnvVarCommand class
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = TraceEnvVarCommand()
        
    def test_nonexistent_directory(self):
        """Test with a directory that does not exist"""
        result = self.command.execute("PORT", "non_existent_dir_abc_123")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_empty_variable_name(self):
        """Test with an empty variable name"""
        result = self.command.execute("  ", ".")
        assert result["success"] is False
        assert "cannot be empty" in result["error"]
        
    def test_trace_in_env_files(self, tmp_path):
        """Test tracing an environment variable configured in env files"""
        # Create .env and .env.example
        env_content = (
            "PORT=3000\n"
            "DATABASE_URL=postgresql://user:pass@host/db\n"
            "SECRET_KEY=supersecretkey\n"
        )
        env_example_content = (
            "PORT=8000\n"
            "DATABASE_URL=\n"
            "SECRET_KEY=\n"
        )
        
        with open(tmp_path / ".env", "w", encoding="utf-8") as f:
            f.write(env_content)
        with open(tmp_path / ".env.example", "w", encoding="utf-8") as f:
            f.write(env_example_content)
            
        # Create a Python file reading the variable
        py_content = (
            "import os\n"
            "port = os.getenv('PORT', 8080)\n"
            "db = os.environ.get('DATABASE_URL')\n"
            "secret = os.getenv('SECRET_KEY')\n"
        )
        with open(tmp_path / "app.py", "w", encoding="utf-8") as f:
            f.write(py_content)
            
        # Trace PORT
        result_port = self.command.execute("PORT", str(tmp_path))
        assert result_port["success"] is True
        assert result_port["env_files_diagnostics"][".env"]["defined"] is True
        assert result_port["env_files_diagnostics"][".env"]["masked_value"] == "30...00"
        assert result_port["env_files_diagnostics"][".env.example"]["defined"] is True
        assert result_port["references_count"] == 1
        assert result_port["references"][0]["file"] == "app.py"
        assert result_port["references"][0]["line_number"] == 2
        assert "PORT" in result_port["references"][0]["line_content"]
        assert result_port["references"][0]["fallback_detected"] == "8080"
        
        # Trace SECRET_KEY (should mask the value securely)
        result_secret = self.command.execute("SECRET_KEY", str(tmp_path))
        assert result_secret["success"] is True
        assert result_secret["env_files_diagnostics"][".env"]["defined"] is True
        assert result_secret["env_files_diagnostics"][".env"]["masked_value"] == "su...ey"
        assert result_secret["references_count"] == 1
        assert result_secret["references"][0]["file"] == "app.py"
        assert result_secret["references"][0]["line_number"] == 4

    def test_trace_php_fallback(self, tmp_path):
        """Test tracing environment variables in PHP files with fallbacks"""
        php_content = (
            "<?php\n"
            "$port = getenv('DB_PORT') ?: 3306;\n"
            "$host = $_ENV['DB_HOST'] ?? 'localhost';\n"
            "$user = $_SERVER['DB_USER'] ?? 'root';\n"
        )
        with open(tmp_path / "config.php", "w", encoding="utf-8") as f:
            f.write(php_content)
            
        result_port = self.command.execute("DB_PORT", str(tmp_path))
        assert result_port["success"] is True
        assert result_port["references_count"] == 1
        assert result_port["references"][0]["file"] == "config.php"
        assert result_port["references"][0]["fallback_detected"] == "3306"
        
        result_host = self.command.execute("DB_HOST", str(tmp_path))
        assert result_host["success"] is True
        assert result_host["references_count"] == 1
        assert result_host["references"][0]["fallback_detected"] == "'localhost'"

        result_user = self.command.execute("DB_USER", str(tmp_path))
        assert result_user["success"] is True
        assert result_user["references_count"] == 1
        assert result_user["references"][0]["fallback_detected"] == "'root'"
