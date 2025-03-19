#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WonderIfFileIsBinary Command - Checks if a file is binary or plain text
"""

import os
import chardet
import string
from Core.command_base import CommandBase

class WonderIfFileIsBinaryCommand(CommandBase):
    """
    Command to check if a file is binary or plain text
    """
    
    name = "wonderIfFileIsBinary"
    description = "Analyzes a file to determine if it's binary or plain text"
    category = "file"
    
    parameters = [
        {
            'name': 'file_path',
            'description': 'Path to the file to analyze',
            'required': True
        },
        {
            'name': 'sample_size',
            'description': 'Size of the file sample to analyze (in bytes)',
            'required': False,
            'default': 8192
        },
        {
            'name': 'binary_threshold',
            'description': 'Percentage of non-text bytes required to classify as binary',
            'required': False,
            'default': 10
        }
    ]
    
    examples = [
        {
            'command': 'qzx wonderIfFileIsBinary script.py',
            'description': 'Check if script.py is a binary file'
        },
        {
            'command': 'qzx wonderIfFileIsBinary image.jpg',
            'description': 'Check if image.jpg is a binary file'
        },
        {
            'command': 'qzx wonderIfFileIsBinary unknown.dat 4096 5',
            'description': 'Check if unknown.dat is binary, using a 4KB sample and 5% threshold'
        }
    ]
    
    def execute(self, file_path, sample_size=8192, binary_threshold=10):
        """
        Checks if a file is binary or plain text
        
        Args:
            file_path (str): Path to the file to analyze
            sample_size (int): Size of the file sample to analyze (in bytes)
            binary_threshold (int): Percentage of non-text bytes required to classify as binary
            
        Returns:
            Dictionary with the result of the analysis
        """
        try:
            # Convert numeric parameters if they're strings
            if isinstance(sample_size, str):
                try:
                    sample_size = int(sample_size)
                except ValueError:
                    return {
                        "success": False,
                        "error": f"sample_size must be an integer, got: {sample_size}"
                    }
            
            if isinstance(binary_threshold, str):
                try:
                    binary_threshold = float(binary_threshold)
                except ValueError:
                    return {
                        "success": False,
                        "error": f"binary_threshold must be a number, got: {binary_threshold}"
                    }
            
            # Validate file exists
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": f"File '{file_path}' does not exist"
                }
            
            # Validate it's a file
            if not os.path.isfile(file_path):
                return {
                    "success": False,
                    "error": f"'{file_path}' is not a file"
                }
            
            # Get file size and determine if we're checking the whole file
            file_size = os.path.getsize(file_path)
            is_full_file = file_size <= sample_size
            
            # Read file content (or a sample)
            with open(file_path, 'rb') as f:
                content = f.read(sample_size)
            
            # Empty files are considered text
            if not content:
                return {
                    "success": True,
                    "file_path": os.path.abspath(file_path),
                    "is_binary": False,
                    "file_size": file_size,
                    "file_size_readable": self._format_bytes(file_size),
                    "message": f"File '{file_path}' is empty and considered as plain text"
                }
            
            # Method 1: Look for null bytes (strong indicator of binary)
            if b'\x00' in content:
                binary_score = 100
                detection_method = "null_bytes"
            else:
                # Method 2: Check character distribution
                textchars = bytearray(
                    {7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x7F)) | set(range(0x80, 0x100))
                )
                is_binary_bytes = bytes(c for c in content if c not in textchars)
                binary_score = (len(is_binary_bytes) * 100) / len(content)
                detection_method = "character_distribution"
            
            # Method 3: Use chardet to detect encoding
            encoding_result = chardet.detect(content)
            encoding_confidence = encoding_result['confidence'] * 100
            detected_encoding = encoding_result['encoding']
            
            # Combine methods for final decision
            is_binary = binary_score >= binary_threshold
            
            # Prepare extended details
            details = {
                "binary_byte_percentage": round(binary_score, 2),
                "detection_method": detection_method,
                "encoding_detected": detected_encoding,
                "encoding_confidence": round(encoding_confidence, 2),
                "sample_size": len(content),
                "is_full_file": is_full_file,
                "binary_threshold": binary_threshold
            }
            
            # Determine likely mime type if binary
            mime_type = self._guess_mime_type(file_path, content, is_binary)
            
            # Create result
            result = {
                "success": True,
                "file_path": os.path.abspath(file_path),
                "is_binary": is_binary,
                "file_size": file_size,
                "file_size_readable": self._format_bytes(file_size),
                "analyzed_bytes": len(content),
                "mime_type": mime_type,
                "details": details
            }
            
            # Add a message
            if is_binary:
                result["message"] = f"File '{file_path}' is binary ({mime_type or 'unknown type'})"
            else:
                result["message"] = f"File '{file_path}' is plain text ({detected_encoding})"
            
            return result
        
        except Exception as e:
            return {
                "success": False,
                "file_path": file_path,
                "error": str(e)
            }
    
    def _format_bytes(self, size):
        """
        Format bytes to human-readable size
        
        Args:
            size (int): Size in bytes
            
        Returns:
            str: Human-readable size string
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if size < 1024.0 or unit == 'PB':
                break
            size /= 1024.0
        return f"{size:.2f} {unit}"
    
    def _guess_mime_type(self, file_path, content, is_binary):
        """
        Guess the MIME type of a file based on its extension and content
        
        Args:
            file_path (str): Path to the file
            content (bytes): File content or sample
            is_binary (bool): Whether the file is detected as binary
        
        Returns:
            str: Guessed MIME type or None if unknown
        """
        # Common file extensions and their MIME types
        extension_mime_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.ico': 'image/x-icon',
            '.svg': 'image/svg+xml',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.zip': 'application/zip',
            '.rar': 'application/x-rar-compressed',
            '.tar': 'application/x-tar',
            '.gz': 'application/gzip',
            '.7z': 'application/x-7z-compressed',
            '.exe': 'application/x-msdownload',
            '.dll': 'application/x-msdownload',
            '.so': 'application/octet-stream',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.mp4': 'video/mp4',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.flv': 'video/x-flv',
            '.db': 'application/x-sqlite3',
            '.mdb': 'application/x-msaccess',
            '.ttf': 'font/ttf',
            '.otf': 'font/otf',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2'
        }
        
        # Text file extensions and their MIME types
        text_extension_mime_map = {
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.htm': 'text/html',
            '.css': 'text/css',
            '.js': 'text/javascript',
            '.json': 'application/json',
            '.xml': 'text/xml',
            '.md': 'text/markdown',
            '.rst': 'text/x-rst',
            '.csv': 'text/csv',
            '.log': 'text/plain',
            '.ini': 'text/plain',
            '.conf': 'text/plain',
            '.py': 'text/x-python',
            '.java': 'text/x-java',
            '.c': 'text/x-c',
            '.cpp': 'text/x-c++',
            '.h': 'text/x-c',
            '.hpp': 'text/x-c++',
            '.cs': 'text/x-csharp',
            '.php': 'text/x-php',
            '.rb': 'text/x-ruby',
            '.pl': 'text/x-perl',
            '.sh': 'text/x-shellscript',
            '.bat': 'text/plain',
            '.ps1': 'text/plain',
            '.sql': 'text/x-sql',
            '.yaml': 'text/yaml',
            '.yml': 'text/yaml'
        }
        
        # Get file extension
        ext = os.path.splitext(file_path.lower())[1]
        
        # Check if the file extension matches known binary types
        if is_binary and ext in extension_mime_map:
            return extension_mime_map[ext]
            
        # Check if the file extension matches known text types
        if not is_binary and ext in text_extension_mime_map:
            return text_extension_mime_map[ext]
        
        # Try to identify binary file types by magic numbers
        if is_binary:
            # Check for common file signatures
            if content.startswith(b'\xFF\xD8\xFF'):
                return 'image/jpeg'
            elif content.startswith(b'\x89PNG\r\n\x1A\n'):
                return 'image/png'
            elif content.startswith(b'GIF87a') or content.startswith(b'GIF89a'):
                return 'image/gif'
            elif content.startswith(b'%PDF'):
                return 'application/pdf'
            elif content.startswith(b'PK\x03\x04'):
                return 'application/zip'
            elif content.startswith(b'Rar!\x1A\x07'):
                return 'application/x-rar-compressed'
            elif content.startswith(b'\x1F\x8B'):
                return 'application/gzip'
            elif content.startswith(b'MZ'):
                return 'application/x-msdownload'  # EXE or DLL
            elif content.startswith(b'\x7FELF'):
                return 'application/x-executable'  # ELF binary
            
            # Default for binary
            return 'application/octet-stream'
            
        # Default for text
        return 'text/plain' 