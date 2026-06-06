#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CheckUrlStatus Command - Validates HTTP connectivity and measures response metrics for a target URL
"""

import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class CheckUrlStatusCommand(CommandBase):
    """
    Command to verify connectivity and retrieve metadata for a target URL
    """
    
    name = "checkUrlStatus"
    description = "Pings an HTTP URL, returning its status code, response time, and basic headers"
    category = "network"
    
    parameters = [
        {
            'name': 'url',
            'description': 'Target URL to check (e.g., https://api.github.com)',
            'required': True
        },
        {
            'name': 'timeout',
            'description': 'Request timeout in seconds (default: 5.0)',
            'required': False,
            'default': 5.0
        }
    ]
    
    examples = [
        {
            'command': 'qzx checkUrlStatus https://api.github.com',
            'description': 'Verify if GitHub API is accessible and check response times'
        },
        {
            'command': 'qzx checkUrlStatus https://httpbin.org/status/404 3.0',
            'description': 'Check a URL with a custom 3-second timeout'
        }
    ]
    
    def execute(self, url, timeout=5.0):
        """
        Executes an HTTP request to check URL status
        
        Args:
            url (str): Target URL
            timeout (float/str, optional): Connection timeout in seconds
            
        Returns:
            Dictionary with response metrics, headers, and online status
        """
        try:
            # Clean and parse URL
            url = url.strip()
            if not url:
                return {
                    "success": False,
                    "error": "URL cannot be empty."
                }
                
            # If protocol is missing, prepend https://
            parsed = urllib.parse.urlparse(url)
            if not parsed.scheme:
                url = "https://" + url
                parsed = urllib.parse.urlparse(url)
                
            # Parse and normalize timeout
            try:
                if isinstance(timeout, str):
                    timeout = float(timeout)
            except ValueError:
                timeout = 5.0
                
            # Headers to simulate a clean browser/client request
            req_headers = {
                'User-Agent': 'QZX-Agent/1.0 (Quick Zap Exchange CLI)',
                'Accept': '*/*'
            }
            
            req = urllib.request.Request(url, headers=req_headers)
            
            start_time = time.perf_counter()
            response_code = None
            response_reason = "Unknown"
            headers_dict = {}
            is_online = False
            error_msg = None
            
            try:
                # Execute the request
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    end_time = time.perf_counter()
                    response_code = response.status
                    response_reason = response.msg or "OK"
                    is_online = response_code >= 200 and response_code < 400
                    
                    # Extract header info
                    for key, val in response.headers.items():
                        headers_dict[key] = val
            except urllib.error.HTTPError as e:
                # HTTPError means the server replied, but with a non-2xx status (e.g. 404, 500)
                end_time = time.perf_counter()
                response_code = e.code
                response_reason = e.reason or "HTTP Error"
                is_online = False
                error_msg = f"HTTP Error {response_code}: {response_reason}"
                for key, val in e.headers.items():
                    headers_dict[key] = val
            except urllib.error.URLError as e:
                # URLError means connection failed (DNS error, timeout, server down)
                end_time = time.perf_counter()
                is_online = False
                error_msg = f"Connection Failed: {str(e.reason)}"
            except Exception as e:
                # Other connection issues (e.g., ssl handshake failed, timeout)
                end_time = time.perf_counter()
                is_online = False
                error_msg = f"Request Failed: {str(e)}"
                
            elapsed_ms = (end_time - start_time) * 1000
            
            # Prepare result
            result = {
                "success": True,
                "url": url,
                "is_online": is_online,
                "response_time_ms": round(elapsed_ms, 2)
            }
            
            if response_code is not None:
                result["status_code"] = response_code
                result["reason"] = response_reason
                
            if headers_dict:
                # Extract some common/useful headers to avoid bloat
                essential_headers = {}
                common_header_keys = [
                    'Content-Type', 'Content-Length', 'Server', 'Date', 
                    'Cache-Control', 'Location', 'Content-Encoding'
                ]
                for k in common_header_keys:
                    for hk, hv in headers_dict.items():
                        if k.lower() == hk.lower():
                            essential_headers[k] = hv
                result["headers"] = essential_headers
                
            if error_msg:
                result["error"] = error_msg
                
            # Formulate the response message
            if is_online:
                result["message"] = f"URL '{url}' is ONLINE (Status: {response_code} {response_reason}, Time: {result['response_time_ms']}ms)."
            elif response_code is not None:
                result["message"] = f"URL '{url}' responded with client/server error status (Status: {response_code} {response_reason}, Time: {result['response_time_ms']}ms)."
            else:
                result["message"] = f"URL '{url}' is OFFLINE or unreachable: {error_msg}."
                
            return result
            
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "message": f"An unexpected error occurred while checking URL connectivity: {str(e)}"
            }
