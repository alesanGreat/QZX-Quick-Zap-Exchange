#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TestDiskSpeed Command - Benchmarks sequential read/write speed of a directory's filesystem.
"""

import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class TestDiskSpeedCommand(CommandBase):
    """
    Command to measure read and write throughput speeds for a target storage directory.
    """
    
    name = "testDiskSpeed"
    description = "Benchmarks sequential write and read speeds (MB/s) of the filesystem at a target path"
    category = "system"
    
    parameters = [
        {
            'name': 'test_path',
            'description': 'Directory path to benchmark (defaults to current directory)',
            'required': False,
            'default': '.'
        },
        {
            'name': 'size_mb',
            'description': 'Temporary test file size in Megabytes (defaults to 50)',
            'required': False,
            'default': '50'
        }
    ]
    
    examples = [
        {
            'command': 'qzx testDiskSpeed',
            'description': 'Benchmark disk speed in the current folder using a 50MB test file'
        },
        {
            'command': 'qzx testDiskSpeed C:/temp 100',
            'description': 'Benchmark disk speed in C:/temp using a 100MB test file'
        }
    ]
    
    def execute(self, test_path='.', size_mb='50'):
        """
        Runs read/write benchmark
        
        Args:
            test_path (str): Directory to test
            size_mb (str/int): Test file size in MB
            
        Returns:
            Dictionary with read and write MB/s values
        """
        abs_path = os.path.abspath(test_path)
        
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"Path '{test_path}' does not exist.",
                "message": f"Path '{test_path}' does not exist."
            }
            
        if not os.path.isdir(abs_path):
            return {
                "success": False,
                "error": f"'{test_path}' is not a directory.",
                "message": f"'{test_path}' is not a directory."
            }
            
        try:
            mb_to_test = int(size_mb)
            if mb_to_test <= 0:
                mb_to_test = 50
        except ValueError:
            mb_to_test = 50
            
        temp_file = os.path.join(abs_path, "qzx_speedtest_temp.bin")
        
        try:
            # 1. Generate 1MB byte buffer
            # Using random bytes to prevent filesystem compression optimization from inflating results
            chunk_size = 1024 * 1024  # 1 MB
            buffer = os.urandom(chunk_size)
            
            # 2. Benchmark Write Speed
            print(f"Executing write test of {mb_to_test} MB...")
            start_write = time.perf_counter()
            with open(temp_file, "wb") as f:
                for _ in range(mb_to_test):
                    f.write(buffer)
                    # Force disk flushing
                    f.flush()
                    os.fsync(f.fileno())
            write_duration = time.perf_counter() - start_write
            
            # 3. Benchmark Read Speed
            print(f"Executing read test of {mb_to_test} MB...")
            start_read = time.perf_counter()
            bytes_read = 0
            with open(temp_file, "rb") as f:
                while True:
                    read_chunk = f.read(chunk_size)
                    if not read_chunk:
                        break
                    bytes_read += len(read_chunk)
            read_duration = time.perf_counter() - start_read
            
            # Clean up temp file immediately
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            # Calculations
            write_speed = mb_to_test / write_duration
            read_speed = mb_to_test / read_duration
            
            msg = f"Disk Benchmark completed successfully for '{abs_path}':\n"
            msg += f"- Sequential Write: {write_speed:.2f} MB/s (took {write_duration:.3f} s)\n"
            msg += f"- Sequential Read: {read_speed:.2f} MB/s (took {read_duration:.3f} s)\n"
            msg += f"- Tested File Size: {mb_to_test} MB"
            
            return {
                "success": True,
                "test_directory": abs_path,
                "test_file_size_mb": mb_to_test,
                "write_speed_mbs": round(write_speed, 2),
                "write_duration_seconds": round(write_duration, 3),
                "read_speed_mbs": round(read_speed, 2),
                "read_duration_seconds": round(read_duration, 3),
                "message": msg
            }
            
        except Exception as e:
            # Clean up if failed
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            return {
                "success": False,
                "error": str(e),
                "message": f"Disk speed test failed: {str(e)}"
            }
