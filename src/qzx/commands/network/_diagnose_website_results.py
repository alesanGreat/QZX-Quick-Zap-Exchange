"""Stable result builders for the diagnoseWebsite workflow."""

from __future__ import annotations


def failure(error_code, message, **details):
    """Build the public failure contract for invalid local inputs."""
    return {
        "success": False,
        "error_code": error_code,
        "error": message,
        "message": message,
        "remediation": (
            "Pass a hostname such as example.com or a shell-neutral HTTPS URL "
            "such as https://example.com/status."
        ),
        "details": details,
    }


def finding(layer, status, summary):
    """Build one ordered layer finding."""
    return {"layer": layer, "status": status, "summary": summary}


def success_result(
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
    """Build the stable successful diagnostic result."""
    host = normalized["host"]
    return {
        "success": True,
        "message": _message(host, overall_status, primary_issue_layer),
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
        "report": _report(normalized["url"], overall_status, findings, recommendations),
    }


def _message(host, overall_status, primary_issue_layer):
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
    return f"Website diagnosis completed for '{host}': {status_text}.{primary}"


def _report(url, overall_status, findings, recommendations):
    lines = [f"Website diagnosis for {url}", f"Overall: {overall_status.upper()}"]
    lines.extend(
        f"- {item['layer'].upper()}: {item['status']} - {item['summary']}"
        for item in findings
    )
    if recommendations:
        lines.append("Next actions:")
        lines.extend(
            f"- [{item['priority']}] {item['action']}" for item in recommendations
        )
    return "\n".join(lines)
