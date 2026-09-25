#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Diagnose a public website by correlating DNS, TLS, and HTTP evidence."""

from qzx.commands.network import _diagnose_website_classify as classify
from qzx.commands.network import _diagnose_website_recommendations as recommend
from qzx.commands.network import _diagnose_website_results as results
from qzx.commands.network import _diagnose_website_target as target_support
from qzx.core.command_base import CommandBase


class DiagnoseWebsiteCommand(CommandBase):
    """Turn three network probes into one actionable website diagnosis."""

    name = "diagnoseWebsite"
    description = (
        "Diagnoses why an HTTPS website may be failing by correlating DNS, TLS "
        "certificate, and HTTP reachability evidence"
    )
    category = "network"

    parameters = [
        {
            "name": "target",
            "description": (
                "Domain or HTTPS URL to diagnose, optionally including a port or path"
            ),
            "required": True,
            "type": "str",
        },
        {
            "name": "timeout",
            "description": "HTTP request timeout in seconds (0.1-60; defaults to 10)",
            "required": False,
            "default": 10.0,
            "type": "float",
        },
    ]

    examples = [
        {
            "command": "qzx diagnoseWebsite example.com",
            "description": "Diagnose DNS, TLS, and HTTP for a website in one command",
        },
        {
            "command": "qzx diagnoseWebsite https://example.com/docs --json",
            "description": "Return a structured diagnosis for a specific HTTPS path",
        },
        {
            "command": "qzx diagnoseWebsite example.com:8443/status --timeout 15 --json",
            "description": "Diagnose an HTTPS service on a custom port with a longer HTTP timeout",
        },
    ]

    def __init__(self, *, dns_command=None, tls_command=None, http_command=None):
        """Allow deterministic probe injection while keeping normal use self-contained."""
        if dns_command is None:
            from qzx.commands.network.check_dns import CheckDnsCommand

            dns_command = CheckDnsCommand()
        if tls_command is None:
            from qzx.commands.network.check_ssl_certificate import CheckSslCertificateCommand

            tls_command = CheckSslCertificateCommand()
        if http_command is None:
            from qzx.commands.network.check_url_status import CheckUrlStatusCommand

            http_command = CheckUrlStatusCommand()
        self._dns = dns_command
        self._tls = tls_command
        self._http = http_command

    def execute(self, target, timeout=10.0):
        """Run bounded read-only probes and explain the most likely failing layer."""
        normalized, error = target_support.normalize_target(target)
        if error is not None:
            return error
        timeout_value, error = target_support.normalize_timeout(
            timeout,
            normalized["target"],
        )
        if error is not None:
            return error

        host = normalized["host"]
        dns = self._run_probe("dns", self._dns.execute, host)
        if dns.get("error_code") == "dns_name_not_found":
            return self._nxdomain_result(normalized, timeout_value, dns)

        port = normalized["port"]
        endpoint = normalized["url"]
        tls = self._run_probe("tls", self._tls.execute, host, port)
        http = self._run_probe("http", self._http.execute, endpoint, timeout_value)
        return self._correlated_result(
            normalized,
            timeout_value,
            dns,
            tls,
            http,
        )

    def _correlated_result(self, normalized, timeout_value, dns, tls, http):
        host = normalized["host"]
        port = normalized["port"]
        endpoint = normalized["url"]
        dns_status, dns_finding = classify.classify_dns(dns, host)
        tls_status, tls_finding = classify.classify_tls(tls, host, port)
        http_status, http_finding = classify.classify_http(http, endpoint)
        probe_status = {
            "dns": dns_status,
            "tls": tls_status,
            "http": http_status,
        }
        findings = [dns_finding, tls_finding, http_finding]
        overall_status = classify.overall_status(probe_status)
        primary_issue_layer = classify.primary_issue_layer(probe_status)
        recommendations = recommend.recommendations(
            host=host,
            port=port,
            endpoint=endpoint,
            timeout=timeout_value,
            probe_status=probe_status,
            dns=dns,
            tls=tls,
            http=http,
        )
        return results.success_result(
            normalized=normalized,
            timeout=timeout_value,
            overall_status=overall_status,
            primary_issue_layer=primary_issue_layer,
            partial="failed" in probe_status.values(),
            probe_status=probe_status,
            findings=findings,
            recommendations=recommendations,
            dns=dns,
            tls=tls,
            http=http,
        )

    @staticmethod
    def _run_probe(layer, callback, *args):
        try:
            result = callback(*args)
        except Exception as exc:  # Defensive boundary between independent probes.
            return {
                "success": False,
                "error_code": "probe_exception",
                "error": f"{type(exc).__name__}: {exc}",
                "message": f"The {layer} probe raised an unexpected exception.",
            }
        if not isinstance(result, dict):
            return {
                "success": False,
                "error_code": "invalid_probe_result",
                "error": (
                    f"The {layer} probe returned {type(result).__name__}, "
                    "expected a dictionary."
                ),
                "message": f"The {layer} probe returned an invalid result shape.",
            }
        return result

    @staticmethod
    def _nxdomain_result(normalized, timeout_value, dns):
        host = normalized["host"]
        findings = [
            results.finding(
                "dns",
                "unhealthy",
                f"DNS reports that '{host}' does not exist.",
            ),
            results.finding(
                "tls",
                "skipped",
                "TLS was skipped because an authoritative DNS name-not-found result makes the hostname unreachable.",
            ),
            results.finding(
                "http",
                "skipped",
                "HTTP was skipped because the hostname cannot currently resolve.",
            ),
        ]
        recommendations = [
            {
                "priority": "high",
                "action": "Verify the hostname spelling, registration, delegated nameservers, and required DNS records before checking TLS or HTTP.",
                "reason": "DNS name-not-found is upstream of both TLS and HTTP.",
                "command": f"qzx checkDns {host} --json",
            }
        ]
        return results.success_result(
            normalized=normalized,
            timeout=timeout_value,
            overall_status="unhealthy",
            primary_issue_layer="dns",
            partial=False,
            probe_status={
                "dns": "unhealthy",
                "tls": "skipped",
                "http": "skipped",
            },
            findings=findings,
            recommendations=recommendations,
            dns=dns,
            tls=None,
            http=None,
        )
