#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WonderFileTypeMagic Command - Identifies file type based on its magic number (file signature)
"""

import os
import magic
from Core.command_base import CommandBase

class WonderFileTypeMagicCommand(CommandBase):
    """
    Command to identify file type based on its magic number (file signature)
    """
    
    name = "wonderFileTypeMagic"
    description = "Identifies file type based on its magic number (file signature) rather than extension"
    category = "file"
    
    parameters = [
        {
            'name': 'file_path',
            'description': 'Path to the file to analyze',
            'required': True
        },
        {
            'name': 'detailed_info',
            'description': 'Whether to show detailed MIME type information',
            'required': False,
            'default': False
        }
    ]
    
    examples = [
        {
            'command': 'qzx wonderFileTypeMagic image.jpg',
            'description': 'Identify the real type of image.jpg based on its contents'
        },
        {
            'command': 'qzx wonderFileTypeMagic unknown.bin true',
            'description': 'Identify an unknown file with detailed MIME information'
        }
    ]
    
    def execute(self, file_path, detailed_info=False):
        """
        Identifies file type based on its magic number
        
        Args:
            file_path (str): Path to the file to analyze
            detailed_info (bool): Whether to include detailed MIME type information
            
        Returns:
            Dictionary with the result of the analysis
        """
        try:
            # Handle string conversion for detailed_info parameter
            if isinstance(detailed_info, str):
                detailed_info = detailed_info.lower() in ['true', 'yes', '1', 't', 'y']
            
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
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Use python-magic to identify the file type
            mime_type = magic.from_file(file_path, mime=True)
            file_description = magic.from_file(file_path)
            
            # Get file extension if any
            _, file_extension = os.path.splitext(file_path)
            file_extension = file_extension.lower() if file_extension else "none"
            
            # Common extensions for detected MIME type
            common_extensions = self._get_common_extensions_for_mime(mime_type)
            
            # Check if the extension matches what would be expected
            extension_matches = (file_extension[1:] if file_extension.startswith('.') else file_extension) in common_extensions
            
            # Determine if it's a binary file
            is_binary = not mime_type.startswith('text/')
            
            # Basic result
            result = {
                "success": True,
                "file_path": os.path.abspath(file_path),
                "file_size": file_size,
                "file_size_readable": self._format_bytes(file_size),
                "mime_type": mime_type,
                "description": file_description,
                "extension": file_extension,
                "is_binary": is_binary,
                "extension_matches_content": extension_matches,
                "message": f"File '{file_path}' is a {mime_type} file"
            }
            
            # Add suggested extension if current one doesn't match
            if not extension_matches and common_extensions:
                result["suggested_extension"] = f".{common_extensions[0]}"
                
                if file_extension != "none":
                    result["message"] = f"File '{file_path}' has extension '{file_extension}' but is actually a {mime_type} file (should be '.{common_extensions[0]}')"
                else:
                    result["message"] = f"File '{file_path}' has no extension but is a {mime_type} file (should have '.{common_extensions[0]}')"
            
            # Add detailed info if requested
            if detailed_info:
                # Get common file types
                file_categories = self._categorize_mime_type(mime_type)
                
                result["details"] = {
                    "mime_type": mime_type,
                    "description": file_description,
                    "common_extensions": common_extensions,
                    "categories": file_categories
                }
            
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
    
    def _get_common_extensions_for_mime(self, mime_type):
        """
        Return common file extensions for a given MIME type
        
        Args:
            mime_type (str): MIME type string
            
        Returns:
            list: List of common extensions (without leading dot)
        """
        mime_to_ext = {
            # Image formats
            'image/jpeg': ['jpg', 'jpeg'],
            'image/png': ['png'],
            'image/gif': ['gif'],
            'image/bmp': ['bmp'],
            'image/webp': ['webp'],
            'image/tiff': ['tiff', 'tif'],
            'image/svg+xml': ['svg'],
            'image/x-icon': ['ico'],
            
            # Document formats
            'application/pdf': ['pdf'],
            'application/msword': ['doc'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['docx'],
            'application/vnd.ms-excel': ['xls'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['xlsx'],
            'application/vnd.ms-powerpoint': ['ppt'],
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['pptx'],
            'text/plain': ['txt', 'text'],
            'text/html': ['html', 'htm'],
            'text/css': ['css'],
            'text/csv': ['csv'],
            'application/json': ['json'],
            'application/xml': ['xml'],
            'application/rtf': ['rtf'],
            
            # Archive formats
            'application/zip': ['zip'],
            'application/x-rar-compressed': ['rar'],
            'application/gzip': ['gz'],
            'application/x-tar': ['tar'],
            'application/x-7z-compressed': ['7z'],
            
            # Audio formats
            'audio/mpeg': ['mp3'],
            'audio/wav': ['wav'],
            'audio/ogg': ['ogg'],
            'audio/midi': ['mid', 'midi'],
            'audio/aac': ['aac'],
            'audio/flac': ['flac'],
            
            # Video formats
            'video/mp4': ['mp4'],
            'video/mpeg': ['mpeg', 'mpg'],
            'video/x-msvideo': ['avi'],
            'video/quicktime': ['mov'],
            'video/webm': ['webm'],
            'video/x-flv': ['flv'],
            'video/x-matroska': ['mkv'],
            
            # Executable/binary formats
            'application/x-msdownload': ['exe', 'dll'],
            'application/x-executable': ['exe'],
            'application/x-sharedlib': ['so', 'dll'],
            'application/x-object': ['o', 'obj'],
            'application/octet-stream': ['bin', 'dat'],
            
            # Font formats
            'font/ttf': ['ttf'],
            'font/otf': ['otf'],
            'font/woff': ['woff'],
            'font/woff2': ['woff2'],
            
            # Programming languages
            'text/x-python': ['py'],
            'text/x-c': ['c'],
            'text/x-c++': ['cpp', 'cxx', 'cc'],
            'text/x-java': ['java'],
            'text/javascript': ['js'],
            'application/x-httpd-php': ['php'],
            'text/x-ruby': ['rb'],
            'text/x-perl': ['pl'],
            'text/x-shellscript': ['sh', 'bash'],
            'text/x-csharp': ['cs'],
            
            # Database formats
            'application/x-sqlite3': ['sqlite', 'db'],
            'application/vnd.sqlite3': ['sqlite', 'db'],
            'application/vnd.ms-access': ['mdb', 'accdb']
        }
        
        return mime_to_ext.get(mime_type, [])
    
    def _categorize_mime_type(self, mime_type):
        """
        Categorize a MIME type into user-friendly categories
        
        Args:
            mime_type (str): MIME type string
            
        Returns:
            list: List of categories this file type belongs to
        """
        categories = []
        
        if mime_type.startswith('image/'):
            categories.append('Image')
        
        if mime_type.startswith('audio/'):
            categories.append('Audio')
        
        if mime_type.startswith('video/'):
            categories.append('Video')
        
        if mime_type.startswith('text/'):
            categories.append('Text')
            
            # Subcategories for text
            if 'html' in mime_type:
                categories.append('Web')
            if any(lang in mime_type for lang in ['python', 'java', 'c++', 'javascript', 'php', 'ruby', 'perl', 'shellscript', 'csharp']):
                categories.append('Source Code')
            
        if mime_type.startswith('application/'):
            if any(archive in mime_type for archive in ['zip', 'rar', 'gzip', 'tar', '7z', 'x-compressed']):
                categories.append('Archive')
            if any(doc in mime_type for doc in ['pdf', 'msword', 'openxmlformats', 'ms-excel', 'ms-powerpoint']):
                categories.append('Document')
            if any(exec_type in mime_type for exec_type in ['x-msdownload', 'x-executable', 'x-sharedlib', 'x-mach-binary']):
                categories.append('Executable')
            if any(db in mime_type for db in ['sqlite', 'ms-access']):
                categories.append('Database')
        
        if mime_type.startswith('font/'):
            categories.append('Font')
            
        # If no categories matched, use a generic one
        if not categories:
            categories.append('Other')
            
        return categories 