"""Tests for checkDns against the real configured resolver."""

import ipaddress

import dns.exception

from qzx.commands.network.check_dns import CheckDnsCommand


class TestCheckDnsCommand:
    def setup_method(self):
        self.command = CheckDnsCommand()

    def test_empty_domain(self):
        result = self.command.execute("")

        assert result["success"] is False
        assert "must not be empty" in result["error"]

    def test_example_dns_records_are_really_resolved(self):
        result = self.command.execute("example.com")

        assert result["success"] is True
        assert result["domain"] == "example.com"
        assert result["errors"] == []

        records = result["records"]
        assert records["A"]
        assert records["MX"] == ["0 ."]
        assert records["NS"]
        assert all(
            ipaddress.ip_address(address).version == 4
            for address in records["A"]
        )
        assert all(
            ipaddress.ip_address(address).version == 6
            for address in records["AAAA"]
        )
        assert result["summary"]["A"] == len(records["A"])
        assert result["summary"]["MX"] == len(records["MX"])
        assert result["record_status"]["A"] == "resolved"
        assert result["record_status"]["MX"] == "null_mx"
        assert result["record_status"]["CNAME"] == "no_record"
        assert result["ttl_seconds"]["MX"] > 0
        assert "explicitly does not accept email" in result["message"]

    def test_reserved_invalid_name_returns_structured_nxdomain(self):
        result = self.command.execute("qzx-no-such-name.invalid")

        assert result["success"] is False
        assert result["error_code"] == "dns_name_not_found"
        assert result["domain"] == "qzx-no-such-name.invalid"
        assert set(result["record_status"].values()) == {"name_not_found"}
        assert result["records"]["A"] == []
        assert result["error"] == result["message"]
        assert result["remediation"]

    def test_total_resolver_failure_has_cause_and_remediation(self):
        class UnavailableResolver:
            def resolve(self, *_args, **_kwargs):
                raise dns.exception.DNSException("resolver unavailable")

        result = CheckDnsCommand(
            resolver_factory=UnavailableResolver,
        ).execute("example.com")

        assert result["success"] is False
        assert result["error_code"] == "dns_queries_failed"
        assert len(result["errors"]) == 6
        assert result["error"]
        assert result["remediation"]
        assert set(result["record_status"].values()) == {"query_failed"}

    def test_resolver_initialization_failure_is_structured(self):
        def unavailable_resolver():
            raise dns.exception.DNSException("no resolver configuration")

        result = CheckDnsCommand(
            resolver_factory=unavailable_resolver,
        ).execute("example.com")

        assert result["success"] is False
        assert result["error_code"] == "dns_resolver_unavailable"
        assert "no resolver configuration" in result["error"]
        assert result["remediation"]
