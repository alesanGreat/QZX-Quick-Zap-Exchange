"""Actionable recommendations for diagnoseWebsite."""

from __future__ import annotations


def recommendations(*, host, port, endpoint, timeout, probe_status, dns, tls, http):
    """Return ordered next actions without mutating remote state."""
    items = []
    items.extend(_dns_items(host, probe_status["dns"]))
    items.extend(_tls_items(host, port, probe_status["tls"], tls))
    items.extend(_http_items(endpoint, timeout, probe_status["http"], http))
    if items:
        return items
    return [
        {
            "priority": "info",
            "action": "No immediate DNS, TLS, or HTTP repair is indicated. If users still report a problem, investigate application behavior, content, authentication, browser-specific errors, or regional/CDN differences.",
            "reason": "All three website layers passed the current diagnostic.",
        }
    ]


def _dns_items(host, status):
    if status == "failed":
        return [
            {
                "priority": "medium",
                "action": "Retry DNS inspection separately or verify the local resolver before treating DNS as the website root cause.",
                "reason": "The DNS probe itself was inconclusive.",
                "command": f"qzx checkDns {host} --json",
            }
        ]
    if status == "attention":
        return [
            {
                "priority": "high",
                "action": "Verify that the hostname has the intended A, AAAA, or CNAME record.",
                "reason": "DNS answered, but no website-address record was visible to the diagnostic.",
                "command": f"qzx checkDns {host} --json",
            }
        ]
    return []


def _tls_items(host, port, status, tls):
    command = f"qzx checkSslCertificate {host} {port} --json"
    if status == "unhealthy":
        return [
            {
                "priority": "high",
                "action": "Inspect certificate trust, hostname coverage, dates, and the HTTPS listener before debugging application code.",
                "reason": tls.get("message") or tls.get("error") or "TLS validation failed.",
                "command": command,
            }
        ]
    if status == "attention":
        return [
            {
                "priority": "medium",
                "action": "Renew or rotate the certificate before its remaining validity becomes an outage risk.",
                "reason": "The certificate is valid but close to expiry.",
                "command": command,
            }
        ]
    if status == "failed":
        return [
            {
                "priority": "medium",
                "action": "Run the TLS probe separately because the diagnostic engine could not classify this layer.",
                "reason": tls.get("message") or tls.get("error") or "TLS inspection was inconclusive.",
                "command": command,
            }
        ]
    return []


def _http_items(endpoint, timeout, status, http):
    command = f"qzx checkUrlStatus {endpoint} {timeout:g} --json"
    status_code = http.get("status_code") if isinstance(http, dict) else None
    if status == "attention":
        return [
            {
                "priority": "medium",
                "action": "Check application routing, authentication, or the requested path while keeping DNS and TLS evidence as already-known context.",
                "reason": f"The server responded with HTTP {status_code}.",
                "command": command,
            }
        ]
    if status == "unhealthy":
        return [_unhealthy_http_item(command, status_code, http)]
    if status == "failed":
        return [
            {
                "priority": "medium",
                "action": "Run the HTTP probe separately because the diagnostic engine could not classify the response.",
                "reason": http.get("message") or http.get("error") or "HTTP inspection was inconclusive.",
                "command": command,
            }
        ]
    return []


def _unhealthy_http_item(command, status_code, http):
    action = (
        "Inspect the origin application and upstream service health; DNS and TLS results show how far the request progressed."
        if isinstance(status_code, int) and status_code >= 500
        else "Check the HTTPS listener, origin service, firewall/proxy path, and application availability."
    )
    return {
        "priority": "high",
        "action": action,
        "reason": http.get("message") or http.get("status_detail") or "HTTP did not return a healthy response.",
        "command": command,
    }
