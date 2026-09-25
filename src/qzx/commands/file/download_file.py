#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DownloadFile Command - Downloads a file from the Internet
"""

import os
import urllib.parse

from qzx.commands.file._download_request import prepare_download_request
from qzx.commands.file._download_transfer import download_prepared_file
from qzx.core.command_base import CommandBase

class DownloadFileCommand(CommandBase):
    """
    Command to download a file from the Internet
    """
    
    name = "downloadFile"
    description = "Downloads a file from the Internet (similar to 'wget' or 'curl' in Unix)"
    category = "file"
    requires_explicit_approval = True
    approval_when_parameter = "overwrite"
    backup_target_parameter = "destination_path"
    
    parameters = [
        {
            'name': 'url',
            'description': 'URL of the file to download',
            'required': True
        },
        {
            'name': 'destination_path',
            'description': 'Path where to save the downloaded file',
            'required': True
        },
        {
            'name': 'show_progress',
            'description': 'Whether to show download progress',
            'required': False,
            'default': True
        },
        {
            'name': 'timeout',
            'description': 'Maximum wait time in seconds',
            'required': False,
            'default': 30
        },
        {
            'name': 'overwrite',
            'description': 'Replace an existing destination after creating a safety backup',
            'required': False,
            'default': False
        }
    ]
    
    examples = [
        {
            'command': 'qzx downloadFile https://example.com/file.txt downloads/file.txt',
            'description': 'Download a sample file'
        },
        {
            'command': 'qzx downloadFile https://example.com/file.zip downloads/file.zip false',
            'description': 'Download a file without showing progress'
        },
        {
            'command': 'qzx downloadFile https://example.com/large-file.iso downloads/file.iso true 120',
            'description': 'Download a large file with extended timeout'
        },
        {
            'command': 'qzx downloadFile https://example.com/file.txt downloads/file.txt --overwrite',
            'description': 'Replace an existing file after creating a safety backup'
        }
    ]

    @staticmethod
    def _validated_http_url(url):
        """Return a parsed HTTP(S) URL or raise an actionable validation error."""
        parsed = urllib.parse.urlsplit(str(url))
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError(
                "url must be an absolute HTTP or HTTPS URL with a hostname"
            )
        if parsed.username is not None or parsed.password is not None:
            raise ValueError(
                "credentials embedded in URLs are not accepted; use a credential-safe client"
            )
        return parsed

    def validate_safety_backup_target(self, target, values):
        """Require a real file-like destination before an overwrite backup."""
        if not os.path.lexists(target):
            return {
                "success": False,
                "error_code": "overwrite_target_missing",
                "error": f"Cannot overwrite missing destination: {target}",
                "message": (
                    f"Destination '{target}' does not exist. Omit --overwrite "
                    "to create it as a new download."
                ),
                "details": {
                    "destination": os.path.abspath(target),
                    "overwrite": True,
                },
            }
        if os.path.isdir(target) and not os.path.islink(target):
            return {
                "success": False,
                "error_code": "destination_is_directory",
                "error": f"Destination is a directory: {target}",
                "message": (
                    f"Destination '{target}' is a directory. Choose a file path."
                ),
                "details": {
                    "destination": os.path.abspath(target),
                    "overwrite": True,
                },
            }
        return None

    def execute(
        self,
        url,
        destination_path,
        show_progress=True,
        timeout=30,
        overwrite=False,
    ):
        """Download one HTTP(S) resource using an atomic destination replace."""
        try:
            request, failure = prepare_download_request(
                self,
                url,
                destination_path,
                show_progress,
                timeout,
                overwrite,
            )
            if failure is not None:
                return failure
            return download_prepared_file(self, request)
        except Exception as exc:
            return {
                "success": False,
                "error_code": "download_failed",
                "url": str(url),
                "destination": os.path.abspath(destination_path),
                "error": f"{type(exc).__name__}: {exc}",
                "message": (
                    f"Download from '{url}' failed before the destination was "
                    f"replaced: {exc}"
                ),
                "details": {
                    "timeout_seconds": timeout,
                    "partial_file_removed": True,
                },
            }
