#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FindDuplicateFiles Command - Scans directories recursively for duplicate files by hashing and comparing sizes.
"""

import os
import sys
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class FindDuplicateFilesCommand(CommandBase):
    """
    Command to recursively identify duplicate files inside a folder to optimize disk usage.
    """
    
    name = "findDuplicateFiles"
    description = "Scans a directory for identical/duplicate files by file size matching and MD5 hashing"
    category = "file"
    
    parameters = [
        {
            'name': 'scan_path',
            'description': 'Path to start searching for duplicate files (defaults to current directory)',
            'required': False,
            'default': '.'
        },
        {
            'name': 'min_size_kb',
            'description': 'Minimum file size in KB to consider for duplicates (defaults to 10)',
            'required': False,
            'default': '10'
        },
        {
            'name': 'max_depth',
            'description': 'Maximum depth level to walk directories recursively (defaults to 4)',
            'required': False,
            'default': '4'
        }
    ]
    
    examples = [
        {
            'command': 'qzx findDuplicateFiles',
            'description': 'Search for duplicates in the current directory (min 10KB)'
        },
        {
            'command': 'qzx findDuplicateFiles C:/my-assets 0',
            'description': 'Search for all duplicate files of any size inside C:/my-assets'
        }
    ]
    
    def execute(self, scan_path='.', min_size_kb='10', max_depth='4'):
        """
        Locates duplicate files
        
        Args:
            scan_path (str): Root folder to scan
            min_size_kb (str/int): Size threshold to filter files
            max_depth (str/int): Folder depth limit
            
        Returns:
            Dictionary containing duplicate file lists and disk reclaim details
        """
        abs_path = os.path.abspath(scan_path)
        
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"Path '{scan_path}' does not exist.",
                "message": f"Path '{scan_path}' does not exist."
            }
            
        if not os.path.isdir(abs_path):
            return {
                "success": False,
                "error": f"'{scan_path}' is not a directory.",
                "message": f"'{scan_path}' is not a directory."
            }
            
        # Parse params
        try:
            min_bytes = float(min_size_kb) * 1024
        except ValueError:
            min_bytes = 10 * 1024
            
        try:
            depth_limit = int(max_depth)
        except ValueError:
            depth_limit = 4
            
        # 1. Group files by size first (fast pre-filter)
        files_by_size = {}
        base_depth = abs_path.count(os.sep)
        
        try:
            for root, dirs, files in os.walk(abs_path, topdown=True):
                current_depth = root.count(os.sep) - base_depth
                if current_depth >= depth_limit:
                    dirs.clear()
                    continue
                    
                # Skip heavy system/dependency dirs
                for skip in [".git", "node_modules", ".venv", "env"]:
                    if skip in dirs:
                        dirs.remove(skip)
                        
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        if os.path.islink(fp):
                            continue
                        size = os.path.getsize(fp)
                        if size >= min_bytes:
                            if size not in files_by_size:
                                files_by_size[size] = []
                            files_by_size[size].append(fp)
                    except OSError:
                        pass
                        
            # Filter sizes with multiple candidate files
            size_candidates = {s: files for s, files in files_by_size.items() if len(files) > 1}
            
            # 2. Hash candidates to confirm duplicates
            duplicates = {}
            for size, file_list in size_candidates.items():
                hashes = {}
                for fp in file_list:
                    h = self._get_md5(fp)
                    if h:
                        if h not in hashes:
                            hashes[h] = []
                        hashes[h].append(fp)
                        
                # Keep only hashes matching multiple files
                for h, paths in hashes.items():
                    if len(paths) > 1:
                        duplicates[h] = {
                            "size_bytes": size,
                            "size_readable": self._format_bytes(size),
                            "files": sorted(paths)
                        }
                        
            # 3. Calculate reclaimable space
            reclaimable_bytes = 0
            total_duplicate_groups = len(duplicates)
            total_duplicate_files = 0
            
            for h, info in duplicates.items():
                count = len(info["files"])
                total_duplicate_files += count
                # Space reclaimed = size * (count - 1)
                reclaimable_bytes += info["size_bytes"] * (count - 1)
                
            readable_reclaim = self._format_bytes(reclaimable_bytes)
            
            msg = f"Duplicate files scan completed for '{abs_path}':\n"
            msg += f"- Duplicate groups identified: {total_duplicate_groups}\n"
            msg += f"- Total duplicate file copies: {total_duplicate_files}\n"
            msg += f"- Reclaimable space: {readable_reclaim}\n"
            
            if total_duplicate_groups > 0:
                msg += "\nTop Duplicate Groups:\n"
                # Sort duplicate groups by size descending
                sorted_dups = sorted(duplicates.items(), key=lambda x: x[1]["size_bytes"], reverse=True)
                for h, info in sorted_dups[:5]:
                    rel_paths = [os.path.relpath(p, abs_path) for p in info["files"]]
                    msg += f"  - [{info['size_readable']}] MD5: {h[:8]}...\n"
                    for rel_p in rel_paths:
                        msg += f"    -> {rel_p}\n"
                if len(sorted_dups) > 5:
                    msg += f"  ... and {len(sorted_dups) - 5} more groups.\n"
                    
            return {
                "success": True,
                "scan_path": abs_path,
                "total_groups": total_duplicate_groups,
                "total_duplicate_files": total_duplicate_files,
                "reclaimable_bytes": reclaimable_bytes,
                "reclaimable_space_readable": readable_reclaim,
                "duplicate_groups": duplicates,
                "message": msg
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to search for duplicate files: {str(e)}"
            }
            
    def _get_md5(self, filepath):
        """Computes MD5 hash of file in chunks"""
        hash_md5 = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return None
            
    def _format_bytes(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0 or unit == 'GB':
                break
            size /= 1024.0
        return f"{size:.2f} {unit}"
