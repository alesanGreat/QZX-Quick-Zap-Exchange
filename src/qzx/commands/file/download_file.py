#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DownloadFile Command - Downloads a file from the Internet
"""

import hashlib
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

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
        """
        Downloads a file from the Internet
        
        Args:
            url (str): URL of the file to download
            destination_path (str): Path where to save the downloaded file
            show_progress (bool, optional): Whether to show download progress
            timeout (int, optional): Maximum wait time in seconds
            overwrite (bool, optional): Whether to replace an existing file
            
        Returns:
            Operation result
        """
        try:
            # Convert boolean parameters when execute() is called directly.
            if isinstance(show_progress, str):
                parsed_progress = self._parse_bool(show_progress)
                if parsed_progress is None:
                    return {
                        "success": False,
                        "error_code": "invalid_show_progress",
                        "error": f"Invalid show_progress value: {show_progress}",
                        "message": (
                            "show_progress must be true or false; received "
                            f"'{show_progress}'."
                        ),
                    }
                show_progress = parsed_progress
            if isinstance(overwrite, str):
                parsed_overwrite = self._parse_bool(overwrite)
                if parsed_overwrite is None:
                    return {
                        "success": False,
                        "error_code": "invalid_overwrite",
                        "error": f"Invalid overwrite value: {overwrite}",
                        "message": (
                            "overwrite must be true or false; received "
                            f"'{overwrite}'."
                        ),
                    }
                overwrite = parsed_overwrite

            try:
                timeout = int(timeout)
            except (TypeError, ValueError):
                return {
                    "success": False,
                    "error_code": "invalid_timeout",
                    "error": f"Invalid timeout: {timeout}",
                    "message": (
                        f"timeout must be a positive integer; received '{timeout}'."
                    ),
                }
            if timeout <= 0:
                return {
                    "success": False,
                    "error_code": "invalid_timeout",
                    "error": f"Invalid timeout: {timeout}",
                    "message": (
                        f"timeout must be greater than zero; received {timeout}."
                    ),
                }

            try:
                self._validated_http_url(url)
            except ValueError as exc:
                return {
                    "success": False,
                    "error_code": "invalid_url",
                    "error": str(exc),
                    "message": f"Download was not started: {exc}.",
                    "details": {
                        "url": str(url),
                        "allowed_schemes": ["http", "https"],
                    },
                }

            # Normalize destination path
            destination_path = os.path.normpath(destination_path)
            abs_destination_path = os.path.abspath(destination_path)
            if os.path.isdir(abs_destination_path) and not os.path.islink(
                abs_destination_path
            ):
                return {
                    "success": False,
                    "error_code": "destination_is_directory",
                    "error": f"Destination is a directory: {abs_destination_path}",
                    "message": (
                        f"Destination '{abs_destination_path}' is a directory. "
                        "Choose a file path."
                    ),
                    "details": {
                        "destination": abs_destination_path,
                    },
                }
            if os.path.lexists(abs_destination_path) and not overwrite:
                return {
                    "success": False,
                    "error_code": "destination_exists",
                    "error": f"Destination already exists: {abs_destination_path}",
                    "message": (
                        f"Destination '{abs_destination_path}' already exists. "
                        "Use --overwrite to replace it after a safety backup."
                    ),
                    "details": {
                        "destination": abs_destination_path,
                        "overwrite": False,
                    },
                }

            # Create parent directories if they don't exist
            destination_dir = os.path.dirname(abs_destination_path)
            if destination_dir and not os.path.exists(destination_dir):
                os.makedirs(destination_dir)

            # Prepare the result
            result = {
                "url": str(url),
                "destination": abs_destination_path,
                "show_progress": show_progress,
                "timeout": timeout,
                "overwrite": bool(overwrite),
                "start_time": time.time(),
                "success": True
            }

            request = urllib.request.Request(
                str(url),
                headers={"User-Agent": "QZX/0.2 (+https://qzx.yumbale.com/)"},
            )
            temporary_path = None
            response_status = None
            final_url = str(url)
            content_type = None
            expected_size = None
            file_size = 0
            sha256 = hashlib.sha256()
            started_monotonic = time.monotonic()
            try:
                descriptor, temporary_path = tempfile.mkstemp(
                    prefix=".qzx-download-",
                    suffix=".part",
                    dir=destination_dir or None,
                )
                with os.fdopen(descriptor, "wb") as destination_file:
                    with urllib.request.urlopen(  # nosec B310 - URL validated above.
                        request,
                        timeout=timeout,
                    ) as response:
                        final_url = response.geturl()
                        self._validated_http_url(final_url)
                        response_status = getattr(response, "status", None)
                        content_type = response.headers.get_content_type()
                        content_length = response.headers.get("Content-Length")
                        if content_length:
                            try:
                                expected_size = int(content_length)
                            except ValueError:
                                expected_size = None

                        while True:
                            chunk = response.read(64 * 1024)
                            if not chunk:
                                break
                            destination_file.write(chunk)
                            sha256.update(chunk)
                            file_size += len(chunk)
                            if show_progress:
                                elapsed = max(
                                    time.monotonic() - started_monotonic,
                                    0.001,
                                )
                                speed = file_size / elapsed
                                if expected_size and expected_size > 0:
                                    percent = min(
                                        100.0,
                                        file_size * 100 / expected_size,
                                    )
                                    progress = (
                                        f"{percent:.1f}% "
                                        f"({self._format_bytes(file_size)} / "
                                        f"{self._format_bytes(expected_size)})"
                                    )
                                else:
                                    progress = self._format_bytes(file_size)
                                sys.stdout.write(
                                    "\rDownloading: "
                                    f"{progress} at {self._format_bytes(speed)}/s"
                                )
                                sys.stdout.flush()
                    destination_file.flush()
                    os.fsync(destination_file.fileno())

                if expected_size is not None and file_size != expected_size:
                    raise OSError(
                        "response ended after {} bytes; expected {}".format(
                            file_size,
                            expected_size,
                        )
                    )
                os.replace(temporary_path, abs_destination_path)
                temporary_path = None
            finally:
                if temporary_path and os.path.exists(temporary_path):
                    os.unlink(temporary_path)

            if show_progress:
                print()

            file_size_readable = self._format_bytes(file_size)

            # Calculate total time
            end_time = time.time()
            download_time = end_time - result["start_time"]

            # Calculate average speed
            if download_time > 0:
                avg_speed = file_size / download_time
                avg_speed_readable = self._format_bytes(avg_speed) + "/s"
            else:
                avg_speed = None
                avg_speed_readable = "N/A"
            
            # Update the result
            result.update({
                "final_url": final_url,
                "http_status": response_status,
                "content_type": content_type,
                "expected_size": expected_size,
                "file_size": file_size,
                "file_size_readable": file_size_readable,
                "sha256": sha256.hexdigest(),
                "download_time": download_time,
                "download_time_readable": f"{download_time:.2f} seconds",
                "avg_speed": avg_speed,
                "avg_speed_readable": avg_speed_readable,
                "message": (
                    f"Downloaded {final_url} to {abs_destination_path} "
                    f"({file_size_readable}, SHA-256 {sha256.hexdigest()})."
                ),
            })

            return result
        except Exception as e:
            return {
                "success": False,
                "error_code": "download_failed",
                "url": str(url),
                "destination": os.path.abspath(destination_path),
                "error": f"{type(e).__name__}: {e}",
                "message": (
                    f"Download from '{url}' failed before the destination was "
                    f"replaced: {e}"
                ),
                "details": {
                    "timeout_seconds": timeout,
                    "partial_file_removed": True,
                },
            }
    
