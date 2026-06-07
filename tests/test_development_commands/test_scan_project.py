#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the ScanProject command
"""

import os
import json
from qzx.commands.development.scan_project import ScanProjectCommand

class TestScanProjectCommand:
    """
    Tests for the ScanProject command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = ScanProjectCommand()
        
    def test_nonexistent_directory(self):
        """Test with a directory that does not exist"""
        result = self.command.execute("non_existent_dir_abc_123")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_file_instead_of_directory(self, tmp_path):
        """Test with a file path instead of a directory"""
        file_path = tmp_path / "test.txt"
        file_path.touch()
        
        result = self.command.execute(str(file_path))
        assert result["success"] is False
        assert "is not a directory" in result["error"]
        
    def test_scan_empty_directory(self, tmp_path):
        """Test scanning a clean empty directory"""
        result = self.command.execute(str(tmp_path))
        
        assert result["success"] is True
        assert result["project_types"] == []
        assert result["package_managers"] == []
        assert result["package_json"] is None
        assert result["python_dependencies"]["requirements_file_found"] is False
        assert result["environment_diagnostics"]["example_file_found"] is False
        assert result["environment_diagnostics"]["local_file_found"] is False
        
    def test_scan_nodejs_ts_project(self, tmp_path):
        """Test scanning a Node.js project with TypeScript and ESLint"""
        # Create package.json
        package_json = {
            "name": "my-mock-app",
            "version": "2.1.0",
            "description": "Mock Node project",
            "scripts": {
                "dev": "vite",
                "build": "tsc && vite build"
            },
            "dependencies": {
                "react": "^18.2.0"
            },
            "devDependencies": {
                "typescript": "^5.0.0"
            }
        }
        with open(tmp_path / "package.json", "w", encoding="utf-8") as f:
            json.dump(package_json, f)
            
        # Create lockfile and TS/ESLint configs
        (tmp_path / "pnpm-lock.yaml").touch()
        (tmp_path / "tsconfig.json").touch()
        (tmp_path / "eslint.config.js").touch()
        
        result = self.command.execute(str(tmp_path))
        
        assert result["success"] is True
        assert "Node.js" in result["project_types"]
        assert "TypeScript" in result["project_types"]
        assert "pnpm" in result["package_managers"]
        assert result["configuration_files"]["typescript"] is True
        assert result["configuration_files"]["eslint"] is True
        
        node = result["package_json"]
        assert node["name"] == "my-mock-app"
        assert node["version"] == "2.1.0"
        assert "dev" in node["scripts"]
        assert node["dependencies_count"] == 1
        assert node["devDependencies_count"] == 1
        
    def test_scan_python_project(self, tmp_path):
        """Test scanning a Python project with requirements.txt"""
        # Create requirements.txt
        reqs = (
            "# Main Dependencies\n"
            "Flask==2.0.1\n"
            "requests>=2.25.0\n"
            "pytest\n"
        )
        with open(tmp_path / "requirements.txt", "w", encoding="utf-8") as f:
            f.write(reqs)
            
        result = self.command.execute(str(tmp_path))
        
        assert result["success"] is True
        assert "Python" in result["project_types"]
        assert "pip" in result["package_managers"]
        
        py = result["python_dependencies"]
        assert py["requirements_file_found"] is True
        assert py["count"] == 3
        assert "Flask" in py["packages"]
        assert "requests" in py["packages"]
        assert "pytest" in py["packages"]
        
    def test_env_file_diagnostics(self, tmp_path):
        """Test the .env versus .env.example matching logic"""
        # Create .env.example
        env_example = (
            "# App config\n"
            "PORT=3000\n"
            "DB_HOST=localhost\n"
            "API_SECRET=\n"
            "DEBUG=true\n"
        )
        with open(tmp_path / ".env.example", "w", encoding="utf-8") as f:
            f.write(env_example)
            
        # Create local .env missing some keys
        env_local = (
            "PORT=8080\n"
            "export DB_HOST=127.0.0.1\n"
        )
        with open(tmp_path / ".env", "w", encoding="utf-8") as f:
            f.write(env_local)
            
        result = self.command.execute(str(tmp_path))
        
        assert result["success"] is True
        env = result["environment_diagnostics"]
        assert env["example_file_found"] is True
        assert env["local_file_found"] is True
        assert env["example_filename"] == ".env.example"
        assert env["local_filename"] == ".env"
        
        # Verify keys
        assert "PORT" in env["example_keys"]
        assert "DB_HOST" in env["example_keys"]
        assert "API_SECRET" in env["example_keys"]
        assert "DEBUG" in env["example_keys"]
        
        assert "PORT" in env["local_keys"]
        assert "DB_HOST" in env["local_keys"]
        
        # Verify missing keys
        assert "API_SECRET" in env["missing_keys"]
        assert "DEBUG" in env["missing_keys"]
        assert "PORT" not in env["missing_keys"]
        assert "DB_HOST" not in env["missing_keys"]
        assert env["keys_configured_ok"] == 2

    def test_scan_php_project(self, tmp_path):
        """Test scanning a PHP project with composer.json"""
        composer_json = {
            "name": "mock/php-app",
            "description": "Mock PHP composer project",
            "require": {
                "php": ">=8.1",
                "laravel/framework": "^10.0"
            },
            "require-dev": {
                "phpunit/phpunit": "^10.0"
            }
        }
        with open(tmp_path / "composer.json", "w", encoding="utf-8") as f:
            json.dump(composer_json, f)
            
        result = self.command.execute(str(tmp_path))
        
        assert result["success"] is True
        assert "PHP" in result["project_types"]
        assert "composer" in result["package_managers"]
        assert result["configuration_files"]["composer"] is True
        
        php = result["php_dependencies"]
        assert php is not None
        assert php["name"] == "mock/php-app"
        assert php["dependencies_count"] == 2
        assert php["devDependencies_count"] == 1
        assert "laravel/framework" in php["dependencies_keys"]
