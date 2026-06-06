#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DecompressZip Command - Extracts files from a ZIP archive securely to a target folder.
"""

import os
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class DecompressZipCommand(CommandBase):
    """
    Command to extract ZIP archives, featuring security path verification to block directory traversal attacks.
    """
    
    name = "decompressZip"
    description = "Extracts all files from a ZIP archive to a destination folder, safely and securely"
    category = "file"
    
    parameters = [
        {
            'name': 'zip_path',
            'description': 'Path to the ZIP file to extract',
            'required': True
        },
        {
            'name': 'target_path',
            'description': 'Destination directory to extract files into (defaults to current directory)',
            'required': False,
            'default': '.'
        }
    ]
    
    examples = [
        {
            'command': 'qzx decompressZip project.zip',
            'description': 'Extract project.zip into the current directory'
        },
        {
            'command': 'qzx decompressZip project.zip C:/extracted-app',
            'description': 'Extract project.zip into C:/extracted-app'
        }
    ]
    
    def execute(self, zip_path, target_path='.'):
        """
        Decompresses a ZIP file
        
        Args:
            zip_path (str): ZIP file to read
            target_path (str): Destination directory
            
        Returns:
            Dictionary with decompression results
        """
        zip_path = zip_path.strip()
        target_path = target_path.strip()
        
        if not zip_path:
            return {
                "success": False,
                "error": "The zip_path parameter is required.",
                "message": "ZIP file path is required."
            }
            
        abs_zip = os.path.abspath(zip_path)
        abs_target = os.path.abspath(target_path)
        
        if not os.path.exists(abs_zip):
            return {
                "success": False,
                "error": f"ZIP file '{zip_path}' does not exist.",
                "message": f"ZIP file '{zip_path}' does not exist."
            }
            
        if not os.path.isfile(abs_zip):
            return {
                "success": False,
                "error": f"'{zip_path}' is not a file.",
                "message": f"'{zip_path}' is not a file."
            }
            
        if not zipfile.is_zipfile(abs_zip):
            return {
                "success": False,
                "error": f"'{zip_path}' is not a valid ZIP archive.",
                "message": f"'{zip_path}' is not a valid ZIP archive."
            }
            
        try:
            os.makedirs(abs_target, exist_ok=True)
            target_dir_path = Path(abs_target).resolve()
            
            extracted_files = []
            skipped_traversals = []
            total_bytes = 0
            
            with zipfile.ZipFile(abs_zip, 'r') as zipf:
                for member in zipf.infolist():
                    # Security validation: resolve target path and ensure it's inside target_dir_path (prevents Zip Slip)
                    # Zip Slip exploits "../" in file paths inside ZIPs to overwrite external files.
                    member_target_path = Path(os.path.join(abs_target, member.filename)).resolve()
                    
                    try:
                        # Path.is_relative_to is available in Python 3.9+
                        is_safe = member_target_path.is_relative_to(target_dir_path)
                    except AttributeError:
                        # Fallback for Python < 3.9
                        try:
                            member_target_path.relative_to(target_dir_path)
                            is_safe = True
                        except ValueError:
                            is_safe = False
                            
                    if not is_safe:
                        skipped_traversals.append(member.filename)
                        continue
                        
                    # Extract single member
                    zipf.extract(member, abs_target)
                    extracted_files.append(member.filename)
                    total_bytes += member.file_size
                    
            readable_extracted_size = self._format_bytes(total_bytes)
            
            msg = f"ZIP Decompression completed successfully for '{abs_zip}':\n"
            msg += f"- Extracted to: {abs_target}\n"
            msg += f"- Total files extracted: {len(extracted_files)}\n"
            msg += f"- Uncompressed size: {readable_extracted_size}\n"
            
            if skipped_traversals:
                msg += f"\n[WARNING] Skipped {len(skipped_traversals)} directory traversal attempt(s) (Zip Slip) during extraction:\n"
                for s in skipped_traversals[:5]:
                    msg += f"  - {s}\n"
                if len(skipped_traversals) > 5:
                    msg += f"  ... and {len(skipped_traversals) - 5} more.\n"
                    
            return {
                "success": True,
                "zip_path": abs_zip,
                "target_path": abs_target,
                "files_extracted": len(extracted_files),
                "total_bytes_extracted": total_bytes,
                "total_size_readable": readable_extracted_size,
                "skipped_traversals": skipped_traversals,
                "message": msg
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to decompress ZIP archive: {str(e)}"
            }
            
    def _format_bytes(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0 or unit == 'GB':
                break
            size /= 1024.0
        return f"{size:.2f} {unit}"
