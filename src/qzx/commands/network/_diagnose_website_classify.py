"""Layer classification for diagnoseWebsite."""

from __future__ import annotations

from qzx.commands.network._diagnose_website_results import finding


def classify_dns(result, host):
    if result.get("error_code") in {"probe_exception", "invalid_probe_result"}:
        return "failed", finding(
            "dns",
            "failed",
            "The DNS diagnostic engine failed unexpectedly, so this layer is inconclusive.",
        )
    if not result.get("success"):
        return "failed", finding(
            "dns",
            "failed",
            result.get("message") or result.get("error") or "DNS inspection was inconclusive.",
        )
    records = result.get("records") or {}
    addresses = list(records.get("A") or []) + list(records.get("AAAA") or [])
    cnames = list(records.get("CNAME") or [])
    if addresses or cnames:
        return "healthy", finding(
            "dns",
            "healthy",
            f"DNS resolved website-address records for '{host}'.",
        )
    return "attention", finding(
        "dns",
        "attention",
        f"DNS queries completed for '{host}', but no A, AAAA, or CNAME website-address record was returned.",
    )


def classify_tls(result, host, port):
    if result.get("error_code") in {"probe_exception", "invalid_probe_result"}:
        return "failed", finding(
            "tls",
            "failed",
            "The TLS diagnostic engine failed unexpectedly, so this layer is inconclusive.",
        )
    if not result.get("success"):
        return "unhealthy", finding(
            "tls",
            "unhealthy",
            result.get("message") or result.get("error") or f"TLS could not be established for {host}:{port}.",
        )
    if not result.get("is_valid"):
        return "unhealthy", finding(
            "tls",
            "unhealthy",
            f"TLS responded on {host}:{port}, but the certificate is not valid for trusted HTTPS use.",
        )
    days_remaining = result.get("days_remaining")
    if isinstance(days_remaining, (int, float)) and days_remaining < 30:
        return "attention", finding(
            "tls",
            "attention",
            f"TLS is valid, but the certificate has only {days_remaining:g} day(s) remaining.",
        )
    return "healthy", finding(
        "tls",
        "healthy",
        f"TLS certificate validation succeeded for {host}:{port}.",
    )


def classify_http(result, endpoint):
    failed_probe = result.get("error_code") in {"probe_exception", "invalid_probe_result"}
    if failed_probe or not result.get("success"):
        return "failed", finding(
            "http",
            "failed",
            result.get("message") or result.get("error") or "The HTTP diagnostic engine was inconclusive.",
        )
    status_code = result.get("status_code")
    if result.get("is_online"):
        return "healthy", finding(
            "http",
            "healthy",
            f"HTTP reached '{endpoint}' successfully with status {status_code}.",
        )
    if isinstance(status_code, int) and 400 <= status_code < 500:
        return "attention", finding(
            "http",
            "attention",
            f"The web server is reachable, but '{endpoint}' returned HTTP {status_code}.",
        )
    if isinstance(status_code, int) and status_code >= 500:
        return "unhealthy", finding(
            "http",
            "unhealthy",
            f"The web server returned HTTP {status_code}, indicating a server-side failure for '{endpoint}'.",
        )
    return "unhealthy", finding(
        "http",
        "unhealthy",
        result.get("status_detail") or f"No usable HTTP response was received from '{endpoint}'.",
    )


def overall_status(probe_status):
    values = set(probe_status.values())
    if "unhealthy" in values:
        return "unhealthy"
    if "failed" in values:
        return "partial"
    if "attention" in values:
        return "attention"
    return "healthy"


def primary_issue_layer(probe_status):
    for state in ("unhealthy", "attention"):
        for layer in ("dns", "tls", "http"):
            if probe_status.get(layer) == state:
                return layer
    if "failed" in probe_status.values():
        return "diagnostic"
    return None
