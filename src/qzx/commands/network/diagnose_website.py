#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Diagnose a public website by correlating DNS, TLS, and HTTP evidence."""

import re
import urllib.parse

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

    _control_characters = re.compile(r"[\x00-\x1f\x7f]")
    _unsafe_input = re.compile(r"[\s\\`\"'$&;|<>^!%()\[\]{}*]")
    _scheme = re.compile(r"^([a-z][a-z0-9+.-]*)://", re.IGNORECASE)
    _safe_path = re.compile(r"^[a-zA-Z0-9/_.~:-]*$")
    _safe_label = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

    def __init__(
        self,
        *,
        dns_command=None,
        tls_command=None,
        http_command=None,
    ):
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

        normalized, error = self._normalize_target(target)
        if error is not None:
            return error

        try:
            timeout_value = float(timeout)
        except (TypeError, ValueError):
            return self._failure(
                "invalid_timeout",
                f"Timeout must be a number between 0.1 and 60 seconds, received '{timeout}'.",
                target=normalized["target"],
            )
        if not 0.1 <= timeout_value <= 60:
            return self._failure(
                "invalid_timeout",
                f"Timeout {timeout_value:g} is outside the supported 0.1-60 second range.",
                target=normalized["target"],
            )

        host = normalized["host"]
        port = normalized["port"]
        endpoint = normalized["url"]

        dns = self._run_probe("dns", self._dns.execute, host)
        if dns.get("error_code") == "dns_name_not_found":
            findings = [
                self._finding(
                    "dns",
                    "unhealthy",
                    f"DNS reports that '{host}' does not exist.",
                ),
                self._finding(
                    "tls",
                    "skipped",
                    "TLS was skipped because an authoritative DNS name-not-found result makes the hostname unreachable.",
                ),
                self._finding(
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
            return self._success_result(
                normalized=normalized,
                timeout=timeout_value,
                overall_status="unhealthy",
                primary_issue_layer="dns",
                partial=False,
                probe_status={"dns": "unhealthy", "tls": "skipped", "http": "skipped"},
                findings=findings,
                recommendations=recommendations,
                dns=dns,
                tls=None,
                http=None,
            )

        dns_status, dns_finding = self._classify_dns(dns, host)
        tls = self._run_probe("tls", self._tls.execute, host, port)
        tls_status, tls_finding = self._classify_tls(tls, host, port)
        http = self._run_probe("http", self._http.execute, endpoint, timeout_value)
        http_status, http_finding = self._classify_http(http, endpoint)

        probe_status = {
            "dns": dns_status,
            "tls": tls_status,
            "http": http_status,
        }
        findings = [dns_finding, tls_finding, http_finding]
        overall_status = self._overall_status(probe_status)
        primary_issue_layer = self._primary_issue_layer(probe_status)
        partial = "failed" in probe_status.values()
        recommendations = self._recommendations(
            host=host,
            port=port,
            endpoint=endpoint,
            timeout=timeout_value,
            probe_status=probe_status,
            dns=dns,
            tls=tls,
            http=http,
        )

        return self._success_result(
            normalized=normalized,
            timeout=timeout_value,
            overall_status=overall_status,
            primary_issue_layer=primary_issue_layer,
            partial=partial,
            probe_status=probe_status,
            findings=findings,
            recommendations=recommendations,
            dns=dns,
            tls=tls,
            http=http,
        )

    @classmethod
    def _normalize_target(cls, target):
        if not isinstance(target, str):
            return None, cls._failure(
                "invalid_target",
                "Website target must be a domain name or HTTPS URL.",
                target=target,
            )
        raw = target.strip()
        if not raw or len(raw) > 2048:
            return None, cls._failure(
                "invalid_target",
                "Website target must contain between 1 and 2048 characters.",
                target=raw,
            )
        if cls._control_characters.search(raw) or cls._unsafe_input.search(raw):
            return None, cls._failure(
                "unsafe_target",
                "Website target contains whitespace or shell-sensitive characters that are not accepted by this workflow.",
                target=raw,
            )
        if any(character in raw for character in "?@#"):
            return None, cls._failure(
                "private_target_component",
                "Query strings, fragments, and user-info are intentionally excluded from website diagnosis targets.",
                target=raw,
            )

        scheme_match = cls._scheme.match(raw)
        if scheme_match and scheme_match.group(1).lower() != "https":
            return None, cls._failure(
                "unsupported_scheme",
                "diagnoseWebsite currently accepts HTTPS targets only; omit the scheme to use HTTPS by default.",
                target=raw,
            )
        candidate = raw if scheme_match else "https://" + raw
        try:
            parsed = urllib.parse.urlsplit(candidate)
            port = parsed.port or 443
        except ValueError:
            return None, cls._failure(
                "invalid_target",
                "Website target contains an invalid hostname or port.",
                target=raw,
            )

        if parsed.scheme.lower() != "https" or not parsed.hostname:
            return None, cls._failure(
                "invalid_target",
                "Website target must be a valid domain name or HTTPS URL.",
                target=raw,
            )
        if parsed.username or parsed.password:
            return None, cls._failure(
                "private_target_component",
                "Embedded credentials are intentionally excluded from website diagnosis targets.",
                target=raw,
            )
        if parsed.query or parsed.fragment:
            return None, cls._failure(
                "private_target_component",
                "Query strings and fragments are intentionally excluded from website diagnosis targets.",
                target=raw,
            )
        if not 1 <= port <= 65535:
            return None, cls._failure(
                "invalid_target",
                "Website target port must be between 1 and 65535.",
                target=raw,
            )
        if not cls._safe_path.fullmatch(parsed.path):
            return None, cls._failure(
                "unsafe_target",
                "Website path contains characters outside the shell-neutral subset supported by this workflow.",
                target=raw,
            )

        try:
            host = parsed.hostname.rstrip(".").lower().encode("idna").decode("ascii")
        except UnicodeError:
            return None, cls._failure(
                "invalid_target",
                "Website target contains a hostname that cannot be represented as a DNS name.",
                target=raw,
            )
        labels = host.split(".")
        if (
            not host
            or len(host) > 254
            or re.fullmatch(r"[0-9.]+", host)
            or re.fullmatch(r"0x[0-9a-f]+", host)
            or not all(cls._safe_label.fullmatch(label) for label in labels)
        ):
            return None, cls._failure(
                "invalid_target",
                "Website target must contain a valid DNS hostname rather than a numeric address.",
                target=raw,
            )

        port_suffix = "" if port == 443 else f":{port}"
        path = parsed.path
        endpoint = f"https://{host}{port_suffix}"
        if path and path != "/":
            endpoint += path

        return {
            "input": raw,
            "target": endpoint,
            "host": host,
            "port": port,
            "path": path or "/",
            "url": endpoint,
        }, None

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
                "error": f"The {layer} probe returned {type(result).__name__}, expected a dictionary.",
                "message": f"The {layer} probe returned an invalid result shape.",
            }
        return result

    @classmethod
    def _classify_dns(cls, result, host):
        if result.get("error_code") in {"probe_exception", "invalid_probe_result"}:
            return "failed", cls._finding(
                "dns", "failed", "The DNS diagnostic engine failed unexpectedly, so this layer is inconclusive."
            )
        if not result.get("success"):
            return "failed", cls._finding(
                "dns",
                "failed",
                result.get("message") or result.get("error") or "DNS inspection was inconclusive.",
            )
        records = result.get("records") or {}
        addresses = list(records.get("A") or []) + list(records.get("AAAA") or [])
        cnames = list(records.get("CNAME") or [])
        if addresses or cnames:
            return "healthy", cls._finding(
                "dns",
                "healthy",
                f"DNS resolved website-address records for '{host}'.",
            )
        return "attention", cls._finding(
            "dns",
            "attention",
            f"DNS queries completed for '{host}', but no A, AAAA, or CNAME website-address record was returned.",
        )

    @classmethod
    def _classify_tls(cls, result, host, port):
        if result.get("error_code") in {"probe_exception", "invalid_probe_result"}:
            return "failed", cls._finding(
                "tls", "failed", "The TLS diagnostic engine failed unexpectedly, so this layer is inconclusive."
            )
        if not result.get("success"):
            return "unhealthy", cls._finding(
                "tls",
                "unhealthy",
                result.get("message") or result.get("error") or f"TLS could not be established for {host}:{port}.",
            )
        if not result.get("is_valid"):
            return "unhealthy", cls._finding(
                "tls",
                "unhealthy",
                f"TLS responded on {host}:{port}, but the certificate is not valid for trusted HTTPS use.",
            )
        days_remaining = result.get("days_remaining")
        if isinstance(days_remaining, (int, float)) and days_remaining < 30:
            return "attention", cls._finding(
                "tls",
                "attention",
                f"TLS is valid, but the certificate has only {days_remaining:g} day(s) remaining.",
            )
        return "healthy", cls._finding(
            "tls", "healthy", f"TLS certificate validation succeeded for {host}:{port}."
        )

    @classmethod
    def _classify_http(cls, result, endpoint):
        if result.get("error_code") in {"probe_exception", "invalid_probe_result"} or not result.get("success"):
            return "failed", cls._finding(
                "http",
                "failed",
                result.get("message") or result.get("error") or "The HTTP diagnostic engine was inconclusive.",
            )
        status_code = result.get("status_code")
        if result.get("is_online"):
            return "healthy", cls._finding(
                "http",
                "healthy",
                f"HTTP reached '{endpoint}' successfully with status {status_code}.",
            )
        if isinstance(status_code, int) and 400 <= status_code < 500:
            return "attention", cls._finding(
                "http",
                "attention",
                f"The web server is reachable, but '{endpoint}' returned HTTP {status_code}.",
            )
        if isinstance(status_code, int) and status_code >= 500:
            return "unhealthy", cls._finding(
                "http",
                "unhealthy",
                f"The web server returned HTTP {status_code}, indicating a server-side failure for '{endpoint}'.",
            )
        return "unhealthy", cls._finding(
            "http",
            "unhealthy",
            result.get("status_detail") or f"No usable HTTP response was received from '{endpoint}'.",
        )

    @staticmethod
    def _overall_status(probe_status):
        values = set(probe_status.values())
        if "unhealthy" in values:
            return "unhealthy"
        if "failed" in values:
            return "partial"
        if "attention" in values:
            return "attention"
        return "healthy"

    @staticmethod
    def _primary_issue_layer(probe_status):
        for state in ("unhealthy", "attention"):
            for layer in ("dns", "tls", "http"):
                if probe_status.get(layer) == state:
                    return layer
        if "failed" in probe_status.values():
            return "diagnostic"
        return None

    @staticmethod
    def _finding(layer, status, summary):
        return {"layer": layer, "status": status, "summary": summary}

    @classmethod
    def _recommendations(
        cls,
        *,
        host,
        port,
        endpoint,
        timeout,
        probe_status,
        dns,
        tls,
        http,
    ):
        recommendations = []
        if probe_status["dns"] == "failed":
            recommendations.append(
                {
                    "priority": "medium",
                    "action": "Retry DNS inspection separately or verify the local resolver before treating DNS as the website root cause.",
                    "reason": "The DNS probe itself was inconclusive.",
                    "command": f"qzx checkDns {host} --json",
                }
            )
        elif probe_status["dns"] == "attention":
            recommendations.append(
                {
                    "priority": "high",
                    "action": "Verify that the hostname has the intended A, AAAA, or CNAME record.",
                    "reason": "DNS answered, but no website-address record was visible to the diagnostic.",
                    "command": f"qzx checkDns {host} --json",
                }
            )

        if probe_status["tls"] == "unhealthy":
            recommendations.append(
                {
                    "priority": "high",
                    "action": "Inspect certificate trust, hostname coverage, dates, and the HTTPS listener before debugging application code.",
                    "reason": tls.get("message") or tls.get("error") or "TLS validation failed.",
                    "command": f"qzx checkSslCertificate {host} {port} --json",
                }
            )
        elif probe_status["tls"] == "attention":
            recommendations.append(
                {
                    "priority": "medium",
                    "action": "Renew or rotate the certificate before its remaining validity becomes an outage risk.",
                    "reason": "The certificate is valid but close to expiry.",
                    "command": f"qzx checkSslCertificate {host} {port} --json",
                }
            )
        elif probe_status["tls"] == "failed":
            recommendations.append(
                {
                    "priority": "medium",
                    "action": "Run the TLS probe separately because the diagnostic engine could not classify this layer.",
                    "reason": tls.get("message") or tls.get("error") or "TLS inspection was inconclusive.",
                    "command": f"qzx checkSslCertificate {host} {port} --json",
                }
            )

        status_code = http.get("status_code") if isinstance(http, dict) else None
        if probe_status["http"] == "attention":
            recommendations.append(
                {
                    "priority": "medium",
                    "action": "Check application routing, authentication, or the requested path while keeping DNS and TLS evidence as already-known context.",
                    "reason": f"The server responded with HTTP {status_code}.",
                    "command": f"qzx checkUrlStatus {endpoint} {timeout:g} --json",
                }
            )
        elif probe_status["http"] == "unhealthy":
            action = (
                "Inspect the origin application and upstream service health; DNS and TLS results show how far the request progressed."
                if isinstance(status_code, int) and status_code >= 500
                else "Check the HTTPS listener, origin service, firewall/proxy path, and application availability."
            )
            recommendations.append(
                {
                    "priority": "high",
                    "action": action,
                    "reason": http.get("message") or http.get("status_detail") or "HTTP did not return a healthy response.",
                    "command": f"qzx checkUrlStatus {endpoint} {timeout:g} --json",
                }
            )
        elif probe_status["http"] == "failed":
            recommendations.append(
                {
                    "priority": "medium",
                    "action": "Run the HTTP probe separately because the diagnostic engine could not classify the response.",
                    "reason": http.get("message") or http.get("error") or "HTTP inspection was inconclusive.",
                    "command": f"qzx checkUrlStatus {endpoint} {timeout:g} --json",
                }
            )

        if not recommendations:
            recommendations.append(
                {
                    "priority": "info",
                    "action": "No immediate DNS, TLS, or HTTP repair is indicated. If users still report a problem, investigate application behavior, content, authentication, browser-specific errors, or regional/CDN differences.",
                    "reason": "All three website layers passed the current diagnostic.",
                }
            )
        return recommendations

    @classmethod
    def _success_result(
        cls,
        *,
        normalized,
        timeout,
        overall_status,
        primary_issue_layer,
        partial,
        probe_status,
        findings,
        recommendations,
        dns,
        tls,
        http,
    ):
        host = normalized["host"]
        status_text = {
            "healthy": "DNS, TLS, and HTTP all passed",
            "attention": "the website responds but at least one layer needs attention",
            "unhealthy": "at least one website layer is unhealthy",
            "partial": "the diagnosis is partial because a probe was inconclusive",
        }[overall_status]
        primary = (
            f" Most likely layer to inspect first: {primary_issue_layer}."
            if primary_issue_layer
            else ""
        )
        report_lines = [
            f"Website diagnosis for {normalized['url']}",
            f"Overall: {overall_status.upper()}",
        ]
        report_lines.extend(
            f"- {item['layer'].upper()}: {item['status']} - {item['summary']}"
            for item in findings
        )
        if recommendations:
            report_lines.append("Next actions:")
            report_lines.extend(
                f"- [{item['priority']}] {item['action']}"
                for item in recommendations
            )

        return {
            "success": True,
            "message": f"Website diagnosis completed for '{host}': {status_text}.{primary}",
            "target": normalized["target"],
            "host": host,
            "port": normalized["port"],
            "path": normalized["path"],
            "url": normalized["url"],
            "timeout_seconds": timeout,
            "overall_status": overall_status,
            "healthy": overall_status == "healthy",
            "partial": partial,
            "primary_issue_layer": primary_issue_layer,
            "read_only": True,
            "network_requests": True,
            "probe_status": probe_status,
            "findings": findings,
            "recommendations": recommendations,
            "dns": dns,
            "tls": tls,
            "http": http,
            "related_commands": ["checkDns", "checkSslCertificate", "checkUrlStatus"],
            "report": "\n".join(report_lines),
        }

    @staticmethod
    def _failure(error_code, message, **details):
        return {
            "success": False,
            "error_code": error_code,
            "error": message,
            "message": message,
            "remediation": (
                "Pass a hostname such as example.com or a shell-neutral HTTPS URL such as https://example.com/status."
            ),
            "details": details,
        }
