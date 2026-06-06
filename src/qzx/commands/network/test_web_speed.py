#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TestWebSpeed Command - Measures internet ping latency and download speed using a public high-speed CDN.
"""

import os
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class TestWebSpeedCommand(CommandBase):
    """
    Command to measure internet connection latency (ping) and active download speed.
    """
    
    name = "testWebSpeed"
    description = "Measures internet download speed (Mbps) and HTTP ping latency (ms)"
    category = "network"
    
    parameters = [
        {
            'name': 'max_seconds',
            'description': 'Maximum duration of the download test in seconds (defaults to 3)',
            'required': False,
            'default': '3'
        }
    ]
    
    examples = [
        {
            'command': 'qzx testWebSpeed',
            'description': 'Measure connection latency and download throughput'
        },
        {
            'command': 'qzx testWebSpeed 5',
            'description': 'Run the speed test for up to 5 seconds'
        }
    ]
    
    # Fast, reliable CDN file for testing throughput
    TEST_URL = "https://speed.cloudflare.com/__down?bytes=25000000"  # 25 MB chunk
    LATENCY_URL = "https://1.1.1.1/"
    
    def execute(self, max_seconds='3'):
        """
        Executes speed and latency checks
        
        Args:
            max_seconds (str/int): Maximum test duration
            
        Returns:
            Dictionary with download speed and latency statistics
        """
        try:
            max_sec = float(max_seconds)
            if max_sec <= 0:
                max_sec = 3.0
        except ValueError:
            max_sec = 3.0
            
        # 1. Latency check (Ping equivalent using HTTP request)
        print("Measuring latency to Cloudflare DNS (1.1.1.1)...")
        latencies = []
        for _ in range(3):
            try:
                start = time.time()
                req = urllib.request.Request(self.LATENCY_URL, headers={"User-Agent": "QZX Speed Client"})
                # Set a short timeout for ping checks
                with urllib.request.urlopen(req, timeout=2) as conn:
                    conn.read(10)  # read minimal bytes
                elapsed_ms = (time.time() - start) * 1000
                latencies.append(elapsed_ms)
            except Exception:
                pass
                
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
        else:
            avg_latency = -1
            min_latency = -1
            max_latency = -1
            
        # 2. Download speed test
        print(f"Testing download throughput (capping at {max_sec} seconds)...")
        bytes_downloaded = 0
        start_time = time.time()
        elapsed = 0.0
        error_msg = None
        
        try:
            req = urllib.request.Request(self.TEST_URL, headers={"User-Agent": "QZX Speed Client"})
            with urllib.request.urlopen(req, timeout=5) as conn:
                # Read in chunks of 64KB
                while True:
                    chunk = conn.read(65536)
                    if not chunk:
                        break
                    bytes_downloaded += len(chunk)
                    elapsed = time.time() - start_time
                    if elapsed >= max_sec:
                        break
        except Exception as e:
            error_msg = str(e)
            elapsed = time.time() - start_time
            
        # If we failed completely
        if bytes_downloaded == 0:
            return {
                "success": False,
                "error": error_msg or "Failed to download any bytes.",
                "message": f"Speed test failed: {error_msg or 'No connection could be established.'}"
            }
            
        # Calculate speed
        if elapsed <= 0:
            elapsed = 0.01
            
        speed_bps = (bytes_downloaded * 8) / elapsed
        speed_kbps = speed_bps / 1000
        speed_mbps = speed_bps / 1000000
        
        # Formulate message
        msg = "Internet Speed Test Results:\n"
        if avg_latency > 0:
            msg += f"- HTTP Latency: {avg_latency:.1f} ms (min: {min_latency:.1f} ms, max: {max_latency:.1f} ms)\n"
        else:
            msg += "- HTTP Latency: failed to resolve latency\n"
        msg += f"- Download Speed: {speed_mbps:.2f} Mbps ({speed_kbps/1024:.2f} MB/s)\n"
        msg += f"- Data Fetched: {self._format_bytes(bytes_downloaded)} in {elapsed:.2f} seconds"
        
        return {
            "success": True,
            "latency_ms": {
                "average": avg_latency if avg_latency > 0 else None,
                "min": min_latency if min_latency > 0 else None,
                "max": max_latency if max_latency > 0 else None
            },
            "download_speed_mbps": round(speed_mbps, 2),
            "download_speed_mbs": round((bytes_downloaded / 1024 / 1024) / elapsed, 2),
            "test_details": {
                "bytes_downloaded": bytes_downloaded,
                "duration_seconds": round(elapsed, 2),
                "capped": elapsed >= max_sec
            },
            "message": msg
        }
        
    def _format_bytes(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0 or unit == 'GB':
                break
            size /= 1024.0
        return f"{size:.2f} {unit}"
