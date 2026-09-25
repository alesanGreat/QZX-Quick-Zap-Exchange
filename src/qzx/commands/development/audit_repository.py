#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Security and quality audit of a Git repository."""

import ipaddress
import socket
import urllib.request

from qzx.core.command_base import CommandBase

from ._repository_audit_support import execute_repository_audit


class AuditRepositoryCommand(CommandBase):
    """Audit a repository for common security and quality problems."""

    name = "auditRepository"
    description = (
        "Runs security and quality audits on a Git repository "
        "(secrets, large files, duplicates, .gitignore compliance, licenses)"
    )
    category = "development"

    parameters = [
        {
            "name": "path",
            "description": "Path to the repository to audit (default: '.')",
            "required": False,
            "default": ".",
        }
    ]

    examples = [
        {
            "command": "qzx auditRepository",
            "description": "Audit the current repository",
        },
        {
            "command": "qzx auditRepository C:/other/project",
            "description": "Audit project at specified path",
        },
    ]

    @staticmethod
    def _literal_ip_address(hostname):
        """Parse canonical and legacy IPv4 spellings without resolving DNS."""
        try:
            return ipaddress.ip_address(hostname)
        except ValueError:
            pass
        if ":" in hostname:
            return None
        try:
            normalized = socket.inet_ntoa(socket.inet_aton(hostname))
        except OSError:
            return None
        return ipaddress.ip_address(normalized)

    @classmethod
    def _is_documentation_placeholder_url(cls, parsed_link):
        """Return whether a documentation URL must not be fetched."""
        try:
            hostname = parsed_link.hostname
        except ValueError:
            return False
        if hostname is None:
            return False
        normalized = hostname.casefold().rstrip(".")
        reserved = {
            "example",
            "example.com",
            "example.net",
            "example.org",
            "invalid",
            "localhost",
            "test",
        }
        suffixes = tuple(f".{host}" for host in reserved)
        if normalized in reserved or normalized.endswith(suffixes):
            return True
        address = cls._literal_ip_address(normalized)
        return address is not None and not address.is_global

    @staticmethod
    def _open_url(request, timeout):
        """Open one external documentation URL through an injectable seam."""
        return urllib.request.urlopen(request, timeout=timeout)

    def execute(self, path="."):
        """Execute the repository audit."""
        return execute_repository_audit(self, path)
