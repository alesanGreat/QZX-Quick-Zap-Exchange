#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ProjectDoctor Command - Comprehensive analysis of a project's stack, configuration, quality, and Git state.
"""

import os
import sys
import subprocess
import shutil
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

# Import sibling commands if possible
try:
    from qzx.commands.development.find_dead_code import FindDeadCodeCommand
except ImportError:
    FindDeadCodeCommand = None

try:
    from qzx.commands.development.trace_circular_imports import TraceCircularImportsCommand
except ImportError:
    TraceCircularImportsCommand = None

class ProjectDoctorCommand(CommandBase):
    """
    Command to run a full diagnostic on a workspace's project health (VCS, tech stack, deps, env, tests, dead code, circular imports, large files)
    """
    
    name = "projectDoctor"
    description = "Inspects project health: detects tech stack, dependencies, environment configuration, Git state, test suites, circular imports, dead code, and large files"
    category = "development"
    
    parameters = [
        {
            'name': 'path',
            'description': 'Path to the project directory to diagnose (default: \'.\')',
            'required': False,
            'default': '.'
        }
    ]
    
    examples = [
        {
            'command': 'qzx projectDoctor',
            'description': 'Run project health diagnosis for current directory'
        },
        {
            'command': 'qzx projectDoctor C:/my/project',
            'description': 'Diagnose project at specified path'
        }
    ]
    
    def execute(self, path='.'):
        """
        Executes the project doctor analysis
        """
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"Path '{path}' does not exist.",
                "message": f"Path '{path}' does not exist."
            }
            
        results = {
            "stack": [],
            "git": "not_available",
            "dependencies": {},
            "environment": {},
            "tests": "none_detected",
            "code_quality": {},
            "build_check": "not_applicable",
            "files": [],
            "summary": {
                "health_score": 100,
                "issues": []
            }
        }
        
        # 1. Tech Stack Detection
        files_in_root = os.listdir(abs_path) if os.path.isdir(abs_path) else []
        stack = []
        if "pyproject.toml" in files_in_root or "requirements.txt" in files_in_root or "setup.py" in files_in_root:
            stack.append("Python")
        if "package.json" in files_in_root:
            stack.append("Node.js/JavaScript")
            # Check for TS
            if "tsconfig.json" in files_in_root:
                stack.append("TypeScript")
        if "Cargo.toml" in files_in_root:
            stack.append("Rust")
        if "composer.json" in files_in_root:
            stack.append("PHP")
        if "CMakeLists.txt" in files_in_root or "Makefile" in files_in_root:
            stack.append("C++")
            
        results["stack"] = stack
        
        # 2. Git Status
        is_git = False
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=abs_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            is_git = res.returncode == 0 and res.stdout.strip() == "true"
        except:
            pass
            
        if is_git:
            git_info = {"branch": "unknown", "clean": True, "untracked_count": 0, "commits_ahead": 0}
            try:
                # Get branch
                b_res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                git_info["branch"] = b_res.stdout.strip()
                
                # Check clean / untracked
                s_res = subprocess.run(["git", "status", "--porcelain"], cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                status_lines = s_res.stdout.splitlines()
                modified = [l for l in status_lines if not l.startswith("??")]
                untracked = [l for l in status_lines if l.startswith("??")]
                
                git_info["clean"] = len(modified) == 0
                git_info["untracked_count"] = len(untracked)
                git_info["modified_count"] = len(modified)
                
                results["git"] = git_info
            except Exception as e:
                results["git"] = {"error": str(e)}
                
        # 3. Dependencies
        deps_info = {"count": 0, "manifests_found": []}
        if "package.json" in files_in_root:
            deps_info["manifests_found"].append("package.json")
            # Parse package.json (mock or light parse)
            try:
                import json
                with open(os.path.join(abs_path, "package.json"), 'r', encoding='utf-8') as f:
                    pkg_data = json.load(f)
                    dependencies = pkg_data.get("dependencies", {})
                    dev_dependencies = pkg_data.get("devDependencies", {})
                    deps_info["count"] += len(dependencies) + len(dev_dependencies)
            except:
                pass
        if "requirements.txt" in files_in_root:
            deps_info["manifests_found"].append("requirements.txt")
            try:
                with open(os.path.join(abs_path, "requirements.txt"), 'r', encoding='utf-8') as f:
                    reqs = [l for l in f.readlines() if l.strip() and not l.strip().startswith("#")]
                    deps_info["count"] += len(reqs)
            except:
                pass
        if "pyproject.toml" in files_in_root:
            deps_info["manifests_found"].append("pyproject.toml")
            try:
                with open(os.path.join(abs_path, "pyproject.toml"), 'r', encoding='utf-8') as f:
                    content = f.read()
                    # simple dependency counting for pyproject.toml
                    deps = re.findall(r'(?m)^\s*["\']?([a-zA-Z0-9_\-\[\]]+)["\']?\s*=', content)
                    deps_info["count"] += len(deps) // 2 # rough approximation
            except:
                pass
        if "Cargo.toml" in files_in_root:
            deps_info["manifests_found"].append("Cargo.toml")
        if "composer.json" in files_in_root:
            deps_info["manifests_found"].append("composer.json")
            
        results["dependencies"] = deps_info
        
        # 4. Environment Config
        env_info = {"env_file_present": False, "env_example_present": False}
        if ".env" in files_in_root:
            env_info["env_file_present"] = True
        if ".env.example" in files_in_root:
            env_info["env_example_present"] = True
        results["environment"] = env_info
        
        # 5. Tests Check
        test_folders = [d for d in files_in_root if d in ("tests", "test", "spec")]
        test_configs = [f for f in files_in_root if any(cfg in f for cfg in ("pytest", "jest", "phpunit", "vitest"))]
        if test_folders or test_configs or "Rust" in stack:
            test_results = self._run_tests(abs_path, test_folders, test_configs, stack)
            results["tests"] = {
                "detected": True,
                "folders": test_folders,
                "configs": test_configs,
                "execution": test_results
            }
        else:
            results["tests"] = {
                "detected": False,
                "message": "No test suite configurations or folders detected."
            }
            
        # 6. Code Quality (Lint configs, Dead code, Circular imports)
        quality_info = {
            "lint_configs": [f for f in files_in_root if any(cfg in f for cfg in ("eslint", "prettier", "flake8", "pylint", "tsconfig"))],
            "dead_code": "not_run",
            "circular_imports": "not_run",
            "lint_execution": {"executed": False, "status": "skipped"},
            "type_checking": {"executed": False, "status": "skipped"}
        }
        
        # Run lint & type checking tools
        lint_res, type_res = self._run_lint_and_types(abs_path, files_in_root)
        quality_info["lint_execution"] = lint_res
        quality_info["type_checking"] = type_res
        
        # Dead code check (reusing FindDeadCodeCommand)
        if FindDeadCodeCommand:
            try:
                cmd = FindDeadCodeCommand()
                dc_res = cmd.execute(scan_path=abs_path)
                if dc_res.get("success"):
                    quality_info["dead_code"] = {
                        "dead_symbols_count": dc_res.get("dead_symbols_count", 0),
                        "dead_symbols": dc_res.get("dead_symbols", [])[:10]  # Cap list to 10 items
                    }
            except Exception as e:
                quality_info["dead_code"] = {"error": str(e)}
                
        # Circular imports check (reusing TraceCircularImportsCommand)
        if TraceCircularImportsCommand:
            try:
                cmd = TraceCircularImportsCommand()
                ci_res = cmd.execute(scan_path=abs_path)
                if ci_res.get("success"):
                    quality_info["circular_imports"] = {
                        "cycles_count": ci_res.get("cycles_count", 0),
                        "cycles": ci_res.get("cycles", [])
                    }
            except Exception as e:
                quality_info["circular_imports"] = {"error": str(e)}
                
        results["code_quality"] = quality_info
        
        # 6b. Build Check
        results["build_check"] = self._run_build_check(abs_path, stack)
        
        # 7. Large Files Check (>1MB)
        large_files = []
        scanned_files_count = 0
        for root, dirs, files in os.walk(abs_path):
            dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'dist', 'build', '.pytest_cache', '__pycache__', '.dropbox', '.dropbox.cache')]
            for f in files:
                scanned_files_count += 1
                if scanned_files_count > 5000:
                    break
                file_path = os.path.join(root, f)
                try:
                    f_size = os.path.getsize(file_path)
                    if f_size > 1024 * 1024:  # >1MB
                        large_files.append({
                            "path": os.path.relpath(file_path, abs_path),
                            "size_bytes": f_size
                        })
                except:
                    pass
            if scanned_files_count > 5000:
                break
        results["files"] = large_files
        
        # 8. Summary & Issues List
        issues = []
        score = 100
        
        # Stack issues
        if not stack:
            issues.append(("No known stack identified", "Could not identify standard Python/Node/Rust/PHP/C++ codebase configs.", "medium"))
            score -= 10
            
        # Git issues
        if not is_git:
            issues.append(("No Git repository", "Project is not version-controlled with Git.", "medium"))
            score -= 10
        elif isinstance(results["git"], dict) and not results["git"].get("clean", True):
            issues.append(("Uncommitted changes", "Git has modified or untracked changes.", "low"))
            score -= 5
            
        # Env issues
        if env_info["env_example_present"] and not env_info["env_file_present"]:
            issues.append(("Missing .env file", "A .env.example exists, but no local .env file was found.", "high"))
            score -= 15
            
        # Test issues
        if not results["tests"].get("detected", False):
            issues.append(("No tests found", "No unit test folders or configurations detected.", "medium"))
            score -= 10
        elif isinstance(results["tests"], dict) and results["tests"].get("execution", {}).get("status") == "failed":
            issues.append(("Tests failed", f"Unit tests execution failed in project.", "high"))
            score -= 15
            
        # Dead code / circular import issues
        if isinstance(quality_info["dead_code"], dict) and quality_info["dead_code"].get("dead_symbols_count", 0) > 0:
            count = quality_info["dead_code"]["dead_symbols_count"]
            issues.append(("Dead code detected", f"Found {count} unused functions or classes.", "low"))
            score -= 5
            
        if isinstance(quality_info["circular_imports"], dict) and quality_info["circular_imports"].get("cycles_count", 0) > 0:
            count = quality_info["circular_imports"]["cycles_count"]
            issues.append(("Circular imports detected", f"Found {count} circular dependency cycles in Python code.", "medium"))
            score -= 10
            
        # Lint / type check execution failure scoring
        if quality_info.get("lint_execution", {}).get("status") == "failed":
            issues.append(("Lint check failed", f"Linting rules violations found.", "medium"))
            score -= 5
            
        if quality_info.get("type_checking", {}).get("status") == "failed":
            issues.append(("Type checking failed", f"Static type checker reported errors.", "medium"))
            score -= 10
            
        # Build check failure scoring
        if isinstance(results["build_check"], dict) and results["build_check"].get("status") == "failed":
            issues.append(("Build failed", f"Project compilation / build command failed.", "high"))
            score -= 20
            
        # Large files issues
        if large_files:
            issues.append(("Large files present", f"Detected {len(large_files)} files exceeding 1MB in size.", "low"))
            score -= 5
            
        results["summary"] = {"health_score": max(0, min(100, score)), "issues": [{"title": title, "description": desc, "severity": sev} for title, desc, sev in issues]}
        
        return {
            "success": True,
            "message": "Project doctor diagnostics complete.",
            "details": results
        }
        
    def _run_lint_and_types(self, abs_path, files_in_root):
        lint_results = {"executed": False, "status": "skipped", "output": ""}
        type_results = {"executed": False, "status": "skipped", "output": ""}
        
        # Determine if node modules / npx is available
        has_npx = shutil.which("npx") or shutil.which("npx.cmd")
        
        # Check node project lint
        if "package.json" in files_in_root and has_npx:
            # Check eslint configuration presence
            has_eslint_config = any(f.startswith(".eslintrc") or "eslint.config" in f for f in files_in_root)
            if has_eslint_config:
                try:
                    res = subprocess.run(
                        ["npx", "eslint", ".", "--max-warnings", "0"],
                        cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15, shell=(os.name == 'nt')
                    )
                    lint_results = {
                        "executed": True,
                        "tool": "eslint",
                        "status": "passed" if res.returncode == 0 else "failed",
                        "output": res.stdout[:1000] + res.stderr[:500]
                    }
                except Exception as e:
                    lint_results = {"executed": True, "tool": "eslint", "status": "error", "output": str(e)}
            
            # Check tsconfig presence for typecheck
            if "tsconfig.json" in files_in_root:
                try:
                    res = subprocess.run(
                        ["npx", "tsc", "--noEmit"],
                        cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20, shell=(os.name == 'nt')
                    )
                    type_results = {
                        "executed": True,
                        "tool": "tsc",
                        "status": "passed" if res.returncode == 0 else "failed",
                        "output": res.stdout[:1000] + res.stderr[:500]
                    }
                except Exception as e:
                    type_results = {"executed": True, "tool": "tsc", "status": "error", "output": str(e)}
                    
        # Check Python lint
        elif "requirements.txt" in files_in_root or "pyproject.toml" in files_in_root:
            # Check for local venv flake8 or mypy
            venv_bin = os.path.join(abs_path, "venv", "Scripts") if os.name == 'nt' else os.path.join(abs_path, "venv", "bin")
            flake8_path = shutil.which("flake8", path=venv_bin) or shutil.which("flake8")
            mypy_path = shutil.which("mypy", path=venv_bin) or shutil.which("mypy")
            
            if flake8_path:
                try:
                    res = subprocess.run(
                        [flake8_path, "."],
                        cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15
                    )
                    lint_results = {
                        "executed": True,
                        "tool": "flake8",
                        "status": "passed" if res.returncode == 0 else "failed",
                        "output": res.stdout[:1000] + res.stderr[:500]
                    }
                except Exception as e:
                    lint_results = {"executed": True, "tool": "flake8", "status": "error", "output": str(e)}
                    
            if mypy_path:
                try:
                    res = subprocess.run(
                        [mypy_path, "."],
                        cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20
                    )
                    type_results = {
                        "executed": True,
                        "tool": "mypy",
                        "status": "passed" if res.returncode == 0 else "failed",
                        "output": res.stdout[:1000] + res.stderr[:500]
                    }
                except Exception as e:
                    type_results = {"executed": True, "tool": "mypy", "status": "error", "output": str(e)}
                    
        return lint_results, type_results
        
    def _run_tests(self, abs_path, test_folders, test_configs, stack):
        test_results = {"executed": False, "status": "skipped", "output": ""}
        
        # Check Python / pytest
        if "Python" in stack:
            venv_bin = os.path.join(abs_path, "venv", "Scripts") if os.name == 'nt' else os.path.join(abs_path, "venv", "bin")
            pytest_path = shutil.which("pytest", path=venv_bin) or shutil.which("pytest")
            if pytest_path:
                try:
                    res = subprocess.run(
                        [pytest_path, "-v"],
                        cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20
                    )
                    test_results = {
                        "executed": True,
                        "framework": "pytest",
                        "status": "passed" if res.returncode == 0 else "failed",
                        "output": res.stdout[:1000] + res.stderr[:500]
                    }
                except Exception as e:
                    test_results = {"executed": True, "framework": "pytest", "status": "error", "output": str(e)}
                    
        # Check Node.js / Jest or Vitest
        elif "Node.js/JavaScript" in stack or "TypeScript" in stack:
            has_npx = shutil.which("npx") or shutil.which("npx.cmd")
            if has_npx:
                # Detect framework from configs
                framework = "npm test"
                cmd = ["npm", "test"]
                is_npx_cmd = False
                
                # Check for vitest config
                has_vitest = any("vitest" in f for f in test_configs)
                has_jest = any("jest" in f for f in test_configs)
                
                if has_vitest:
                    framework = "vitest"
                    cmd = ["npx", "vitest", "run"]
                    is_npx_cmd = True
                elif has_jest:
                    framework = "jest"
                    cmd = ["npx", "jest", "--passWithNoTests"]
                    is_npx_cmd = True
                    
                try:
                    res = subprocess.run(
                        cmd,
                        cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30, shell=(os.name == 'nt' or not is_npx_cmd)
                    )
                    test_results = {
                        "executed": True,
                        "framework": framework,
                        "status": "passed" if res.returncode == 0 else "failed",
                        "output": res.stdout[:1000] + res.stderr[:500]
                    }
                except Exception as e:
                    test_results = {"executed": True, "framework": framework, "status": "error", "output": str(e)}
                    
        # Check Rust
        elif "Rust" in stack:
            try:
                res = subprocess.run(
                    ["cargo", "test"],
                    cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30
                )
                test_results = {
                    "executed": True,
                    "framework": "cargo test",
                    "status": "passed" if res.returncode == 0 else "failed",
                    "output": res.stdout[:1000] + res.stderr[:500]
                }
            except Exception as e:
                test_results = {"executed": True, "framework": "cargo test", "status": "error", "output": str(e)}
                
        # Check PHP / phpunit
        elif "PHP" in stack:
            phpunit_path = os.path.join(abs_path, "vendor", "bin", "phpunit")
            if not os.path.exists(phpunit_path):
                phpunit_path = shutil.which("phpunit")
            if phpunit_path:
                try:
                    res = subprocess.run(
                        [phpunit_path],
                        cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20
                    )
                    test_results = {
                        "executed": True,
                        "framework": "phpunit",
                        "status": "passed" if res.returncode == 0 else "failed",
                        "output": res.stdout[:1000] + res.stderr[:500]
                    }
                except Exception as e:
                    test_results = {"executed": True, "framework": "phpunit", "status": "error", "output": str(e)}
                    
        return test_results
        
    def _run_build_check(self, abs_path, stack):
        build_results = {"executed": False, "status": "skipped", "output": ""}
        
        if "Node.js/JavaScript" in stack or "TypeScript" in stack:
            pkg_json = os.path.join(abs_path, "package.json")
            if os.path.exists(pkg_json):
                # Check if build script exists
                try:
                    import json
                    with open(pkg_json, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if "build" in data.get("scripts", {}):
                        # Use pnpm or npm
                        cmd = ["pnpm", "run", "build"] if (shutil.which("pnpm") or shutil.which("pnpm.cmd")) else ["npm", "run", "build"]
                        res = subprocess.run(
                            cmd,
                            cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=40, shell=(os.name == 'nt')
                        )
                        build_results = {
                            "executed": True,
                            "command": " ".join(cmd),
                            "status": "passed" if res.returncode == 0 else "failed",
                            "output": res.stdout[:1000] + res.stderr[:500]
                        }
                except Exception as e:
                    build_results = {"executed": True, "status": "error", "output": str(e)}
                    
        elif "Rust" in stack:
            try:
                res = subprocess.run(
                    ["cargo", "build"],
                    cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=45
                )
                build_results = {
                    "executed": True,
                    "command": "cargo build",
                    "status": "passed" if res.returncode == 0 else "failed",
                    "output": res.stdout[:1000] + res.stderr[:500]
                }
            except Exception as e:
                build_results = {"executed": True, "command": "cargo build", "status": "error", "output": str(e)}
                
        return build_results
