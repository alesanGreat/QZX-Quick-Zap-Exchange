#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DownloadFile Command - Downloads a file from the Internet
"""

import os
import urllib.request
import sys
import time
from Core.command_base import CommandBase

class DownloadFileCommand(CommandBase):
    """
    Command to download a file from the Internet
    """
    
    name = "downloadFile"
    description = "Downloads a file from the Internet (similar to 'wget' or 'curl' in Unix)"
    category = "file"
    
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
        }
    ]
    
    def execute(self, url, destination_path, show_progress=True, timeout=30):
        """
        Downloads a file from the Internet
        
        Args:
            url (str): URL of the file to download
            destination_path (str): Path where to save the downloaded file
            show_progress (bool, optional): Whether to show download progress
            timeout (int, optional): Maximum wait time in seconds
            
        Returns:
            Operation result
        """
        try:
            # Convert show_progress to boolean if it's a string
            if isinstance(show_progress, str):
                show_progress = show_progress.lower() in ('true', 'yes', 'y', '1')
            
            # Convert timeout to integer if it's a string
            if isinstance(timeout, str):
                try:
                    timeout = int(timeout)
                except ValueError:
                    return {
                        "success": False,
                        "error": f"timeout must be an integer, received '{timeout}'"
                    }
            
            # Normalize destination path
            destination_path = os.path.normpath(destination_path)
            abs_destination_path = os.path.abspath(destination_path)
            
            # Create parent directories if they don't exist
            destination_dir = os.path.dirname(destination_path)
            if destination_dir and not os.path.exists(destination_dir):
                os.makedirs(destination_dir)
            
            # Prepare the result
            result = {
                "url": url,
                "destination": abs_destination_path,
                "show_progress": show_progress,
                "timeout": timeout,
                "start_time": time.time(),
                "success": True
            }
            
            # Define a function to show download progress
            if show_progress:
                def progress_callback(block_num, block_size, total_size):
                    if total_size > 0:
                        downloaded = block_num * block_size
                        percent = min(100, downloaded * 100 / total_size)
                        
                        # Calculate speed
                        elapsed = time.time() - result["start_time"]
                        if elapsed > 0:
                            speed = downloaded / elapsed
                            
                            # Format speed
                            if speed < 1024:
                                speed_str = f"{speed:.1f} B/s"
                            elif speed < 1024 * 1024:
                                speed_str = f"{speed / 1024:.1f} KB/s"
                            else:
                                speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                            
                            # Estimated time remaining (ETA)
                            if downloaded > 0:
                                eta = (total_size - downloaded) / speed
                                if eta < 60:
                                    eta_str = f"{eta:.0f} seconds"
                                elif eta < 3600:
                                    eta_str = f"{eta / 60:.1f} minutes"
                                else:
                                    eta_str = f"{eta / 3600:.1f} hours"
                            else:
                                eta_str = "unknown"
                            
                            progress_msg = f"\rDownloading: {percent:.1f}% ({self._format_bytes(downloaded)} / {self._format_bytes(total_size)}) at {speed_str}, ETA: {eta_str}"
                        else:
                            progress_msg = f"\rDownloading: {percent:.1f}% ({self._format_bytes(downloaded)} / {self._format_bytes(total_size)})"
                        
                        sys.stdout.write(progress_msg)
                        sys.stdout.flush()
            else:
                progress_callback = None
            
            # Download the file with or without progress
            urllib.request.urlretrieve(url, destination_path, progress_callback if show_progress else None)
            
            if show_progress:
                print()  # New line after progress output
            
            # Get information about the downloaded file
            file_size = os.path.getsize(destination_path)
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
                "file_size": file_size,
                "file_size_readable": file_size_readable,
                "download_time": download_time,
                "download_time_readable": f"{download_time:.2f} seconds",
                "avg_speed": avg_speed,
                "avg_speed_readable": avg_speed_readable,
                "message": f"Downloaded {url} to {destination_path} ({file_size_readable})"
            })
            
            return result
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "destination": destination_path,
                "error": str(e)
            }
    
    def _format_bytes(self, bytes_value):
        """
        Format bytes to human-readable format
        
        Args:
            bytes_value (int): Bytes to format
            
        Returns:
            str: Formatted string with appropriate unit
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024 or unit == 'TB':
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024 