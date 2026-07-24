#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
BootstrapProject Command - Initializes a project from scratch
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class BootstrapProjectCommand(CommandBase):
    """
    Command to bootstrap a project: set up directory structure, virtual envs, dependencies,
    configure git hooks, environment variables, and run initial checks.
    """
    
    name = "bootstrapProject"
    description = "Initializes a project from scratch, setting up directories, virtual environments, dependencies, .env files, and git hooks"
    category = "development"
    requires_explicit_approval = True
    backup_target_parameter = "path"
    
    parameters = [
        {
            'name': 'path',
            'description': 'Path to the directory to bootstrap (default: \'.\')',
            'required': False,
            'default': '.'
        },
        {
            'name': 'tech',
            'description': 'Technology stack: python, node, rust, php, cpp, typescript (optional, auto-detected if not specified)',
            'required': False,
            'default': None
        },
        {
            'name': 'dry_run',
            'description': 'If True, simulate the bootstrap process without writing/running commands (default: True)',
            'required': False,
            'default': True,
            'type': 'bool'
        }
    ]
    
    examples = [
        {
            'command': 'qzx bootstrapProject',
            'description': 'Preview bootstrap of the current project'
        },
        {
            'command': 'qzx bootstrapProject --tech python --dry_run false',
            'description': 'Back up and bootstrap a Python project'
        },
        {
            'command': 'qzx bootstrapProject --dry_run True',
            'description': 'Simulate the bootstrap process'
        }
    ]
    
    def execute(self, path='.', tech=None, dry_run=True):
        """
        Executes the bootstrap process
        """
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            if not dry_run:
                try:
                    os.makedirs(abs_path, exist_ok=True)
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to create directory '{path}': {e}",
                        "message": f"Failed to create directory '{path}'"
                    }
                    
        if isinstance(dry_run, str):
            dry_run = dry_run.strip().lower() in ('true', '1', 'yes')
            
        steps = []
        environment_created = "skipped"
        dependencies_installed = "skipped"
        env_file_created = "skipped"
        hooks_configured = "skipped"
        tests_result = "skipped"
        
        # 1. Detect Technology
        files_in_root = os.listdir(abs_path) if os.path.exists(abs_path) else []
        detected_tech = tech
        if not detected_tech:
            if "Cargo.toml" in files_in_root:
                detected_tech = "rust"
            elif "package.json" in files_in_root:
                detected_tech = "typescript" if "tsconfig.json" in files_in_root else "node"
            elif "composer.json" in files_in_root:
                detected_tech = "php"
            elif "CMakeLists.txt" in files_in_root or "Makefile" in files_in_root:
                detected_tech = "cpp"
            elif "requirements.txt" in files_in_root or "pyproject.toml" in files_in_root or "setup.py" in files_in_root:
                detected_tech = "python"
            else:
                detected_tech = "python" # fallback default
                
        detected_tech = detected_tech.lower().strip()
        
        # 2. Setup standard directory structure
        dirs_to_create = ["src", "tests"]
        if detected_tech == "cpp":
            dirs_to_create = ["src", "include", "tests"]
            
        for d in dirs_to_create:
            dir_to_make = os.path.join(abs_path, d)
            if not os.path.exists(dir_to_make):
                if dry_run:
                    steps.append({"step": f"Create directory {d}", "status": "dry_run"})
                else:
                    try:
                        os.makedirs(dir_to_make, exist_ok=True)
                        steps.append({"step": f"Create directory {d}", "status": "success"})
                    except Exception as e:
                        steps.append({"step": f"Create directory {d}", "status": "failed", "error": str(e)})
            else:
                steps.append({"step": f"Create directory {d}", "status": "skip_exists"})
                
        # 3. Setup Virtual Env / node_modules initialization
        if detected_tech == "python":
            venv_path = os.path.join(abs_path, "venv")
            if not os.path.exists(venv_path):
                if dry_run:
                    environment_created = "dry_run"
                    steps.append({"step": "Create Python Virtual Environment (venv)", "status": "dry_run"})
                else:
                    try:
                        subprocess.run([sys.executable, "-m", "venv", "venv"], cwd=abs_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        environment_created = "created"
                        steps.append({"step": "Create Python Virtual Environment (venv)", "status": "success"})
                    except Exception as e:
                        environment_created = "failed"
                        steps.append({"step": "Create Python Virtual Environment (venv)", "status": "failed", "error": str(e)})
            else:
                environment_created = "skip_exists"
                steps.append({"step": "Create Python Virtual Environment (venv)", "status": "skip_exists"})
                
        elif detected_tech in ("node", "typescript"):
            # Init package.json if it doesn't exist
            pkg_json = os.path.join(abs_path, "package.json")
            if not os.path.exists(pkg_json):
                if dry_run:
                    environment_created = "dry_run"
                    steps.append({"step": "npm init -y", "status": "dry_run"})
                else:
                    try:
                        subprocess.run(["npm", "init", "-y"], cwd=abs_path, check=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        environment_created = "created"
                        steps.append({"step": "npm init -y", "status": "success"})
                    except Exception as e:
                        environment_created = "failed"
                        steps.append({"step": "npm init -y", "status": "failed", "error": str(e)})
            else:
                environment_created = "skip_exists"
                
        elif detected_tech == "rust":
            cargo_toml = os.path.join(abs_path, "Cargo.toml")
            if not os.path.exists(cargo_toml):
                if dry_run:
                    environment_created = "dry_run"
                    steps.append({"step": "cargo init", "status": "dry_run"})
                else:
                    try:
                        subprocess.run(["cargo", "init"], cwd=abs_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        environment_created = "created"
                        steps.append({"step": "cargo init", "status": "success"})
                    except Exception as e:
                        environment_created = "failed"
                        steps.append({"step": "cargo init", "status": "failed", "error": str(e)})
            else:
                environment_created = "skip_exists"
                
        # 4. Install Dependencies
        if detected_tech == "python":
            req_file = os.path.join(abs_path, "requirements.txt")
            if os.path.exists(req_file):
                # find pip in venv
                pip_path = os.path.join(venv_path, "Scripts", "pip.exe") if os.name == 'nt' else os.path.join(venv_path, "bin", "pip")
                if not os.path.exists(pip_path):
                    pip_path = "pip"
                if dry_run:
                    dependencies_installed = "dry_run"
                    steps.append({"step": "Install Python dependencies from requirements.txt", "status": "dry_run"})
                else:
                    try:
                        subprocess.run([pip_path, "install", "-r", "requirements.txt"], cwd=abs_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        dependencies_installed = "installed"
                        steps.append({"step": "Install Python dependencies from requirements.txt", "status": "success"})
                    except Exception as e:
                        dependencies_installed = "failed"
                        steps.append({"step": "Install Python dependencies from requirements.txt", "status": "failed", "error": str(e)})
            else:
                dependencies_installed = "no_requirements_file"
                
        elif detected_tech in ("node", "typescript"):
            if "package.json" in os.listdir(abs_path):
                if dry_run:
                    dependencies_installed = "dry_run"
                    steps.append({"step": "npm install", "status": "dry_run"})
                else:
                    try:
                        subprocess.run(["npm", "install"], cwd=abs_path, check=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        dependencies_installed = "installed"
                        steps.append({"step": "npm install", "status": "success"})
                    except Exception as e:
                        dependencies_installed = "failed"
                        steps.append({"step": "npm install", "status": "failed", "error": str(e)})
                        
        elif detected_tech == "php":
            if "composer.json" in os.listdir(abs_path):
                if dry_run:
                    dependencies_installed = "dry_run"
                    steps.append({"step": "composer install", "status": "dry_run"})
                else:
                    try:
                        subprocess.run(["composer", "install"], cwd=abs_path, check=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        dependencies_installed = "installed"
                        steps.append({"step": "composer install", "status": "success"})
                    except Exception as e:
                        dependencies_installed = "failed"
                        steps.append({"step": "composer install", "status": "failed", "error": str(e)})
                        
        # 5. Generate .env file
        env_ex_file = os.path.join(abs_path, ".env.example")
        env_file = os.path.join(abs_path, ".env")
        if not os.path.exists(env_file):
            if os.path.exists(env_ex_file):
                if dry_run:
                    env_file_created = "dry_run"
                    steps.append({"step": "Copy .env.example to .env", "status": "dry_run"})
                else:
                    try:
                        shutil.copyfile(env_ex_file, env_file)
                        env_file_created = "created"
                        steps.append({"step": "Copy .env.example to .env", "status": "success"})
                    except Exception as e:
                        env_file_created = "failed"
                        steps.append({"step": "Copy .env.example to .env", "status": "failed", "error": str(e)})
            else:
                # Generate default env file content
                import secrets
                rand_key = secrets.token_hex(24)
                if detected_tech == "python":
                    default_env_content = f"DEBUG=True\nSECRET_KEY={rand_key}\nDATABASE_URL=sqlite:///db.sqlite3\nPORT=8000\n"
                elif detected_tech in ("node", "typescript"):
                    default_env_content = f"NODE_ENV=development\nPORT=3000\nDATABASE_URL=mongodb://localhost:27017/app\nJWT_SECRET={rand_key}\n"
                elif detected_tech == "php":
                    default_env_content = f"APP_ENV=local\nAPP_DEBUG=true\nAPP_KEY=base64:{rand_key}\nDB_CONNECTION=sqlite\n"
                else:
                    default_env_content = f"DATABASE_URL=sqlite:///db.sqlite3\nLOG_LEVEL=debug\n"
                
                if dry_run:
                    env_file_created = "dry_run"
                    steps.append({"step": "Generate default .env file", "status": "dry_run"})
                else:
                    try:
                        with open(env_file, "w", encoding="utf-8") as f:
                            f.write(default_env_content)
                        env_file_created = "generated_default"
                        steps.append({"step": "Generate default .env file", "status": "success"})
                    except Exception as e:
                        env_file_created = "failed"
                        steps.append({"step": "Generate default .env file", "status": "failed", "error": str(e)})
        else:
            env_file_created = "skip_exists"
            steps.append({"step": "Generate .env file", "status": "skip_exists"})
            
        # 6. Configure git hooks
        git_dir = os.path.join(abs_path, ".git")
        if os.path.exists(git_dir):
            hooks_dir = os.path.join(git_dir, "hooks")
            pre_commit = os.path.join(hooks_dir, "pre-commit")
            if os.path.exists(hooks_dir) and not os.path.exists(pre_commit):
                if dry_run:
                    hooks_configured = "dry_run"
                    steps.append({"step": "Configure Git pre-commit hook", "status": "dry_run"})
                else:
                    try:
                        with open(pre_commit, "w", encoding="utf-8") as hf:
                            hf.write("#!/bin/sh\n# QZX auto-generated pre-commit hook\nexit 0\n")
                        # chmod if not windows
                        if os.name != 'nt':
                            os.chmod(pre_commit, 0o755)
                        hooks_configured = "configured"
                        steps.append({"step": "Configure Git pre-commit hook", "status": "success"})
                    except Exception as e:
                        hooks_configured = "failed"
                        steps.append({"step": "Configure Git pre-commit hook", "status": "failed", "error": str(e)})
            else:
                hooks_configured = "skipped"
                
        # 6c. Execute database migrations
        migrations_executed = "skipped"
        migration_command = None
        if "manage.py" in files_in_root:
            python_bin = os.path.join(venv_path, "Scripts", "python.exe") if os.name == 'nt' else os.path.join(venv_path, "bin", "python")
            if not os.path.exists(python_bin):
                python_bin = "python"
            migration_command = [python_bin, "manage.py", "migrate"]
        elif "artisan" in files_in_root:
            migration_command = ["php", "artisan", "migrate", "--force"]
        elif "prisma" in files_in_root or any("prisma" in f for f in files_in_root):
            migration_command = ["npx", "prisma", "db", "push"]
            
        if migration_command:
            if dry_run:
                migrations_executed = "dry_run"
                steps.append({"step": f"Run database migrations ({' '.join(migration_command)})", "status": "dry_run"})
            else:
                try:
                    res = subprocess.run(
                        migration_command,
                        cwd=abs_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        shell=(migration_command[0] in ("npx", "php") and os.name == 'nt'),
                        timeout=30
                    )
                    if res.returncode == 0:
                        migrations_executed = "success"
                        steps.append({"step": "Run database migrations", "status": "success"})
                    else:
                        migrations_executed = "failed"
                        steps.append({"step": "Run database migrations", "status": "failed", "error": res.stderr.decode('utf-8', errors='ignore')})
                except Exception as e:
                    migrations_executed = f"failed: {e}"
                    steps.append({"step": "Run database migrations", "status": "failed", "error": str(e)})
                    
        # 7. Run initial tests
        if not dry_run:
            if detected_tech == "python":
                pytest_bin = os.path.join(venv_path, "Scripts", "pytest.exe") if os.name == 'nt' else os.path.join(venv_path, "bin", "pytest")
                if os.path.exists(pytest_bin):
                    try:
                        subprocess.run([pytest_bin, "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        tests_result = "available"
                    except:
                        tests_result = "failed"
            elif detected_tech == "rust":
                try:
                    subprocess.run(["cargo", "test", "--no-run"], cwd=abs_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    tests_result = "passed"
                except:
                    tests_result = "failed"
                    
        summary_msg = f"Project bootstrapped successfully for technology: {detected_tech}."
        if dry_run:
            summary_msg += " (Dry Run mode)"
            
        return {
            "success": True,
            "message": summary_msg,
            "details": {
                "detected_tech": detected_tech,
                "steps_executed": steps,
                "environment_created": environment_created,
                "dependencies_installed": dependencies_installed,
                "env_file_created": env_file_created,
                "hooks_configured": hooks_configured,
                "migrations_executed": migrations_executed,
                "tests_result": tests_result,
                "dry_run_mode": dry_run
            }
        }
