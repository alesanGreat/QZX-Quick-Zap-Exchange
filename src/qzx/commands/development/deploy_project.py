#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DeployProject Command - Handles local/remote builds, remote backups, synchronization, restarts, health check, and rollback
"""

import os
import sys
import subprocess
import shutil
import urllib.request
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class DeployProjectCommand(CommandBase):
    """
    Command to build a project, create a remote backup, synchronize files via rsync/ssh,
    set permissions, reload services, run health checks, and roll back if they fail.
    """
    
    name = "deployProject"
    description = "Handles local build, remote backup, synchronization, permission setup, service reload, health check, and automatic rollback on failure"
    category = "development"
    requires_explicit_approval = True
    backup_target_parameter = "path"
    
    parameters = [
        {
            'name': 'target_host',
            'description': 'Target SSH host (e.g. deploy@5.161.246.120 or hostname)',
            'required': True
        },
        {
            'name': 'path',
            'description': 'Path to local project root directory (default: \'.\')',
            'required': False,
            'default': '.'
        },
        {
            'name': 'target_path',
            'description': 'Target path on remote host (e.g. /var/www/html/)',
            'required': True
        },
        {
            'name': 'port',
            'description': 'SSH Port (default: 22)',
            'required': False,
            'default': 22
        },
        {
            'name': 'ssh_key',
            'description': 'Path to SSH Private Key (optional)',
            'required': False,
            'default': None
        },
        {
            'name': 'health_url',
            'description': 'Health check URL (optional)',
            'required': False,
            'default': None
        },
        {
            'name': 'restart_cmd',
            'description': 'Remote command to restart service (e.g. nginx -s reload, pm2 restart all) (optional)',
            'required': False,
            'default': None
        },
        {
            'name': 'skip_build',
            'description': 'If True, skip running local build scripts (default: False)',
            'required': False,
            'default': False
        },
        {
            'name': 'dry_run',
            'description': 'If True, only show commands that would be executed without running them (default: True)',
            'required': False,
            'default': True,
            'type': 'bool'
        }
    ]
    
    examples = [
        {
            'command': 'qzx deployProject --target_host deploy@example.test --target_path /var/www/html/ --port 2237',
            'description': 'Previews deployment of the current workspace'
        },
        {
            'command': 'qzx deployProject --target_host deploy@host --target_path /var/www/html/ --health_url https://site.com --dry_run True',
            'description': 'Simulates project deployment with health check'
        },
        {
            'command': 'qzx deployProject --target_host deploy@host --target_path /var/www/html/ --dry_run false',
            'description': 'Backs up the local project and executes deployment'
        }
    ]
    
    def execute(self, target_host, target_path, path='.', port=22, ssh_key=None, health_url=None, restart_cmd=None, skip_build=False, dry_run=True):
        """
        Executes the deployment workflow
        """
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"Local path '{path}' does not exist.",
                "message": f"Local path '{path}' does not exist."
            }
            
        # Parse inputs
        if isinstance(skip_build, str):
            skip_build = skip_build.strip().lower() in ('true', '1', 'yes')
        if isinstance(dry_run, str):
            dry_run = dry_run.strip().lower() in ('true', '1', 'yes')
        port = int(port)
        
        results = {
            "build": "skipped",
            "backup_taken": "skipped",
            "synced": "skipped",
            "permissions_set": "skipped",
            "service_restarted": "skipped",
            "health_check": "skipped",
            "rollback_executed": "skipped",
            "dry_run_mode": dry_run,
            "summary": ""
        }
        
        # 1. Local Build
        if not skip_build:
            build_success = self._run_local_build(abs_path, dry_run)
            results["build"] = "success" if build_success else "failed"
            if not build_success and not dry_run:
                return {
                    "success": False,
                    "error": "Local build script failed.",
                    "message": "Local build failed. Aborting deployment.",
                    "details": results
                }
                
        # Resolve build/dist folder
        dist_dir = os.path.join(abs_path, "dist")
        if not os.path.exists(dist_dir):
            dist_dir = os.path.join(abs_path, "build")
        if not os.path.exists(dist_dir):
            dist_dir = abs_path # Fallback to path if no dist folder
            
        # Establish base SSH command options
        ssh_opts = ["-p", str(port)]
        if ssh_key:
            ssh_opts.extend(["-i", ssh_key])
            
        # 2. Remote Backup
        backup_name = f"backup_{int(time.time())}.tar.gz"
        remote_backup_path = f"/tmp/{backup_name}"
        backup_cmd = f"tar -czf {remote_backup_path} -C {target_path} . 2>/dev/null || true"
        
        if dry_run:
            results["backup_taken"] = "dry_run"
        else:
            try:
                # SSH to take remote backup
                res = subprocess.run(
                    ["ssh"] + ssh_opts + [target_host, backup_cmd],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=15,
                    check=False
                )
                if res.returncode == 0:
                    results["backup_taken"] = f"success: {remote_backup_path}"
                else:
                    results["backup_taken"] = "failed_or_empty_folder"
            except Exception as e:
                results["backup_taken"] = f"failed: {e}"
                
        # 3. Synchronization (using rsync/scp)
        sync_cmd = ["rsync", "-avz", "--delete"]
        if port != 22 or ssh_key:
            ssh_key_opt = f" -i {ssh_key}" if ssh_key else ""
            sync_cmd.extend(["-e", f"ssh -p {port}{ssh_key_opt}"])
        sync_cmd.extend([dist_dir.rstrip("/\\") + "/", f"{target_host}:{target_path}"])
        
        if dry_run:
            results["synced"] = "dry_run"
        else:
            try:
                res = subprocess.run(
                    sync_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=60,
                    check=False
                )
                if res.returncode == 0:
                    results["synced"] = "success"
                else:
                    return {
                        "success": False,
                        "error": f"Rsync synchronization failed with code {res.returncode}: {res.stderr}",
                        "message": "Asset synchronization failed.",
                        "details": results
                    }
            except Exception as e:
                results["synced"] = f"failed: {e}"
                return {
                    "success": False,
                    "error": str(e),
                    "message": "Asset synchronization failed.",
                    "details": results
                }
                
        # 4. Set Permissions
        perm_cmd = f"chmod -R 755 {target_path} 2>/dev/null || true"
        if dry_run:
            results["permissions_set"] = "dry_run"
        else:
            try:
                subprocess.run(
                    ["ssh"] + ssh_opts + [target_host, perm_cmd],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    check=False
                )
                results["permissions_set"] = "success"
            except:
                results["permissions_set"] = "failed"
                
        # 5. Restart Service
        if restart_cmd:
            if dry_run:
                results["service_restarted"] = "dry_run"
            else:
                try:
                    res = subprocess.run(
                        ["ssh"] + ssh_opts + [target_host, restart_cmd],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=15,
                        check=False
                    )
                    if res.returncode == 0:
                        results["service_restarted"] = "success"
                    else:
                        results["service_restarted"] = f"failed with code {res.returncode}: {res.stderr}"
                except Exception as e:
                    results["service_restarted"] = f"failed: {e}"
                    
        # 6. Health Check
        health_passed = True
        if health_url:
            if dry_run:
                results["health_check"] = "dry_run"
            else:
                # Poll health url up to 3 times
                health_passed = False
                for attempt in range(1, 4):
                    try:
                        req = urllib.request.Request(health_url, headers={'User-Agent': 'QZX-Deploy-Health-Check'})
                        with urllib.request.urlopen(req, timeout=5) as response:
                            if response.status >= 200 and response.status < 400:
                                results["health_check"] = f"passed on attempt {attempt}"
                                health_passed = True
                                break
                    except Exception as e:
                        time.sleep(2)
                if not health_passed:
                    results["health_check"] = "failed"
                    
        # 7. Automatic Rollback if Health Check failed
        if not health_passed and not dry_run and "success:" in results["backup_taken"]:
            # Rollback: tar -xzf backup -C target_path
            rollback_cmd = f"rm -rf {target_path}/* && tar -xzf {remote_backup_path} -C {target_path}"
            try:
                res = subprocess.run(
                    ["ssh"] + ssh_opts + [target_host, rollback_cmd],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30,
                    check=False
                )
                if res.returncode == 0:
                    results["rollback_executed"] = "success"
                else:
                    results["rollback_executed"] = f"failed to extract backup: {res.stderr}"
            except Exception as e:
                results["rollback_executed"] = f"failed: {e}"
                
            # Restart service again after rollback
            if restart_cmd:
                try:
                    subprocess.run(
                        ["ssh"] + ssh_opts + [target_host, restart_cmd],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=15,
                        check=False
                    )
                except:
                    pass
                    
            return {
                "success": False,
                "error": "Health check failed. Automatic rollback executed.",
                "message": "Deployment failed health checks. Rollback completed.",
                "details": results
            }
            
        summary_msg = "Project deployed successfully."
        if dry_run:
            summary_msg += " (Dry Run mode)"
        results["summary"] = summary_msg
        
        return {
            "success": True,
            "message": summary_msg,
            "details": results
        }
        
    def _run_local_build(self, local_path, dry_run):
        files = os.listdir(local_path)
        build_script = None
        if "package.json" in files:
            build_script = ["pnpm", "run", "build:deploy"]
            # Fallback to npm if pnpm is not found
            if not shutil.which("pnpm") and not shutil.which("pnpm.cmd"):
                build_script = ["npm", "run", "build"]
        elif "Cargo.toml" in files:
            build_script = ["cargo", "build", "--release"]
            
        if not build_script:
            return True # No build needed
            
        if dry_run:
            return True
            
        try:
            res = subprocess.run(
                build_script,
                cwd=local_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=(os.name == 'nt'), # Use shell on Windows for npm/pnpm.cmd
                check=False
            )
            return res.returncode == 0
        except:
            return False
