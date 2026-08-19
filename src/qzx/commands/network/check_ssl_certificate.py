#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Inspect an SSL/TLS certificate while reporting trust separately."""

import socket
import ssl
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from qzx.core.command_base import CommandBase


class CheckSslCertificateCommand(CommandBase):
    """Fetch, decode, and analyze a server certificate."""

    name = "checkSslCertificate"
    description = "Inspects certificate dates, hostname coverage, and trust-chain validation"
    category = "network"

    parameters = [
        {
            "name": "host",
            "description": "Hostname of the server to check (for example, example.com)",
            "required": True,
            "type": "str",
        },
        {
            "name": "port",
            "description": "TLS port number",
            "required": False,
            "default": 443,
            "type": "int",
        },
    ]

    examples = [
        {
            "command": "qzx checkSslCertificate example.com",
            "description": "Inspect and validate example.com's certificate",
        },
        {
            "command": "qzx checkSslCertificate expired.badssl.com 443",
            "description": "Inspect an expired certificate while reporting the trust failure",
        },
    ]

    def execute(self, host, port=443):
        host = str(host).strip().rstrip(".")
        if not host:
            return {
                "success": False,
                "error_code": "invalid_host",
                "error": "Host name must not be empty.",
                "message": "Provide a DNS hostname to inspect.",
            }

        try:
            port_num = int(port)
        except (TypeError, ValueError):
            return {
                "success": False,
                "error_code": "invalid_port",
                "error": f"Port must be an integer, received '{port}'.",
                "message": "Provide a TCP port between 1 and 65535.",
            }
        if not 1 <= port_num <= 65535:
            return {
                "success": False,
                "error_code": "invalid_port",
                "error": f"Port {port_num} is outside the valid range.",
                "message": "Provide a TCP port between 1 and 65535.",
            }

        chain_trusted = True
        verification_error = None
        try:
            cert, cipher, tls_version = self._connect(
                host,
                port_num,
                self._create_tls_context(),
                binary=False,
            )
        except ssl.SSLCertVerificationError as exc:
            chain_trusted = False
            verification_error = str(exc)
            try:
                unverified_context = self._create_unverified_tls_context()
                der_cert, cipher, tls_version = self._connect(
                    host,
                    port_num,
                    unverified_context,
                    binary=True,
                )
                cert = self._decode_der_certificate(der_cert)
            except Exception as fallback_exc:
                return self._connection_error(host, port_num, fallback_exc)
        except Exception as exc:
            return self._connection_error(host, port_num, exc)

        if not cert:
            return {
                "success": False,
                "error_code": "certificate_decode_failed",
                "error": "The peer certificate could not be decoded.",
                "message": f"Connected to {host}:{port_num}, but certificate details were unavailable.",
            }

        not_before = self._parse_date(cert.get("notBefore", ""))
        not_after = self._parse_date(cert.get("notAfter", ""))
        now = datetime.now(timezone.utc)
        is_started = not_before is None or now >= not_before
        is_expired = not_after is None or now > not_after
        days_remaining = (not_after - now).days if not_after else None

        subject = self._parse_rdn(cert.get("subject", []))
        issuer = self._parse_rdn(cert.get("issuer", []))
        sans = [
            value
            for kind, value in cert.get("subjectAltName", [])
            if kind == "DNS"
        ]
        hostname_match = self._match_hostname(
            host,
            subject.get("commonName", ""),
            sans,
        )
        certificate_valid = (
            chain_trusted
            and is_started
            and not is_expired
            and hostname_match
        )

        reasons = []
        if not chain_trusted:
            reasons.append("UNTRUSTED_CHAIN")
        if not is_started:
            reasons.append("NOT_YET_VALID")
        if is_expired:
            reasons.append("EXPIRED")
        if not hostname_match:
            reasons.append("HOSTNAME_MISMATCH")
        status = "VALID" if certificate_valid else "INVALID"
        if reasons:
            status += " (" + ", ".join(reasons) + ")"

        cipher_name = cipher[0] if cipher else None
        cipher_protocol = cipher[1] if cipher and len(cipher) > 1 else None
        cipher_bits = cipher[2] if cipher and len(cipher) > 2 else None
        message_lines = [
            f"SSL certificate diagnostic for '{host}:{port_num}':",
            f"- Status: {status}",
            f"- Chain trusted: {chain_trusted}",
            f"- Hostname match: {hostname_match}",
            f"- Subject CN: {subject.get('commonName', 'unknown')}",
            f"- Issuer CN: {issuer.get('commonName', 'unknown')}",
            f"- TLS version: {tls_version or 'unknown'}",
            f"- Cipher: {cipher_name or 'unknown'}",
        ]
        if not_after:
            message_lines.append(
                f"- Expires: {not_after.isoformat()} ({days_remaining} day(s) remaining)"
            )

        return {
            "success": True,
            "message": "\n".join(message_lines),
            "host": host,
            "port": port_num,
            "is_valid": certificate_valid,
            "chain_trusted": chain_trusted,
            "verification_error": verification_error,
            "is_expired": is_expired,
            "is_started": is_started,
            "hostname_match": hostname_match,
            "days_remaining": days_remaining,
            "subject": subject,
            "issuer": issuer,
            "subject_alt_names": sans,
            "ssl_version": tls_version,
            "cipher_suite": cipher_name,
            "cipher_protocol": cipher_protocol,
            "cipher_bits": cipher_bits,
            "dates": {
                "not_before": not_before.isoformat() if not_before else None,
                "not_after": not_after.isoformat() if not_after else None,
            },
        }

    @staticmethod
    def _create_tls_context():
        """Create a verified context that never negotiates obsolete TLS."""

        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context

    @classmethod
    def _create_unverified_tls_context(cls):
        """Create a diagnostic context with the same protocol floor."""

        context = cls._create_tls_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    @staticmethod
    def _connect(host, port, context, binary=False):
        with socket.create_connection((host, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=host) as secure_socket:
                return (
                    secure_socket.getpeercert(binary_form=binary),
                    secure_socket.cipher(),
                    secure_socket.version(),
                )

    @staticmethod
    def _decode_der_certificate(der_certificate):
        if not der_certificate:
            return None
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="ascii",
                suffix=".pem",
                delete=False,
            ) as temporary_file:
                temporary_path = temporary_file.name
                temporary_file.write(ssl.DER_cert_to_PEM_cert(der_certificate))
            return ssl._ssl._test_decode_cert(temporary_path)
        finally:
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)

    @staticmethod
    def _parse_date(date_text):
        if not date_text:
            return None
        for date_format in (
            "%b %d %H:%M:%S %Y %Z",
            "%b  %d %H:%M:%S %Y %Z",
            "%b %d %H:%M:%S %Y",
            "%Y%m%d%H%M%SZ",
        ):
            try:
                parsed = datetime.strptime(date_text, date_format)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_rdn(rdn_structure):
        flattened = {}
        for rdn in rdn_structure:
            for item in rdn:
                if len(item) == 2:
                    flattened[item[0]] = item[1]
        return flattened

    @staticmethod
    def _match_hostname(host, common_name, subject_alt_names):
        candidates = subject_alt_names or ([common_name] if common_name else [])
        host_labels = host.lower().split(".")
        for candidate in candidates:
            candidate_labels = candidate.lower().rstrip(".").split(".")
            if candidate_labels == host_labels:
                return True
            if (
                candidate_labels
                and candidate_labels[0] == "*"
                and len(candidate_labels) == len(host_labels)
                and candidate_labels[1:] == host_labels[1:]
            ):
                return True
        return False

    @staticmethod
    def _connection_error(host, port, exc):
        return {
            "success": False,
            "error_code": "tls_connection_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "message": f"Failed to inspect the TLS certificate for {host}:{port}.",
            "details": {
                "host": host,
                "port": port,
                "remediation": "Verify DNS, network access, port, and TLS service availability.",
            },
        }
