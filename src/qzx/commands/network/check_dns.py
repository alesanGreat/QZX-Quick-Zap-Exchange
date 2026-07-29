#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Query common DNS record types with structured resolution status."""

from qzx.core.command_base import CommandBase


class CheckDnsCommand(CommandBase):
    """
    Command to inspect and return all common DNS records for a specific domain name.
    """
    
    name = "checkDns"
    description = (
        "Queries A, AAAA, MX, TXT, NS, and CNAME DNS records for a given domain"
    )
    category = "network"
    
    parameters = [
        {
            'name': 'domain',
            'description': 'Domain name to query (e.g. google.com)',
            'required': True
        }
    ]
    
    examples = [
        {
            'command': 'qzx checkDns google.com',
            'description': 'Get all DNS records for google.com'
        }
    ]

    def __init__(self, resolver_factory=None):
        self._resolver_factory = resolver_factory

    def execute(self, domain):
        """
        Queries DNS records for a domain
        
        Args:
            domain (str): Domain to query
            
        Returns:
            Dictionary with resolved DNS records
        """
        domain = str(domain).strip().rstrip(".").lower()
        if not domain:
            return {
                "success": False,
                "error_code": "invalid_domain",
                "error": "Domain name must not be empty.",
                "message": "Domain name must not be empty.",
                "remediation": "Pass a DNS name such as example.com.",
            }

        try:
            import dns.exception
            import dns.name
            import dns.resolver
        except ImportError:
            return {
                "success": False,
                "error_code": "missing_dependency",
                "error": "The required 'dnspython' package is not installed.",
                "remediation": "Reinstall QZX with its required dependencies.",
                "details": {
                    "dependency": "dnspython",
                },
                "message": (
                    "DNS inspection requires the maintained 'dnspython' "
                    "dependency. Reinstall QZX dependencies and try again."
                ),
            }

        try:
            ascii_domain = domain.encode("idna").decode("ascii")
            dns.name.from_text(ascii_domain + ".")
        except (
            UnicodeError,
            dns.name.BadEscape,
            dns.name.EmptyLabel,
            dns.name.NameTooLong,
        ):
            return {
                "success": False,
                "error_code": "invalid_domain",
                "error": f"'{domain}' is not a valid DNS name.",
                "message": (
                    f"Failed to inspect DNS: '{domain}' is not a valid DNS name."
                ),
                "remediation": "Pass a valid DNS name such as example.com.",
            }

        record_types = ("A", "AAAA", "MX", "TXT", "NS", "CNAME")
        results = {
            record_type: []
            for record_type in record_types
        }
        record_status = {
            record_type: "pending"
            for record_type in record_types
        }
        ttl = {
            record_type: None
            for record_type in record_types
        }
        errors = []

        try:
            resolver = (
                self._resolver_factory()
                if self._resolver_factory is not None
                else dns.resolver.Resolver(configure=True)
            )
        except (OSError, dns.exception.DNSException) as exc:
            return {
                "success": False,
                "error_code": "dns_resolver_unavailable",
                "error": f"Could not initialize the DNS resolver: {exc}",
                "remediation": (
                    "Check the operating system DNS configuration and retry."
                ),
                "message": (
                    "DNS inspection could not start because no usable "
                    "resolver configuration was available."
                ),
            }
        for r_type in record_types:
            try:
                answer = resolver.resolve(
                    ascii_domain,
                    r_type,
                    lifetime=10.0,
                    search=False,
                )
                values = [
                    self._format_rdata(r_type, rdata)
                    for rdata in answer
                ]
                results[r_type] = list(dict.fromkeys(values))
                ttl[r_type] = answer.rrset.ttl if answer.rrset is not None else None
                if (
                    r_type == "MX"
                    and any(
                        rdata.preference == 0
                        and rdata.exchange == dns.name.root
                        for rdata in answer
                    )
                ):
                    record_status[r_type] = "null_mx"
                else:
                    record_status[r_type] = "resolved"
            except dns.resolver.NoAnswer:
                record_status[r_type] = "no_record"
            except dns.resolver.NXDOMAIN:
                return {
                    "success": False,
                    "error_code": "dns_name_not_found",
                    "domain": ascii_domain,
                    "records": results,
                    # NXDOMAIN is authoritative for the queried name, not only
                    # for the record type that happened to return it. Earlier
                    # transient per-type failures cannot make records exist.
                    "record_status": {
                        key: "name_not_found"
                        for key in record_status
                    },
                    "errors": [f"DNS name '{ascii_domain}' does not exist."],
                    "error": f"DNS name '{ascii_domain}' does not exist.",
                    "remediation": (
                        "Check the spelling and whether the domain is registered."
                    ),
                    "message": f"DNS name '{ascii_domain}' does not exist.",
                }
            except (
                dns.resolver.LifetimeTimeout,
                dns.resolver.NoNameservers,
                dns.exception.DNSException,
            ) as exc:
                record_status[r_type] = "query_failed"
                errors.append(f"{r_type} query failed: {exc}")

        summary = {k: len(v) for k, v in results.items()}
        successful_queries = sum(
            status in {"resolved", "null_mx", "no_record"}
            for status in record_status.values()
        )

        msg = f"DNS records inspected for '{ascii_domain}':\n"
        for r_type, count in summary.items():
            status = record_status[r_type]
            if status == "null_mx":
                msg += (
                    f"- {r_type}: Null MX (0 .); this domain explicitly "
                    "does not accept email\n"
                )
            elif count > 0:
                values = ", ".join(results[r_type][:3])
                if len(results[r_type]) > 3:
                    values += f" (+{count - 3} more)"
                msg += f"- {r_type} ({count}): {values}\n"
            elif status == "query_failed":
                msg += f"- {r_type}: Query failed\n"
            else:
                msg += f"- {r_type}: None found\n"

        result = {
            "success": successful_queries > 0,
            "domain": ascii_domain,
            "records": results,
            "summary": summary,
            "record_status": record_status,
            "ttl_seconds": ttl,
            "errors": errors,
            "message": msg
        }
        if successful_queries == 0:
            result.update(
                {
                    "error_code": "dns_queries_failed",
                    "error": (
                        "Every DNS record query failed before a definitive "
                        "answer was received."
                    ),
                    "remediation": (
                        "Check network connectivity and configured DNS "
                        "servers, then retry."
                    ),
                }
            )
        return result

    @staticmethod
    def _format_rdata(record_type, rdata):
        """Return a stable, lossless string for a dnspython record."""
        if record_type == "MX":
            return f"{rdata.preference} {rdata.exchange.to_text()}"
        if record_type == "TXT":
            return "".join(
                part.decode("utf-8", errors="replace")
                for part in rdata.strings
            )
        return rdata.to_text()
