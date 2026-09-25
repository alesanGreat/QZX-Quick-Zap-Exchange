#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Validate HTTP connectivity and measure basic response metrics."""

import time
import urllib.error
import urllib.parse
import urllib.request

from qzx.core.command_base import CommandBase


class CheckUrlStatusCommand(CommandBase):
    """Verify connectivity and retrieve metadata for a target URL."""

    name = "checkUrlStatus"
    description = (
        "Requests an HTTP(S) URL and reports its status code, response time, "
        "and basic headers."
    )
    category = "network"

    parameters = [
        {
            "name": "url",
            "description": "Target URL to check (e.g., https://api.github.com)",
            "required": True,
        },
        {
            "name": "timeout",
            "description": "Request timeout in seconds (default: 5.0)",
            "required": False,
            "default": 5.0,
        },
    ]

    examples = [
        {
            "command": "qzx checkUrlStatus https://api.github.com",
            "description": "Verify if GitHub API is accessible and check response times",
        },
        {
            "command": "qzx checkUrlStatus https://httpbin.org/status/404 3.0",
            "description": "Check a URL with a custom 3-second timeout",
        },
    ]

    def execute(self, url, timeout=5.0):
        """Execute one bounded HTTP request and return transport evidence."""
        try:
            normalized_url, timeout_value, error = self._normalize_input(url, timeout)
            if error:
                return error
            request = urllib.request.Request(
                normalized_url,
                headers={
                    "User-Agent": "QZX-Agent/1.0 (Quick Zap Exchange CLI)",
                    "Accept": "*/*",
                },
            )
            evidence = self._request_evidence(request, timeout_value)
            return self._result(normalized_url, evidence)
        except Exception as exc:
            return {
                "success": False,
                "url": url,
                "error": str(exc),
                "message": (
                    "An unexpected error occurred while checking URL "
                    f"connectivity: {exc}"
                ),
            }

    @staticmethod
    def _normalize_input(url, timeout):
        url = url.strip()
        if not url:
            return None, None, {
                "success": False,
                "message": "URL cannot be empty.",
                "error": "URL cannot be empty.",
                "error_code": "invalid_url",
            }
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme:
            url = "https://" + url
        try:
            if isinstance(timeout, str):
                timeout = float(timeout)
        except ValueError:
            timeout = 5.0
        return url, timeout, None

    @staticmethod
    def _request_evidence(request, timeout):
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return CheckUrlStatusCommand._evidence(
                    started,
                    status_code=response.status,
                    reason=response.msg or "OK",
                    headers=dict(response.headers.items()),
                    is_online=200 <= response.status < 400,
                )
        except urllib.error.HTTPError as exc:
            return CheckUrlStatusCommand._evidence(
                started,
                status_code=exc.code,
                reason=exc.reason or "HTTP Error",
                headers=dict(exc.headers.items()),
                is_online=False,
                status_detail=f"HTTP Error {exc.code}: {exc.reason or 'HTTP Error'}",
            )
        except urllib.error.URLError as exc:
            return CheckUrlStatusCommand._evidence(
                started,
                is_online=False,
                status_detail=f"Connection Failed: {exc.reason}",
            )
        except Exception as exc:
            return CheckUrlStatusCommand._evidence(
                started,
                is_online=False,
                status_detail=f"Request Failed: {exc}",
            )

    @staticmethod
    def _evidence(
        started,
        *,
        status_code=None,
        reason="Unknown",
        headers=None,
        is_online=False,
        status_detail=None,
    ):
        return {
            "status_code": status_code,
            "reason": reason,
            "headers": headers or {},
            "is_online": is_online,
            "status_detail": status_detail,
            "response_time_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    @classmethod
    def _result(cls, url, evidence):
        result = {
            "success": True,
            "url": url,
            "is_online": evidence["is_online"],
            "response_time_ms": evidence["response_time_ms"],
        }
        if evidence["status_code"] is not None:
            result["status_code"] = evidence["status_code"]
            result["reason"] = evidence["reason"]
        essential_headers = cls._essential_headers(evidence["headers"])
        if essential_headers:
            result["headers"] = essential_headers
        if evidence["status_detail"]:
            result["status_detail"] = evidence["status_detail"]
        result["message"] = cls._message(url, evidence, result["response_time_ms"])
        return result

    @staticmethod
    def _essential_headers(headers):
        essential = {}
        common_keys = (
            "Content-Type",
            "Content-Length",
            "Server",
            "Date",
            "Cache-Control",
            "Location",
            "Content-Encoding",
        )
        for expected in common_keys:
            for actual, value in headers.items():
                if expected.lower() == actual.lower():
                    essential[expected] = value
        return essential

    @staticmethod
    def _message(url, evidence, elapsed_ms):
        status_code = evidence["status_code"]
        reason = evidence["reason"]
        if evidence["is_online"]:
            return (
                f"URL '{url}' is ONLINE (Status: {status_code} {reason}, "
                f"Time: {elapsed_ms}ms)."
            )
        if status_code is not None:
            return (
                f"URL '{url}' responded with client/server error status "
                f"(Status: {status_code} {reason}, Time: {elapsed_ms}ms)."
            )
        return f"URL '{url}' is OFFLINE or unreachable: {evidence['status_detail']}."
