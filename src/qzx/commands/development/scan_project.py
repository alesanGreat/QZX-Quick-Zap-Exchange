#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ScanProject Command - Analyzes a project directory, detects tech stack, configuration files, and validates environment files.
"""

import os
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class ScanProjectCommand(CommandBase):
    """
    Command to inspect and summarize a project workspace, identifying tech stacks, configuration setups, and missing env keys.
    """
    
    name = "scanProject"
    description = "Scans a project root to identify technologies, scripts, configuration files, and missing environment keys"
    category = "development"
    
    parameters = [
        {
            'name': 'project_path',
            'description': 'Path to the project root directory (defaults to current directory)',
            'required': False,
            'default': '.'
        }
    ]
    
    examples = [
        {
            'command': 'qzx scanProject',
            'description': 'Scan the current workspace directory'
        },
        {
            'command': 'qzx scanProject C:/my-projects/app',
            'description': 'Scan the project located at C:/my-projects/app'
        }
    ]
    
    def execute(self, project_path='.'):
        """
        Scans and diagnoses a project directory
        
        Args:
            project_path (str): Path to scan
            
        Returns:
            Dictionary with project diagnostic details
        """
        abs_path = os.path.abspath(project_path)
        
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"Path '{project_path}' does not exist.",
                "message": f"Path '{project_path}' does not exist."
            }
            
        if not os.path.isdir(abs_path):
            return {
                "success": False,
                "error": f"'{project_path}' is not a directory. Project scan requires a directory.",
                "message": f"'{project_path}' is not a directory."
            }
            
        try:
            # 1. Detect Configuration Files & Folders
            configs = self._detect_config_files(abs_path)
            
            # 2. Detect Tech Stack
            tech_stacks, package_managers = self._detect_technologies(abs_path, configs)
            
            # 3. Parse Node.js package.json details
            node_details = self._parse_package_json(abs_path)
            
            # 4. Parse Python requirements
            python_details = self._parse_python_requirements(abs_path)
            
            # 4b. Parse PHP composer details
            php_details = self._parse_composer_json(abs_path)
            
            # 5. Environment File Diagnostics (.env vs .env.example)
            env_details = self._diagnose_env_files(abs_path)
            
            # Formulate description message
            techs_str = ", ".join(tech_stacks) if tech_stacks else "Unknown"
            msg = f"Project scan completed for '{abs_path}':\n"
            msg += f"- Detected Tech: {techs_str}\n"
            
            if package_managers:
                msg += f"- Package Managers: {', '.join(package_managers)}\n"
                
            if node_details and node_details.get("name"):
                msg += f"- Node Project: {node_details['name']} (v{node_details.get('version', 'unknown')})\n"
                if node_details.get("scripts"):
                    msg += f"  - NPM Scripts: {', '.join(node_details['scripts'].keys())}\n"
                    
            if python_details and python_details.get("requirements_file_found"):
                msg += f"- Python: Found requirements.txt with {python_details['count']} packages.\n"
                
            if php_details and php_details.get("name"):
                msg += f"- PHP Project: {php_details['name']}\n"
                msg += f"  - Composer Dependencies: {php_details['dependencies_count']} packages, {php_details['devDependencies_count']} dev packages\n"
                
            if env_details.get("example_file_found"):
                missing = env_details.get("missing_keys", [])
                if env_details.get("local_file_found"):
                    if missing:
                        msg += f"- Environment warning: {len(missing)} keys are missing in '.env' that are defined in '{env_details['example_filename']}': {', '.join(missing)}\n"
                    else:
                        msg += f"- Environment status: '.env' is in sync with '{env_details['example_filename']}'.\n"
                else:
                    msg += f"- Environment notice: Found '{env_details['example_filename']}' but no local '.env' file exists.\n"
            else:
                msg += "- Environment: No .env templates found.\n"
                
            return {
                "success": True,
                "project_path": abs_path,
                "project_types": tech_stacks,
                "package_managers": package_managers,
                "configuration_files": configs,
                "package_json": node_details,
                "python_dependencies": python_details,
                "php_dependencies": php_details,
                "environment_diagnostics": env_details,
                "message": msg
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to scan project: {str(e)}"
            }
            
    def _detect_config_files(self, path):
        """Checks for the existence of various configuration files in the root"""
        files = {
            "git": ".git",
            "docker": "Dockerfile",
            "docker_compose": ["docker-compose.yml", "docker-compose.yaml"],
            "typescript": "tsconfig.json",
            "eslint": [".eslintrc", ".eslintrc.json", ".eslintrc.js", "eslint.config.js"],
            "tailwind": ["tailwind.config.js", "tailwind.config.ts"],
            "vite": ["vite.config.js", "vite.config.ts", "vite.config.mjs"],
            "next": ["next.config.js", "next.config.mjs"],
            "github_workflows": ".github/workflows",
            "composer": "composer.json"
        }
        
        results = {}
        for key, value in files.items():
            if isinstance(value, list):
                results[key] = any(os.path.exists(os.path.join(path, f)) for f in value)
            else:
                results[key] = os.path.exists(os.path.join(path, value))
        return results
        
    def _detect_technologies(self, path, configs):
        """Identifies tech stacks based on key root files"""
        techs = []
        managers = []
        
        # Node
        if os.path.exists(os.path.join(path, "package.json")):
            techs.append("Node.js")
            if os.path.exists(os.path.join(path, "package-lock.json")):
                managers.append("npm")
            if os.path.exists(os.path.join(path, "pnpm-lock.yaml")):
                managers.append("pnpm")
            if os.path.exists(os.path.join(path, "yarn.lock")):
                managers.append("yarn")
            if os.path.exists(os.path.join(path, "bun.lockb")) or os.path.exists(os.path.join(path, "bun.lock")):
                managers.append("bun")
                
        # Python
        py_files = ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"]
        if any(os.path.exists(os.path.join(path, f)) for f in py_files):
            techs.append("Python")
            if os.path.exists(os.path.join(path, "Pipfile")):
                managers.append("pipenv")
            if os.path.exists(os.path.join(path, "poetry.lock")):
                managers.append("poetry")
            elif os.path.exists(os.path.join(path, "requirements.txt")):
                managers.append("pip")
                
        # Rust
        if os.path.exists(os.path.join(path, "Cargo.toml")):
            techs.append("Rust")
            managers.append("cargo")
            
        # Go
        if os.path.exists(os.path.join(path, "go.mod")):
            techs.append("Go")
            managers.append("go")
            
        # TypeScript
        if configs.get("typescript"):
            techs.append("TypeScript")
            
        # Docker
        if configs.get("docker") or configs.get("docker_compose"):
            techs.append("Docker")
            
        # Frontend-specific frameworks
        if configs.get("next"):
            techs.append("Next.js")
        elif configs.get("vite"):
            techs.append("Vite")
            
        # PHP
        if configs.get("composer") or any(f.endswith('.php') for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))):
            techs.append("PHP")
            if configs.get("composer"):
                managers.append("composer")
            
        return techs, list(set(managers))
        
    def _parse_package_json(self, path):
        """Parses package.json if it exists"""
        file_path = os.path.join(path, "package.json")
        if not os.path.exists(file_path):
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            return {
                "name": data.get("name"),
                "version": data.get("version"),
                "description": data.get("description"),
                "scripts": data.get("scripts", {}),
                "dependencies_count": len(data.get("dependencies", {})),
                "devDependencies_count": len(data.get("devDependencies", {})),
                "dependencies_keys": list(data.get("dependencies", {}).keys()),
                "devDependencies_keys": list(data.get("devDependencies", {}).keys())
            }
        except Exception:
            return {"error": "Failed to parse package.json (invalid JSON)"}
            
    def _parse_python_requirements(self, path):
        """Parses requirements.txt count and names"""
        file_path = os.path.join(path, "requirements.txt")
        if not os.path.exists(file_path):
            return {"requirements_file_found": False, "count": 0}
            
        try:
            packages = []
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith('-r'):
                        continue
                    # Strip version specifiers (e.g. Flask>=2.0.0 -> Flask)
                    pkg = line
                    for spec in ['==', '>=', '<=', '>', '<', '~=']:
                        if spec in pkg:
                            pkg = pkg.split(spec)[0].strip()
                    packages.append(pkg)
                    
            return {
                "requirements_file_found": True,
                "count": len(packages),
                "packages": packages
            }
        except Exception as e:
            return {
                "requirements_file_found": True,
                "count": 0,
                "error": f"Failed to parse requirements.txt: {str(e)}"
            }
            
    def _diagnose_env_files(self, path):
        """Validates environment keys between .env.example/template and local .env"""
        # Find template/example files
        example_names = [".env.example", ".env.template", ".env.sample", "env.example"]
        example_file = None
        example_name = None
        
        for name in example_names:
            p = os.path.join(path, name)
            if os.path.exists(p):
                example_file = p
                example_name = name
                break
                
        # Find local files
        local_names = [".env", ".env.local", ".env.development"]
        local_file = None
        local_name = None
        
        for name in local_names:
            p = os.path.join(path, name)
            if os.path.exists(p):
                local_file = p
                local_name = name
                break
                
        if not example_file:
            # Check if there is a local .env at least
            has_local = local_file is not None
            return {
                "example_file_found": False,
                "local_file_found": has_local,
                "local_filename": local_name,
                "missing_keys": []
            }
            
        example_keys = self._parse_env_keys(example_file)
        local_keys = self._parse_env_keys(local_file) if local_file else set()
        
        missing = sorted(list(example_keys - local_keys))
        
        return {
            "example_file_found": True,
            "example_filename": example_name,
            "local_file_found": local_file is not None,
            "local_filename": local_name,
            "example_keys": sorted(list(example_keys)),
            "local_keys": sorted(list(local_keys)),
            "missing_keys": missing,
            "keys_configured_ok": len(example_keys & local_keys)
        }
        
    def _parse_env_keys(self, file_path):
        """Extracts unique variable keys from a .env file format"""
        keys = set()
        if not file_path or not os.path.exists(file_path):
            return keys
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    # Match KEY=VALUE (also handles export KEY=VALUE)
                    if '=' in line:
                        parts = line.split('=', 1)
                        key = parts[0].strip()
                        # Strip export keyword if present
                        if key.startswith('export '):
                            key = key[7:].strip()
                        if key:
                            keys.add(key)
        except Exception:
            pass
        return keys

    def _parse_composer_json(self, path):
        """Parses composer.json if it exists"""
        file_path = os.path.join(path, "composer.json")
        if not os.path.exists(file_path):
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            return {
                "name": data.get("name"),
                "description": data.get("description"),
                "dependencies_count": len(data.get("require", {})),
                "devDependencies_count": len(data.get("require-dev", {})),
                "dependencies_keys": list(data.get("require", {}).keys()),
                "devDependencies_keys": list(data.get("require-dev", {}).keys())
            }
        except Exception:
            return {"error": "Failed to parse composer.json (invalid JSON)"}
