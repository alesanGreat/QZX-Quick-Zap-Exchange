#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CalculateFileHash Command - Computes MD5, SHA-1, or SHA-256 cryptographic hashes for a file
"""

from qzx.commands.file._file_hash_operation import execute_file_hash
from qzx.core.command_base import CommandBase

class CalculateFileHashCommand(CommandBase):
    """
    Command to calculate cryptographic hash values of files
    """
    
    name = "calculateFileHash"
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
            'command': 'qzx calculateFileHash file.txt',
            'description': 'Calculate SHA-256 hash for file.txt'
        },
        {
            'command': 'qzx calculateFileHash file.txt md5',
            'description': 'Calculate MD5 hash for file.txt'
        }
    ]
    
    def execute(self, file_path, algorithm='sha256'):
        """Calculate a supported cryptographic digest for one file."""
        return execute_file_hash(self, file_path, algorithm)
