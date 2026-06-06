#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetFileHash Command - Computes MD5, SHA-1, or SHA-256 cryptographic hashes for a file
"""

import os
import sys
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class GetFileHashCommand(CommandBase):
    """
    Command to calculate cryptographic hash values of files
    """
    
    name = "getFileHash"
    description = "Calculates cryptographic hashes (MD5, SHA-1, SHA-256) of a file"
    category = "file"
    
    parameters = [
        {
            'name': 'file_path',
            'description': 'Path to the file to hash',
            'required': True
        },
        {
            'name': 'algorithm',
            'description': 'Hash algorithm to use (sha256, sha1, md5)',
            'required': False,
            'default': 'sha256'
        }
    ]
    
    examples = [
        {
            'command': 'qzx getFileHash file.txt',
            'description': 'Calculate SHA-256 hash for file.txt'
        },
        {
            'command': 'qzx getFileHash file.txt md5',
            'description': 'Calculate MD5 hash for file.txt'
        }
    ]
    
    def execute(self, file_path, algorithm='sha256'):
        """
        Calculates the hash of a file
        
        Args:
            file_path (str): Path to the file
            algorithm (str, optional): Cryptographic algorithm (sha256, sha1, md5)
            
        Returns:
            Dictionary with hash results and metadata
        """
        try:
            # Validate file exists
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": f"File '{file_path}' does not exist."
                }
            
            # Validate it's a file
            if not os.path.isfile(file_path):
                return {
                    "success": False,
                    "error": f"'{file_path}' is not a file."
                }
            
            # Clean and validate algorithm
            algorithm = algorithm.strip().lower()
            supported_algos = {
                'sha256': hashlib.sha256,
                'sha1': hashlib.sha1,
                'md5': hashlib.md5
            }
            
            if algorithm not in supported_algos:
                return {
                    "success": False,
                    "error": f"Unsupported hash algorithm '{algorithm}'. Supported algorithms: {', '.join(supported_algos.keys())}"
                }
            
            # Compute hash by reading in chunks of 64KB (good for memory efficiency)
            hash_obj = supported_algos[algorithm]()
            file_size = os.path.getsize(file_path)
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    hash_obj.update(chunk)
            
            calculated_hash = hash_obj.hexdigest()
            
            # Prepare response
            result = {
                "success": True,
                "file_path": os.path.abspath(file_path),
                "algorithm": algorithm,
                "hash": calculated_hash,
                "file_size": file_size,
                "file_size_readable": self._format_bytes(file_size),
                "message": f"{algorithm.upper()} hash for '{file_path}': {calculated_hash}"
            }
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "file_path": file_path,
                "error": str(e),
                "message": f"Failed to calculate file hash: {str(e)}"
            }
            
    def _format_bytes(self, size):
        """
        Format bytes to human-readable size
        
        Args:
            size (int): Size in bytes
            
        Returns:
            str: Human-readable size string
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0 or unit == 'TB':
                break
            size /= 1024.0
        return f"{size:.2f} {unit}"
