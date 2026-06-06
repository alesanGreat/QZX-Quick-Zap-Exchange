#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetGitStatus Command - Retrieves structured Git repository status and recent history
"""

import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class GetGitStatusCommand(CommandBase):
    """
    Command to retrieve comprehensive, structured information about a Git repository
    """
    
    name = "getGitStatus"
    description = "Provides a structured summary of the Git repository state (branch, remote, changes, recent commits)"
    category = "development"
    
    parameters = [
        {
            'name': 'repo_path',
            'description': 'Path to the directory to scan (defaults to the current working directory)',
            'required': False,
            'default': '.'
        }
    ]
    
    examples = [
        {
            'command': 'qzx getGitStatus',
            'description': 'Show git status for the current directory'
        },
        {
            'command': 'qzx getGitStatus C:/some/path',
            'description': 'Show git status for the repository at C:/some/path'
        }
    ]
    
    def execute(self, repo_path='.'):
        """
        Retrieves Git repository details and status
        
        Args:
            repo_path (str): The path to check
            
        Returns:
            Dictionary containing Git status data
        """
        abs_path = os.path.abspath(repo_path)
        
        # Verify path exists
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"Path '{repo_path}' does not exist.",
                "message": f"Path '{repo_path}' does not exist."
            }
            
        # Verify it's a directory
        if not os.path.isdir(abs_path):
            return {
                "success": False,
                "error": f"'{repo_path}' is not a directory. Git status requires a directory path.",
                "message": f"'{repo_path}' is not a directory."
            }

        # Check if git is installed/available
        try:
            subprocess.run(["git", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            return {
                "success": False,
                "error": "Git is not installed or not available in the system PATH.",
                "message": "Git is not available on this system."
            }
            
        # Check if it's inside a Git worktree
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
        except Exception as e:
            is_git = False
            
        if not is_git:
            return {
                "success": True,
                "is_git_repository": False,
                "repo_path": abs_path,
                "message": f"Directory '{abs_path}' is not a Git repository."
            }
            
        try:
            # 1. Get current branch name
            branch_name = self._run_git(["git", "branch", "--show-current"], abs_path)
            if not branch_name:
                branch_name = self._run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"], abs_path)
            
            # 2. Get tracking branch name (upstream)
            tracking_branch = self._run_git(
                ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                abs_path
            )
            
            # 3. Get ahead/behind counts if tracking branch exists
            ahead = 0
            behind = 0
            if tracking_branch:
                counts = self._run_git(
                    ["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"],
                    abs_path
                )
                if counts and "\t" in counts:
                    parts = counts.split("\t")
                    if len(parts) == 2:
                        try:
                            ahead = int(parts[0])
                            behind = int(parts[1])
                        except ValueError:
                            pass
            
            # 4. Get changes (status porcelain)
            changes_output = self._run_git(["git", "status", "--porcelain"], abs_path, split_lines=True)
            
            staged = []
            modified = []
            untracked = []
            deleted = []
            renamed = []
            
            for line in changes_output:
                if len(line) < 4:
                    continue
                status_code = line[:2]
                file_name = line[3:]
                
                # Check status codes:
                # X = status of staging index (staged changes)
                # Y = status of working tree (unstaged changes)
                # For porcelain, status_code is XY
                x, y = status_code[0], status_code[1]
                
                # If staged (X is not space, and X is not '?')
                if x in ('M', 'A', 'D', 'R', 'C') and x != ' ':
                    if x == 'R':
                        staged.append(file_name)  # renamed
                    else:
                        staged.append(file_name)
                
                # If unstaged (Y is not space, or X/Y are '??' or '!!')
                if y in ('M', 'D') and y != ' ':
                    if y == 'M':
                        modified.append(file_name)
                    elif y == 'D':
                        deleted.append(file_name)
                elif status_code == '??':
                    untracked.append(file_name)
                elif status_code == '!!':
                    # Ignored files, normally skipped or counted separately
                    pass
                elif x == 'D' and y == ' ':
                    # Staged deletion
                    deleted.append(file_name)
                elif x == ' ' and y == 'D':
                    # Unstaged deletion
                    deleted.append(file_name)
            
            # Deduplicate just in case files are in both lists (e.g. modified and staged)
            # We want to represent actual counts and items accurately.
            
            # 5. Get remote URLs
            remotes_output = self._run_git(["git", "remote", "-v"], abs_path, split_lines=True)
            remotes = {}
            for line in remotes_output:
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    url = parts[1]
                    purpose = parts[2].strip("()") if len(parts) >= 3 else "fetch"
                    if name not in remotes:
                        remotes[name] = {}
                    remotes[name][purpose] = url
            
            # 6. Get recent commits (last 5)
            log_output = self._run_git(
                ["git", "log", "-n", "5", "--pretty=format:%h|%an|%ad|%s", "--date=short"],
                abs_path,
                split_lines=True
            )
            recent_commits = []
            for line in log_output:
                parts = line.split("|", 3)
                if len(parts) == 4:
                    recent_commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "subject": parts[3]
                    })
            
            # Formulate description message
            message = f"Git Repository Status for '{abs_path}':\n"
            message += f"- Branch: {branch_name or 'Detached HEAD'}\n"
            if tracking_branch:
                message += f"- Tracking: {tracking_branch} (Ahead: {ahead}, Behind: {behind})\n"
            else:
                message += "- Tracking: None\n"
            message += f"- Uncommitted Changes: Staged={len(staged)}, Modified={len(modified)}, Untracked={len(untracked)}, Deleted={len(deleted)}\n"
            if recent_commits:
                message += f"- Latest Commit: [{recent_commits[0]['hash']}] {recent_commits[0]['subject']} by {recent_commits[0]['author']} ({recent_commits[0]['date']})"
            
            return {
                "success": True,
                "is_git_repository": True,
                "repo_path": abs_path,
                "branch": branch_name,
                "tracking_branch": tracking_branch or None,
                "sync_status": {
                    "ahead": ahead,
                    "behind": behind,
                    "in_sync": (ahead == 0 and behind == 0) if tracking_branch else True
                },
                "changes": {
                    "staged": staged,
                    "modified": modified,
                    "untracked": untracked,
                    "deleted": deleted,
                    "renamed": renamed
                },
                "changes_summary": {
                    "staged_count": len(staged),
                    "modified_count": len(modified),
                    "untracked_count": len(untracked),
                    "deleted_count": len(deleted),
                    "total_changes": len(staged) + len(modified) + len(untracked) + len(deleted)
                },
                "remotes": remotes,
                "recent_commits": recent_commits,
                "message": message
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to retrieve git status: {str(e)}"
            }
            
    def _run_git(self, cmd, cwd, split_lines=False):
        """Helper to run a git command and return its stdout"""
        try:
            res = subprocess.run(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            if res.returncode != 0:
                return [] if split_lines else ""
            
            if split_lines:
                return [line.rstrip('\r\n') for line in res.stdout.splitlines() if line.strip()]
            return res.stdout.strip()
        except Exception:
            return [] if split_lines else ""
