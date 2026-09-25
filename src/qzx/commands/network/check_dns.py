#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Query common DNS record types with structured resolution status."""

from qzx.core.command_base import CommandBase


class CheckDnsCommand(CommandBase):
    """Inspect common DNS records for one domain name."""

    name = "checkDns"
    description = "Queries A, AAAA, MX, TXT, NS, and CNAME DNS records for a given domain"
    category = "network"
    _record_types = ("A", "AAAA", "MX", "TXT", "NS", "CNAME")

    parameters = [
        {
            "name": "domain",
            "description": "Domain name to query (e.g. google.com)",
            "required": True,
        }
    ]

    examples = [
        {
            "command": "qzx checkDns google.com",
            "description": "Get all DNS records for google.com",
        }
    ]

    def __init__(self, resolver_factory=None):
        self._resolver_factory = resolver_factory

    def execute(self, domain):
        """Query the supported DNS record types and return a stable result."""
        domain = str(domain).strip().rstrip(".").lower()
        if not domain:
            return self._invalid_domain("Domain name must not be empty.")

        modules, error = self._dns_modules()
        if error:
            return error
        dns_exception, dns_name, dns_resolver = modules

        ascii_domain, error = self._validated_domain(domain, dns_name)
        if error:
            return error
        resolver, error = self._resolver(dns_exception, dns_resolver)
        if error:
            return error
        return self._query_all(
            ascii_domain,
            resolver,
            dns_exception,
            dns_name,
            dns_resolver,
        )

    @staticmethod
    def _dns_modules():
        try:
            import dns.exception
            import dns.name
            import dns.resolver
        except ImportError:
            return None, {
                "success": False,
                "error_code": "missing_dependency",
                "error": "The required 'dnspython' package is not installed.",
                "remediation": "Reinstall QZX with its required dependencies.",
                "details": {"dependency": "dnspython"},
                "message": (
                    "DNS inspection requires the maintained 'dnspython' dependency. "
                    "Reinstall QZX dependencies and try again."
                ),
            }
        return (dns.exception, dns.name, dns.resolver), None

    def _validated_domain(self, domain, dns_name):
        try:
            ascii_domain = domain.encode("idna").decode("ascii")
            dns_name.from_text(ascii_domain + ".")
        except (
            UnicodeError,
            dns_name.BadEscape,
            dns_name.EmptyLabel,
            dns_name.NameTooLong,
        ):
            return None, self._invalid_domain(
                f"'{domain}' is not a valid DNS name.",
                message=f"Failed to inspect DNS: '{domain}' is not a valid DNS name.",
            )
        return ascii_domain, None

    def _resolver(self, dns_exception, dns_resolver):
        try:
            resolver = (
                self._resolver_factory()
                if self._resolver_factory is not None
                else dns_resolver.Resolver(configure=True)
            )
        except (OSError, dns_exception.DNSException) as exc:
            return None, {
                "success": False,
                "error_code": "dns_resolver_unavailable",
                "error": f"Could not initialize the DNS resolver: {exc}",
                "remediation": "Check the operating system DNS configuration and retry.",
                "message": (
                    "DNS inspection could not start because no usable resolver "
                    "configuration was available."
                ),
            }
        return resolver, None

    def _query_all(self, ascii_domain, resolver, dns_exception, dns_name, dns_resolver):
        records = {record_type: [] for record_type in self._record_types}
        statuses = {record_type: "pending" for record_type in self._record_types}
        ttl = {record_type: None for record_type in self._record_types}
        errors = []
        for record_type in self._record_types:
            outcome = self._query_record(
                resolver,
                ascii_domain,
                record_type,
                dns_exception,
                dns_name,
                dns_resolver,
            )
            if outcome["status"] == "name_not_found":
                return self._nxdomain_result(ascii_domain, records, statuses)
            records[record_type] = outcome["values"]
            statuses[record_type] = outcome["status"]
            ttl[record_type] = outcome["ttl"]
            if outcome["error"]:
                errors.append(outcome["error"])
        return self._aggregate_result(ascii_domain, records, statuses, ttl, errors)

    def _query_record(
        self,
        resolver,
        ascii_domain,
        record_type,
        dns_exception,
        dns_name,
        dns_resolver,
    ):
        try:
            answer = resolver.resolve(
                ascii_domain,
                record_type,
                lifetime=10.0,
                search=False,
            )
            values = list(
                dict.fromkeys(self._format_rdata(record_type, rdata) for rdata in answer)
            )
            status = self._answer_status(record_type, answer, dns_name)
            ttl = answer.rrset.ttl if answer.rrset is not None else None
            return {"values": values, "status": status, "ttl": ttl, "error": None}
        except dns_resolver.NoAnswer:
            return {"values": [], "status": "no_record", "ttl": None, "error": None}
        except dns_resolver.NXDOMAIN:
            return {"values": [], "status": "name_not_found", "ttl": None, "error": None}
        except (
            dns_resolver.LifetimeTimeout,
            dns_resolver.NoNameservers,
            dns_exception.DNSException,
        ) as exc:
            return {
                "values": [],
                "status": "query_failed",
                "ttl": None,
                "error": f"{record_type} query failed: {exc}",
            }

    @staticmethod
    def _answer_status(record_type, answer, dns_name):
        if record_type != "MX":
            return "resolved"
        has_null_mx = any(
            rdata.preference == 0 and rdata.exchange == dns_name.root for rdata in answer
        )
        return "null_mx" if has_null_mx else "resolved"

    def _aggregate_result(self, ascii_domain, records, statuses, ttl, errors):
        summary = {key: len(value) for key, value in records.items()}
        successful_queries = sum(
            status in {"resolved", "null_mx", "no_record"}
            for status in statuses.values()
        )
        result = {
            "success": successful_queries > 0,
            "domain": ascii_domain,
            "records": records,
            "summary": summary,
            "record_status": statuses,
            "ttl_seconds": ttl,
            "errors": errors,
            "message": self._message(ascii_domain, records, statuses, summary),
        }
        if successful_queries == 0:
            result.update(
                {
                    "error_code": "dns_queries_failed",
                    "error": "Every DNS record query failed before a definitive answer was received.",
                    "remediation": "Check network connectivity and configured DNS servers, then retry.",
                }
            )
        return result

    def _message(self, ascii_domain, records, statuses, summary):
        lines = [f"DNS records inspected for '{ascii_domain}':"]
        for record_type, count in summary.items():
            status = statuses[record_type]
            if status == "null_mx":
                detail = "Null MX (0 .); this domain explicitly does not accept email"
            elif count > 0:
                values = ", ".join(records[record_type][:3])
                suffix = f" (+{count - 3} more)" if count > 3 else ""
                detail = f"({count}): {values}{suffix}"
            elif status == "query_failed":
                detail = "Query failed"
            else:
                detail = "None found"
            lines.append(f"- {record_type}: {detail}")
        return "\n".join(lines) + "\n"

    def _nxdomain_result(self, ascii_domain, records, statuses):
        message = f"DNS name '{ascii_domain}' does not exist."
        return {
            "success": False,
            "error_code": "dns_name_not_found",
            "domain": ascii_domain,
            "records": records,
            "record_status": {key: "name_not_found" for key in statuses},
            "errors": [message],
            "error": message,
            "remediation": "Check the spelling and whether the domain is registered.",
            "message": message,
        }

    @staticmethod
    def _invalid_domain(error, *, message=None):
        return {
            "success": False,
            "error_code": "invalid_domain",
            "error": error,
            "message": message or error,
            "remediation": "Pass a valid DNS name such as example.com.",
        }

    @staticmethod
    def _format_rdata(record_type, rdata):
        """Return a stable, lossless string for a dnspython record."""
        if record_type == "MX":
            return f"{rdata.preference} {rdata.exchange.to_text()}"
        if record_type == "TXT":
            return "".join(
                part.decode("utf-8", errors="replace") for part in rdata.strings
            )
        return rdata.to_text()
