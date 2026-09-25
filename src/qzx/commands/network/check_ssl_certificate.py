#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Inspect an SSL/TLS certificate while reporting trust separately."""

import socket
import ssl
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from qzx.commands.network import _check_ssl_certificate_result as result_support
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
        host, port_num, error = result_support.normalize_target(host, port)
        if error:
            return error
        evidence, error = self._certificate_evidence(host, port_num)
        if error:
            return error
        cert = evidence["certificate"]
        if not cert:
            return {
                "success": False,
                "error_code": "certificate_decode_failed",
                "error": "The peer certificate could not be decoded.",
                "message": (
                    f"Connected to {host}:{port_num}, but certificate details "
                    "were unavailable."
                ),
            }
        return result_support.build_result(
            cert,
            host,
            port_num,
            evidence,
            self._parse_date,
            self._parse_rdn,
            self._match_hostname,
        )

    def _certificate_evidence(self, host, port):
        try:
            cert, cipher, tls_version = self._connect(
                host,
                port,
                self._create_tls_context(),
                binary=False,
            )
            return self._evidence(cert, cipher, tls_version, True, None), None
        except ssl.SSLCertVerificationError as exc:
            return self._unverified_evidence(host, port, str(exc))
        except Exception as exc:
            return None, self._connection_error(host, port, exc)

    def _unverified_evidence(self, host, port, verification_error):
        try:
            der_cert, cipher, tls_version = self._connect(
                host,
                port,
                self._create_unverified_tls_context(),
                binary=True,
            )
            cert = self._decode_der_certificate(der_cert)
        except Exception as exc:
            return None, self._connection_error(host, port, exc)
        return self._evidence(
            cert,
            cipher,
            tls_version,
            False,
            verification_error,
        ), None

    @staticmethod
    def _evidence(cert, cipher, tls_version, chain_trusted, verification_error):
        return {
            "certificate": cert,
            "cipher": cipher,
            "tls_version": tls_version,
            "chain_trusted": chain_trusted,
            "verification_error": verification_error,
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
            wildcard_match = (
                candidate_labels
                and candidate_labels[0] == "*"
                and len(candidate_labels) == len(host_labels)
                and candidate_labels[1:] == host_labels[1:]
            )
            if wildcard_match:
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
                "remediation": (
                    "Verify DNS, network access, port, and TLS service availability."
                ),
            },
        }
