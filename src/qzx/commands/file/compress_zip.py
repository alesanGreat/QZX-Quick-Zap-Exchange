#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CompressZip Command - Creates a ZIP archive of a folder or file, with support for exclusions.
"""

import os
import sys
import zipfile
import fnmatch
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class CompressZipCommand(CommandBase):
    """
    Command to package and compress files/folders into a ZIP archive while filtering unwanted paths.
    """
    
    name = "compressZip"
    description = "Compresses a directory or file into a ZIP archive with custom exclusion rules"
    category = "file"
    
    parameters = [
        {
            'name': 'zip_path',
            'description': 'Target path for the created ZIP archive (e.g. project.zip)',
            'required': True
        },
        {
            'name': 'source_path',
            'description': 'Local file or directory to compress',
            'required': True
        },
        {
            'name': 'exclude_patterns',
            'description': 'Comma-separated folders, files, or wildcards to exclude (defaults to standard caches)',
            'required': False,
            'default': '.git,node_modules,__pycache__,.venv,env,dist,build'
        }
    ]
    
    examples = [
        {
            'command': 'qzx compressZip project.zip .',
            'description': 'Compress the current directory into project.zip, excluding standard build folders'
        },
        {
            'command': 'qzx compressZip src.zip src',
            'description': 'Compress the src folder into src.zip'
        }
    ]
    
    def execute(self, zip_path, source_path, exclude_patterns=None):
        """
        Compresses a file or directory
        
        Args:
            zip_path (str): Destination ZIP file path
            source_path (str): Source directory or file
            exclude_patterns (str, optional): Exclude rules comma-separated
            
        Returns:
            Dictionary with compression results
        """
        zip_path = zip_path.strip()
        source_path = source_path.strip()
        
        if not zip_path or not source_path:
            return {
                "success": False,
                "error": "Both zip_path and source_path parameters are required.",
                "message": "Both parameters must be set."
            }
            
        abs_source = os.path.abspath(source_path)
        abs_zip = os.path.abspath(zip_path)
        
        if not os.path.exists(abs_source):
            return {
                "success": False,
                "error": f"Source path '{source_path}' does not exist.",
                "message": f"Source path '{source_path}' does not exist."
            }
            
        # Parse excludes
        if exclude_patterns is None:
            excludes = {'.git', 'node_modules', '__pycache__', '.venv', 'env', 'dist', 'build'}
        else:
            excludes = {p.strip() for p in exclude_patterns.split(',') if p.strip()}
            
        # Determine ZIP compression method
        compression = zipfile.ZIP_DEFLATED
        try:
            import zlib
        except ImportError:
            compression = zipfile.ZIP_STORED
            
        try:
            # Create parent folder for target zip if it doesn't exist
            zip_dir = os.path.dirname(abs_zip)
            if zip_dir:
                os.makedirs(zip_dir, exist_ok=True)
                
            total_files = 0
            original_size = 0
            
            with zipfile.ZipFile(abs_zip, 'w', compression) as zipf:
                if os.path.isfile(abs_source):
                    # Compress a single file
                    arcname = os.path.basename(abs_source)
                    zipf.write(abs_source, arcname)
                    original_size = os.path.getsize(abs_source)
                    total_files = 1
                else:
                    # Compress a directory recursively
                    base_dir = os.path.dirname(abs_source)
                    for root, dirs, files in os.walk(abs_source):
                        # Filter directories in-place to stop scanning ignored subdirectories
                        for d in list(dirs):
                            if d in excludes or any(fnmatch.fnmatch(d, pat) for pat in excludes):
                                dirs.remove(d)
                                
                        for f in files:
                            # Skip if file matches exclusions
                            if f in excludes or any(fnmatch.fnmatch(f, pat) for pat in excludes):
                                continue
                                
                            full_path = os.path.join(root, f)
                            
                            # Skip writing the output ZIP file if it's placed inside the source directory
                            if os.path.abspath(full_path) == abs_zip:
                                continue
                                
                            arcname = os.path.relpath(full_path, abs_source)
                            zipf.write(full_path, arcname)
                            
                            try:
                                original_size += os.path.getsize(full_path)
                            except OSError:
                                pass
                            total_files += 1
                            
            compressed_size = os.path.getsize(abs_zip)
            ratio = (1 - (compressed_size / original_size)) * 100 if original_size > 0 else 0
            
            readable_orig = self._format_bytes(original_size)
            readable_comp = self._format_bytes(compressed_size)
            
            msg = f"ZIP Compression completed successfully for '{abs_source}':\n"
            msg += f"- Archive location: {abs_zip}\n"
            msg += f"- Compressed files: {total_files}\n"
            msg += f"- Original size: {readable_orig}\n"
            msg += f"- ZIP archive size: {readable_comp} (Savings: {ratio:.1f}%)\n"
            
            return {
                "success": True,
                "zip_path": abs_zip,
                "source_path": abs_source,
                "files_archived": total_files,
                "original_bytes": original_size,
                "compressed_bytes": compressed_size,
                "compression_ratio_percent": round(ratio, 2),
                "message": msg
            }
            
        except Exception as e:
            # Cleanup broken zip if created
            if os.path.exists(abs_zip):
                try:
                    os.remove(abs_zip)
                except OSError:
                    pass
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to compress ZIP archive: {str(e)}"
            }
            
    def _format_bytes(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0 or unit == 'GB':
                break
            size /= 1024.0
        return f"{size:.2f} {unit}"
