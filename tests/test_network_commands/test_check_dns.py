"""Tests for checkDns against the real configured resolver."""

import ipaddress

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
        assert records["MX"]
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
        assert "MX" in result["message"]
