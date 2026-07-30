#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
RepairWorkspace Command - Cleans and reorganizes a development workspace
"""

import os
import sys
import shutil
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class RepairWorkspaceCommand(CommandBase):
    """
    Command to clean and reorganize workspaces, identifying and removing caches, temp files, and duplicate assets safely.
    """
    
    name = "repairWorkspace"
    description = "Scans, reorganizes, and cleans temporary files, build directories, binary artifacts, and duplicate files. (Safe dry-run by default)"
    category = "file"
    requires_explicit_approval = True
    backup_target_parameter = "path"
    
    parameters = [
        {
            'name': 'path',
            'description': 'Directory path to scan and clean (default: \'.\')',
            'required': False,
            'default': '.'
        },
        {
            'name': 'dry_run',
            'description': 'If True, only show what would be done without modifying any files (default: True)',
            'required': False,
            'default': True
        },
        {
            'name': 'categories',
            'description': 'List of categories to clean: build, temp, artifacts, duplicates, reorganizations (default: all)',
            'required': False,
            'default': 'build,temp,artifacts,duplicates,reorganizations'
        },
        {
            'name': 'apply',
            'description': 'Must be True alongside dry_run=False to actually delete/modify files (default: False)',
            'required': False,
            'default': False
        }
    ]
    
    examples = [
        {
            'command': 'qzx repairWorkspace',
            'description': 'Scan the workspace for build directories, temp files, duplicates, and reorganizations (dry-run)'
        },
        {
            'command': 'qzx repairWorkspace --dry_run False --apply True',
            'description': 'Actually delete/clean and reorganize the detected files'
        }
    ]
    
    def execute(self, path='.', dry_run=True, categories='build,temp,artifacts,duplicates,reorganizations', apply=False):
        """
        Executes the workspace repair/cleanup logic
        """
        # Parse inputs
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"Path '{path}' does not exist.",
                "message": f"Path '{path}' does not exist."
            }
            
        # Parse booleans
        if isinstance(dry_run, str):
            dry_run = dry_run.strip().lower() in ('true', '1', 'yes')
        if isinstance(apply, str):
            apply = apply.strip().lower() in ('true', '1', 'yes')
            
        # Actual modification occurs ONLY if dry_run=False AND apply=True
        is_dry_run = dry_run or not apply
        
        # Parse categories
        if isinstance(categories, str):
            cats = [c.strip().lower() for c in categories.split(",") if c.strip()]
        elif isinstance(categories, list):
            cats = [c.strip().lower() for c in categories]
        else:
            cats = ['build', 'temp', 'artifacts', 'duplicates', 'reorganizations']
            
        results = {
            "scanned_files": 0,
            "categories": {
                "build": [],
                "temp": [],
                "artifacts": [],
                "duplicates": [],
                "reorganizations": []
            },
            "space_recoverable_bytes": 0,
            "actions_proposed": [],
            "actions_applied": [],
            "dry_run_mode": is_dry_run,
            "summary": ""
        }
        
        # Scanners
        build_dirs = {'dist', 'build', 'target', '.next', '__pycache__', '.pytest_cache', '.sass-cache', 'out'}
        build_exts = {'.pyc', '.pyo', '.pyd', '.class'}
        temp_exts = {'.tmp', '.log', '.bak', '.swp', '.temp'}
        artifact_exts = {'.o', '.obj', '.so', '.dylib', '.dll', '.exe', '.a', '.lib'}
        
        found_files_hash = {}
        scanned_count = 0
        space_recoverable = 0
        
        # Walk directory tree safely
        for root, dirs, files in os.walk(abs_path):
            # Ignore VCS and dependency folders
            dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '.dropbox', '.dropbox.cache')]
            
            # 1. Build directories check
            if 'build' in cats:
                for d in list(dirs):
                    if d in build_dirs:
                        dir_path = os.path.join(root, d)
                        # Calculate directory size
                        dir_size = 0
                        for r_sub, _, f_sub in os.walk(dir_path):
                            for fs in f_sub:
                                try:
                                    dir_size += os.path.getsize(os.path.join(r_sub, fs))
                                except:
                                    pass
                        
                        rel_dir = os.path.relpath(dir_path, abs_path).replace('\\', '/')
                        results["categories"]["build"].append({
                            "type": "directory",
                            "path": rel_dir,
                            "size_bytes": dir_size
                        })
                        space_recoverable += dir_size
                        results["actions_proposed"].append(f"Delete directory: {rel_dir}")
                        
                        # Remove directory from dirs so os.walk doesn't descend into it
                        dirs.remove(d)
                        
            # 2. Files scan
            for f in files:
                scanned_count += 1
                if scanned_count > 15000:  # Safety limit
                    break
                    
                file_path = os.path.join(root, f)
                rel_file = os.path.relpath(file_path, abs_path).replace('\\', '/')
                
                try:
                    f_size = os.path.getsize(file_path)
                except:
                    continue
                    
                _, ext = os.path.splitext(f)
                ext = ext.lower()
                
                # Check build files
                if 'build' in cats and ext in build_exts:
                    results["categories"]["build"].append({
                        "type": "file",
                        "path": rel_file,
                        "size_bytes": f_size
                    })
                    space_recoverable += f_size
                    results["actions_proposed"].append(f"Delete file: {rel_file}")
                    
                # Check temp files
                elif 'temp' in cats and (ext in temp_exts or f.endswith('~')):
                    results["categories"]["temp"].append({
                        "type": "file",
                        "path": rel_file,
                        "size_bytes": f_size
                    })
                    space_recoverable += f_size
                    results["actions_proposed"].append(f"Delete file: {rel_file}")
                    
                # Check compiled artifacts
                elif 'artifacts' in cats and ext in artifact_exts:
                    # Don't delete exe in the root directory easily if it might be an installer,
                    # but if it is deep in src or build folders, flag it.
                    results["categories"]["artifacts"].append({
                        "type": "file",
                        "path": rel_file,
                        "size_bytes": f_size
                    })
                    space_recoverable += f_size
                    results["actions_proposed"].append(f"Delete file: {rel_file}")
                    
                # Duplicate check by content/name similarity
                if 'duplicates' in cats and f_size < 10 * 1024 * 1024:  # under 10MB to be fast
                    # Duplicate pattern check in name
                    lower_name = f.lower()
                    has_dup_pattern = any(p in lower_name for p in [" (1)", " - copy", "_backup", "_copy"])
                    
                    try:
                        file_hash = self._get_sha256(file_path)
                        matching_original = next(
                            (
                                original_rel
                                for original_rel, original_path
                                in found_files_hash.get(file_hash, [])
                                if self._files_identical(file_path, original_path)
                            ),
                            None,
                        )

                        if matching_original is not None:
                            orig_path = matching_original
                            results["categories"]["duplicates"].append({
                                "file": rel_file,
                                "duplicate_of": orig_path,
                                "size_bytes": f_size,
                                "sha256": file_hash,
                                "reason": "sha256_and_byte_match"
                            })
                            space_recoverable += f_size
                            results["actions_proposed"].append(
                                "Delete duplicate file (SHA-256 and exact byte "
                                f"match): {rel_file} (Original: {orig_path})"
                            )
                        elif has_dup_pattern:
                            # Potential copy based on filename
                            results["categories"]["duplicates"].append({
                                "file": rel_file,
                                "size_bytes": f_size,
                                "reason": "filename_pattern"
                            })
                            results["actions_proposed"].append(f"Review potential copy: {rel_file}")
                        else:
                            found_files_hash.setdefault(file_hash, []).append(
                                (rel_file, file_path)
                            )
                    except:
                        pass
                
                # Check reorganizations (env outside root, uppercase extension, spaces in name)
                if 'reorganizations' in cats:
                    # 1. .env outside root
                    if f == '.env' and os.path.abspath(root) != os.path.abspath(abs_path):
                        new_rel = '.env'
                        results["categories"]["reorganizations"].append({
                            "type": "move",
                            "from_path": rel_file,
                            "to_path": new_rel,
                            "reason": "env_outside_root",
                            "old_name": f,
                            "new_name": f
                        })
                        results["actions_proposed"].append(f"Move .env file: {rel_file} -> {new_rel}")
                    
                    else:
                        name_part, ext_part = os.path.splitext(f)
                        has_spaces = ' ' in f
                        has_upper_ext = ext_part != ext_part.lower() and ext_part != ''
                        
                        if has_spaces or has_upper_ext:
                            clean_name = f.replace(' ', '_')
                            clean_ext = ext_part.lower()
                            clean_name_part, _ = os.path.splitext(clean_name)
                            new_name = clean_name_part + clean_ext
                            
                            if new_name != f:
                                rel_dir = os.path.relpath(root, abs_path).replace('\\', '/')
                                if rel_dir == '.':
                                    new_rel = new_name
                                else:
                                    new_rel = f"{rel_dir}/{new_name}"
                                
                                reason = []
                                if has_spaces: reason.append("spaces_in_name")
                                if has_upper_ext: reason.append("uppercase_extension")
                                
                                results["categories"]["reorganizations"].append({
                                    "type": "rename",
                                    "from_path": rel_file,
                                    "to_path": new_rel,
                                    "reason": ",".join(reason),
                                    "old_name": f,
                                    "new_name": new_name
                                })
                                results["actions_proposed"].append(f"Rename/Move file: {rel_file} -> {new_rel} (Reason: {','.join(reason)})")
            
            if scanned_count > 15000:
                break
                
        results["scanned_files"] = scanned_count
        results["space_recoverable_bytes"] = space_recoverable
        
        # Apply actions if not dry run
        if not is_dry_run:
            # First reorganizations
            if 'reorganizations' in cats:
                for item in results["categories"]["reorganizations"]:
                    from_path = os.path.normpath(os.path.join(abs_path, item["from_path"]))
                    to_path = os.path.normpath(os.path.join(abs_path, item["to_path"]))
                    
                    if os.path.exists(from_path):
                        try:
                            # Handle case-insensitive renaming
                            if os.path.abspath(from_path).lower() == os.path.abspath(to_path).lower():
                                temp_path = from_path + ".tmp_rename"
                                while os.path.exists(temp_path):
                                    temp_path += "_"
                                os.rename(from_path, temp_path)
                                os.rename(temp_path, to_path)
                            else:
                                os.makedirs(os.path.dirname(to_path), exist_ok=True)
                                shutil.move(from_path, to_path)
                            
                            # Update references in code/config
                            self._update_references(abs_path, item["from_path"], item["to_path"], item["old_name"], item["new_name"])
                            results["actions_applied"].append(f"Moved/Renamed: {item['from_path']} -> {item['to_path']}")
                        except Exception as e:
                            results["actions_applied"].append(f"Failed to move/rename {item['from_path']}: {e}")

            # 1. Delete files
            for cat_name, items in results["categories"].items():
                if cat_name == "reorganizations":
                    continue
                for item in items:
                    if item.get("type") == "file" or "file" in item:
                        item_path = item.get("path") or item.get("file")
                        full_item_path = os.path.join(abs_path, item_path)
                        # Skip if it is duplicate entry classified as filename_pattern (needs manual review)
                        if item.get("reason") == "filename_pattern":
                            results["actions_applied"].append(f"Skipped manual review item: {item_path}")
                            continue
                            
                        if os.path.exists(full_item_path):
                            try:
                                os.remove(full_item_path)
                                results["actions_applied"].append(f"Deleted file: {item_path}")
                            except Exception as e:
                                results["actions_applied"].append(f"Failed to delete file {item_path}: {e}")
                                
            # 2. Delete directories
            for item in results["categories"]["build"]:
                if item.get("type") == "directory":
                    item_path = item.get("path")
                    full_item_path = os.path.join(abs_path, item_path)
                    if os.path.exists(full_item_path):
                        try:
                            shutil.rmtree(full_item_path)
                            results["actions_applied"].append(f"Deleted directory: {item_path}")
                        except Exception as e:
                            results["actions_applied"].append(f"Failed to delete directory {item_path}: {e}")
                            
            results["summary"] = f"Workspace cleaned. Recovered {space_recoverable} bytes."
        else:
            results["summary"] = f"Dry run complete. Found potential {space_recoverable} bytes recoverable across build/temp/artifacts/duplicates."
            if 'reorganizations' in cats:
                results["summary"] += f" Also detected {len(results['categories']['reorganizations'])} reorganization items."
            
        return {
            "success": True,
            "message": "Workspace cleanup scanning complete.",
            "details": results
        }

    @staticmethod
    def _get_sha256(file_path):
        """Compute a SHA-256 candidate digest for duplicate detection."""
        content_hash = hashlib.sha256()
        with open(file_path, "rb") as source:
            for chunk in iter(lambda: source.read(65536), b""):
                content_hash.update(chunk)
        return content_hash.hexdigest()

    @staticmethod
    def _files_identical(first_path, second_path):
        """Require an exact byte match before proposing duplicate deletion."""
        if os.path.getsize(first_path) != os.path.getsize(second_path):
            return False
        with open(first_path, "rb") as first, open(second_path, "rb") as second:
            while True:
                first_chunk = first.read(65536)
                second_chunk = second.read(65536)
                if first_chunk != second_chunk:
                    return False
                if not first_chunk:
                    return True

    def _update_references(self, abs_path, old_rel_path, new_rel_path, old_name, new_name):
        """
        Scans files in the workspace and updates references from old_rel_path/old_name to new_rel_path/new_name.
        """
        old_rel_forward = old_rel_path.replace('\\', '/')
        new_rel_forward = new_rel_path.replace('\\', '/')
        old_rel_back = old_rel_path.replace('/', '\\')
        new_rel_back = new_rel_path.replace('/', '\\')
        
        # Basenames without extensions (useful for Python imports and module names)
        old_base, _ = os.path.splitext(old_name)
        new_base, _ = os.path.splitext(new_name)
        
        text_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.html', 
            '.css', '.yml', '.yaml', '.md', '.toml', '.bat', '.sh', '.txt'
        }
        
        for root, dirs, files in os.walk(abs_path):
            dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '.dropbox', '.dropbox.cache', '__pycache__', 'dist', 'build')]
            
            for f in files:
                file_path = os.path.join(root, f)
                _, ext = os.path.splitext(f)
                if ext.lower() not in text_extensions:
                    continue
                    
                # Skip the file itself if we just moved it there!
                if os.path.abspath(file_path) == os.path.abspath(os.path.join(abs_path, new_rel_path)):
                    continue
                    
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as fp:
                        content = fp.read()
                    
                    updated = False
                    
                    # Check 1: Route references (forward slash)
                    if old_rel_forward in content:
                        content = content.replace(old_rel_forward, new_rel_forward)
                        updated = True
                    
                    # Check 2: Route references (backslash)
                    if old_rel_back in content:
                        content = content.replace(old_rel_back, new_rel_back)
                        updated = True
                    
                    # Check 3: Just the filename (only if different)
                    if old_name != new_name and old_name in content:
                        content = content.replace(old_name, new_name)
                        updated = True
                    
                    # Check 4: Base name without extension (e.g. for imports) if it contains spaces or is longer than 3 chars
                    if old_base != new_base and (len(old_base) > 3 or ' ' in old_base) and old_base in content:
                        content = content.replace(old_base, new_base)
                        updated = True
                    
                    if updated:
                        with open(file_path, 'w', encoding='utf-8') as fp:
                            fp.write(content)
                except Exception as e:
                    pass
