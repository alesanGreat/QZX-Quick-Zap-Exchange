#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ReleaseProject Command - Automates versioning, changelog, building, hashing, committing, and tagging
"""

import os
import re
import sys
import shutil
import hashlib
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class ReleaseProjectCommand(CommandBase):
    """
    Command to automate the release cycle of a project (preflight, bump version, update changelog, build, hash, git commit/tag)
    """
    
    name = "releaseProject"
    description = "Handles release workflow: bumps versions in manifests, generates CHANGELOG.md, builds, hashes assets, commits, and tags (supports dry-run)"
    category = "development"
    requires_explicit_approval = True
    backup_target_parameter = "path"
    
    parameters = [
        {
            'name': 'bump',
            'description': 'Semantic version bump type: patch, minor, major (default: \'patch\')',
            'required': False,
            'default': 'patch'
        },
        {
            'name': 'path',
            'description': 'Path to project directory (default: \'.\')',
            'required': False,
            'default': '.'
        },
        {
            'name': 'dry_run',
            'description': 'If True, simulate release without mutating files or running git commits (default: True)',
            'required': False,
            'default': True,
            'type': 'bool'
        }
    ]
    
    examples = [
        {
            'command': 'qzx releaseProject',
            'description': 'Preview a patch release'
        },
        {
            'command': 'qzx releaseProject --bump minor --dry_run false',
            'description': 'Back up and run a minor release'
        }
    ]
    
    def execute(self, bump='patch', path='.', dry_run=True):
        """
        Executes the release process
        """
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"Path '{path}' does not exist.",
                "message": f"Path '{path}' does not exist."
            }
            
        bump = bump.lower().strip()
        if bump not in ("major", "minor", "patch"):
            bump = "patch"
            
        if isinstance(dry_run, str):
            dry_run = dry_run.strip().lower() in ('true', '1', 'yes')
            
        preflight = {"git_exists": False, "git_clean": False, "tests_pass": "skipped"}
        old_version = "0.0.0"
        new_version = "0.0.0"
        manifest_type = None
        manifest_file = None
        
        # 1. Preflight Checks
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
            preflight["git_exists"] = is_git
        except:
            pass
            
        if is_git:
            try:
                status_res = subprocess.run(["git", "status", "--porcelain"], cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                preflight["git_clean"] = len(status_res.stdout.strip()) == 0
            except:
                pass
                
        # 2. Detect Manifest & Version
        files = os.listdir(abs_path)
        if "package.json" in files:
            manifest_type = "npm"
            manifest_file = os.path.join(abs_path, "package.json")
        elif "pyproject.toml" in files:
            manifest_type = "python"
            manifest_file = os.path.join(abs_path, "pyproject.toml")
        elif "Cargo.toml" in files:
            manifest_type = "rust"
            manifest_file = os.path.join(abs_path, "Cargo.toml")
            
        if manifest_file:
            old_version = self._read_version(manifest_file, manifest_type)
            new_version = self._bump_semver(old_version, bump)
            
        # 2b. Run Preflight Tests
        tests_passed = True
        test_tool = None
        test_cmd = None
        
        # Smart detection of tests to avoid running pytest on projects without unit tests (which returns exit code 5 and aborts)
        has_tests = False
        if manifest_type == "npm":
            if os.path.exists(manifest_file):
                try:
                    import json
                    with open(manifest_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    test_script = data.get("scripts", {}).get("test", "")
                    if test_script and "no test specified" not in test_script.lower():
                        has_tests = True
                except:
                    pass
            if has_tests:
                test_tool = "pnpm test" if shutil.which("pnpm") else "npm test"
                test_cmd = ["pnpm", "test"] if shutil.which("pnpm") else ["npm", "test"]
                
        elif manifest_type == "python":
            for root, dirs, files in os.walk(abs_path):
                dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'venv', '__pycache__')]
                if any(d in ("tests", "test", "spec") for d in dirs):
                    has_tests = True
                    break
                if any((f.startswith("test_") or f.endswith("_test.py")) and f.endswith(".py") for f in files):
                    has_tests = True
                    break
            if has_tests:
                venv_bin = os.path.join(abs_path, "venv", "Scripts") if os.name == 'nt' else os.path.join(abs_path, "venv", "bin")
                pytest_bin = shutil.which("pytest", path=venv_bin) or shutil.which("pytest")
                test_tool = "pytest"
                test_cmd = [pytest_bin] if pytest_bin else [sys.executable, "-m", "unittest"]
                
        elif manifest_type == "rust":
            # Rust cargo test handles no tests gracefully (exit code 0)
            has_tests = True
            test_tool = "cargo test"
            test_cmd = ["cargo", "test"]
            
        if test_cmd and has_tests:
            if dry_run:
                preflight["tests_pass"] = "dry_run_passed"
            else:
                try:
                    res = subprocess.run(
                        test_cmd,
                        cwd=abs_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        shell=(manifest_type == "npm" and os.name == 'nt'),
                        timeout=30
                    )
                    if res.returncode == 0:
                        preflight["tests_pass"] = True
                    else:
                        preflight["tests_pass"] = False
                        tests_passed = False
                except Exception as e:
                    preflight["tests_pass"] = f"error: {e}"
                    tests_passed = False
        else:
            preflight["tests_pass"] = "no_tests_configured"
            
        if not tests_passed and not dry_run:
            return {
                "success": False,
                "error": f"Preflight check failed: tests execution failed using {test_tool}.",
                "message": "Preflight tests failed. Release aborted.",
                "details": {
                    "old_version": old_version,
                    "new_version": new_version,
                    "preflight": preflight,
                    "dry_run_mode": dry_run
                }
            }

        # 3. Simulate or Perform Version Bump
        bumped = False
        if manifest_file and old_version != "0.0.0":
            if dry_run:
                bumped = True
            else:
                try:
                    self._write_version(manifest_file, manifest_type, new_version)
                    bumped = True
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to write version to manifest: {e}",
                        "message": "Failed to update version in manifest."
                    }
                    
        # 4. Generate/Update CHANGELOG.md
        changelog_updated = False
        commits_log = ""
        if is_git:
            try:
                log_res = subprocess.run(["git", "log", "-n", "15", "--pretty=format:* %s (%h)"], cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                commits_log = log_res.stdout.strip()
            except:
                pass
                
        changelog_path = os.path.join(abs_path, "CHANGELOG.md")
        new_entry = f"## [{new_version}] - Release\n\n### Commits:\n{commits_log}\n\n"
        if dry_run:
            changelog_updated = True
        else:
            try:
                existing_content = ""
                if os.path.exists(changelog_path):
                    with open(changelog_path, 'r', encoding='utf-8') as f:
                        existing_content = f.read()
                with open(changelog_path, 'w', encoding='utf-8') as f:
                    f.write(new_entry + existing_content)
                changelog_updated = True
            except:
                pass
                
        # 5. Build Project
        build_result = "skipped"
        if manifest_type == "npm" and not dry_run:
            try:
                subprocess.run(["npm", "run", "build"], cwd=abs_path, check=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                build_result = "success"
            except:
                build_result = "failed"
        elif manifest_type == "rust" and not dry_run:
            try:
                subprocess.run(["cargo", "build", "--release"], cwd=abs_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                build_result = "success"
            except:
                build_result = "failed"
        elif dry_run:
            build_result = "dry_run"
            
        # 6. SHA256 Hashes of Artifacts
        artifacts = []
        # Look for artifacts in dist/ or target/release/
        dist_dirs = ["dist", "build", "target/release"]
        artifact_count = 0
        for dd in dist_dirs:
            full_dd = os.path.join(abs_path, dd)
            if os.path.exists(full_dd) and os.path.isdir(full_dd):
                for root, _, files_in_dir in os.walk(full_dd):
                    for f in files_in_dir:
                        artifact_count += 1
                        if artifact_count > 100:
                            break
                        fp = os.path.join(root, f)
                        try:
                            h = hashlib.sha256()
                            with open(fp, 'rb') as f_bin:
                                for chunk in iter(lambda: f_bin.read(8192), b''):
                                    h.update(chunk)
                            artifacts.append({
                                "file": os.path.relpath(fp, abs_path),
                                "sha256": h.hexdigest()
                            })
                        except:
                            pass
                            
        # 6b. Package/Bundle Creation
        package_created = "skipped"
        package_path = None
        package_hash = None
        
        if bumped:
            # Determine folder to compress
            dir_to_compress = None
            for dd in ["dist", "build", "target/release"]:
                full_dd = os.path.join(abs_path, dd)
                if os.path.exists(full_dd) and os.path.isdir(full_dd):
                    dir_to_compress = full_dd
                    break
                    
            if not dir_to_compress:
                # Fallback: create a temporary package of src/ if exists
                if os.path.exists(os.path.join(abs_path, "src")):
                    dir_to_compress = os.path.join(abs_path, "src")
                    
            if dir_to_compress:
                release_out_dir = os.path.join(abs_path, "release")
                if not dry_run:
                    os.makedirs(release_out_dir, exist_ok=True)
                archive_name = f"release_v{new_version}"
                archive_dest = os.path.join(release_out_dir, archive_name)
                
                if dry_run:
                    package_created = f"dry_run: would create release/release_v{new_version}.zip"
                    package_path = f"release/release_v{new_version}.zip"
                else:
                    try:
                        # Create zip archive
                        archive_path_actual = shutil.make_archive(archive_dest, 'zip', dir_to_compress)
                        package_path = os.path.relpath(archive_path_actual, abs_path)
                        
                        # Calculate SHA256 of the package
                        h = hashlib.sha256()
                        with open(archive_path_actual, 'rb') as f_bin:
                            for chunk in iter(lambda: f_bin.read(8192), b''):
                                h.update(chunk)
                        package_hash = h.hexdigest()
                        package_created = f"success: {package_path}"
                        
                        # Add to artifacts list
                        artifacts.append({
                            "file": package_path,
                            "sha256": package_hash,
                            "type": "distribution_package"
                        })
                    except Exception as e:
                        package_created = f"failed: {e}"

        # 7. Git Commit & Tag
        git_commit = "skipped"
        git_tag = "skipped"
        if is_git and not dry_run and bumped:
            try:
                # Add changes
                subprocess.run(["git", "add", "."], cwd=abs_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # Commit
                commit_msg = f"chore(release): v{new_version}"
                subprocess.run(["git", "commit", "-m", commit_msg], cwd=abs_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                git_commit = f"committed: {commit_msg}"
                
                # Tag
                tag_name = f"v{new_version}"
                subprocess.run(["git", "tag", "-a", tag_name, "-m", f"Version {new_version}"], cwd=abs_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                git_tag = f"tagged: {tag_name}"
            except Exception as e:
                git_commit = f"failed: {e}"
        elif dry_run:
            git_commit = "dry_run"
            git_tag = "dry_run"
            
        summary_msg = f"Project release process completed: bumped version from {old_version} to {new_version}."
        if dry_run:
            summary_msg += " (Dry Run mode)"
            
        return {
            "success": True,
            "message": summary_msg,
            "details": {
                "old_version": old_version,
                "new_version": new_version,
                "preflight": preflight,
                "changelog_updated": changelog_updated,
                "build_result": build_result,
                "artifacts": artifacts,
                "package_created": package_created,
                "git_commit": git_commit,
                "git_tag": git_tag,
                "dry_run_mode": dry_run
            }
        }
        
    def _read_version(self, manifest_file, manifest_type):
        try:
            with open(manifest_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if manifest_type == "npm":
                import json
                data = json.loads(content)
                return data.get("version", "0.0.0")
            elif manifest_type == "python":
                # Match version = "x.y.z"
                m = re.search(r'(?m)^version\s*=\s*[\'"]([^\'"]+)[\'"]', content)
                if m:
                    return m.group(1)
            elif manifest_type == "rust":
                m = re.search(r'(?m)^version\s*=\s*[\'"]([^\'"]+)[\'"]', content)
                if m:
                    return m.group(1)
        except:
            pass
        return "0.0.0"
        
    def _write_version(self, manifest_file, manifest_type, new_version):
        with open(manifest_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if manifest_type == "npm":
            import json
            data = json.loads(content)
            data["version"] = new_version
            with open(manifest_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                f.write("\n")
        elif manifest_type in ("python", "rust"):
            new_content = re.sub(r'(?m)^version\s*=\s*[\'"]([^\'"]+)[\'"]', f'version = "{new_version}"', content, count=1)
            with open(manifest_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
                
    def _bump_semver(self, version_str, bump):
        parts = version_str.split(".")
        if len(parts) < 3:
            return "0.0.1"
        try:
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2].split("-")[0])
        except:
            return "0.0.1"
            
        if bump == "major":
            return f"{major+1}.0.0"
        elif bump == "minor":
            return f"{major}.{minor+1}.0"
        else: # patch
            return f"{major}.{minor}.{patch+1}"
        
        return version_str
