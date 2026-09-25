"""Validation and result helpers for checkSslCertificate."""

from __future__ import annotations

from datetime import datetime, timezone


def normalize_target(host, port):
    host = str(host).strip().rstrip(".")
    if not host:
        return None, None, {
            "success": False,
            "error_code": "invalid_host",
            "error": "Host name must not be empty.",
            "message": "Provide a DNS hostname to inspect.",
        }
    try:
        port_num = int(port)
    except (TypeError, ValueError):
        return None, None, {
            "success": False,
            "error_code": "invalid_port",
            "error": f"Port must be an integer, received '{port}'.",
            "message": "Provide a TCP port between 1 and 65535.",
        }
    if not 1 <= port_num <= 65535:
        return None, None, {
            "success": False,
            "error_code": "invalid_port",
            "error": f"Port {port_num} is outside the valid range.",
            "message": "Provide a TCP port between 1 and 65535.",
        }
    return host, port_num, None


def build_result(cert, host, port, evidence, parse_date, parse_rdn, match_hostname):
    """Analyze decoded certificate evidence and build the public result."""
    facts = _certificate_facts(
        cert,
        host,
        evidence["chain_trusted"],
        parse_date,
        parse_rdn,
        match_hostname,
    )
    cipher = _cipher_parts(evidence["cipher"])
    return _result_payload(host, port, evidence, facts, cipher)


def _result_payload(host, port, evidence, facts, cipher):
    cipher_name, cipher_protocol, cipher_bits = cipher
    return {
        "success": True,
        "message": _message(
            host,
            port,
            facts,
            evidence["chain_trusted"],
            evidence["tls_version"],
            cipher_name,
        ),
        "host": host,
        "port": port,
        "is_valid": facts["is_valid"],
        "chain_trusted": evidence["chain_trusted"],
        "verification_error": evidence["verification_error"],
        "is_expired": facts["is_expired"],
        "is_started": facts["is_started"],
        "hostname_match": facts["hostname_match"],
        "days_remaining": facts["days_remaining"],
        "subject": facts["subject"],
        "issuer": facts["issuer"],
        "subject_alt_names": facts["sans"],
        "ssl_version": evidence["tls_version"],
        "cipher_suite": cipher_name,
        "cipher_protocol": cipher_protocol,
        "cipher_bits": cipher_bits,
        "dates": {
            "not_before": _iso_or_none(facts["not_before"]),
            "not_after": _iso_or_none(facts["not_after"]),
        },
    }


def _certificate_facts(cert, host, chain_trusted, parse_date, parse_rdn, match_hostname):
    not_before = parse_date(cert.get("notBefore", ""))
    not_after = parse_date(cert.get("notAfter", ""))
    now = datetime.now(timezone.utc)
    is_started = not_before is None or now >= not_before
    is_expired = not_after is None or now > not_after
    days_remaining = (not_after - now).days if not_after else None
    subject = parse_rdn(cert.get("subject", []))
    issuer = parse_rdn(cert.get("issuer", []))
    sans = [value for kind, value in cert.get("subjectAltName", []) if kind == "DNS"]
    hostname_match = match_hostname(host, subject.get("commonName", ""), sans)
    is_valid = chain_trusted and is_started and not is_expired and hostname_match
    return {
        "not_before": not_before,
        "not_after": not_after,
        "is_started": is_started,
        "is_expired": is_expired,
        "days_remaining": days_remaining,
        "subject": subject,
        "issuer": issuer,
        "sans": sans,
        "hostname_match": hostname_match,
        "is_valid": is_valid,
        "status": _status(is_valid, chain_trusted, is_started, is_expired, hostname_match),
    }


def _status(is_valid, chain_trusted, is_started, is_expired, hostname_match):
    reasons = []
    if not chain_trusted:
        reasons.append("UNTRUSTED_CHAIN")
    if not is_started:
        reasons.append("NOT_YET_VALID")
    if is_expired:
        reasons.append("EXPIRED")
    if not hostname_match:
        reasons.append("HOSTNAME_MISMATCH")
    status = "VALID" if is_valid else "INVALID"
    return status + (" (" + ", ".join(reasons) + ")" if reasons else "")


def _message(host, port, facts, chain_trusted, tls_version, cipher_name):
    lines = [
        f"SSL certificate diagnostic for '{host}:{port}':",
        f"- Status: {facts['status']}",
        f"- Chain trusted: {chain_trusted}",
        f"- Hostname match: {facts['hostname_match']}",
        f"- Subject CN: {facts['subject'].get('commonName', 'unknown')}",
        f"- Issuer CN: {facts['issuer'].get('commonName', 'unknown')}",
        f"- TLS version: {tls_version or 'unknown'}",
        f"- Cipher: {cipher_name or 'unknown'}",
    ]
    if facts["not_after"]:
        lines.append(
            f"- Expires: {facts['not_after'].isoformat()} "
            f"({facts['days_remaining']} day(s) remaining)"
        )
    return "\n".join(lines)


def _cipher_parts(cipher):
    name = cipher[0] if cipher else None
    protocol = cipher[1] if cipher and len(cipher) > 1 else None
    bits = cipher[2] if cipher and len(cipher) > 2 else None
    return name, protocol, bits


def _iso_or_none(value):
    return value.isoformat() if value else None
