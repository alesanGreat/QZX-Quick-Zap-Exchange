#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Real-network tests for getNetworkConfig."""

import ipaddress
import json
import socket
import sys
from types import SimpleNamespace

from qzx.commands.network.get_network_config import GetNetworkConfigCommand


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(
            {
                "ip": "203.0.113.10",
                "country": "CO",
                "region": "Bogota",
                "city": "Bogota",
                "org": "QZX Test Network",
            }
        ).encode("utf-8")


class ProviderBackedNetworkConfigCommand(GetNetworkConfigCommand):
    """Use a deterministic public-network provider response."""

    @staticmethod
    def _open_url(_request, timeout):
        assert timeout == 4
        return FakeResponse()


class ResolverFallbackNetworkConfigCommand(GetNetworkConfigCommand):
    """Exercise the Unix resolver fallback through explicit fake boundaries."""

    @staticmethod
    def _system_name():
        return "Linux"

    @staticmethod
    def _collect_interfaces():
        return (
            {
                "eth0": {
                    "ipv4": ["192.0.2.10"],
                    "ipv6": [],
                    "description": "eth0",
                    "mac": "",
                    "is_up": True,
                    "speed_mbps": 1000,
                    "mtu": 1500,
                }
            },
            [],
        )

    @staticmethod
    def _configured_dns_servers():
        raise ImportError("resolver unavailable")

    @staticmethod
    def _run_system_command(_command):
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    @staticmethod
    def _parse_resolv_conf():
        return ["192.0.2.53"]


def test_local_network_config_comes_from_the_real_host():
    result = GetNetworkConfigCommand().execute(check_public=False)

    assert result["success"] is True
    assert result["hostname"] == socket.gethostname()
    assert isinstance(result["local_ips"], list)
    for address in result["local_ips"]:
        ipaddress.ip_address(address)
    assert isinstance(result["interfaces"], dict)
    assert result["interfaces"]
    for interface in result["interfaces"].values():
        assert interface["ipv4"] or interface["ipv6"]
        assert interface["is_up"] is True
        for address in interface["ipv4"] + interface["ipv6"]:
            ipaddress.ip_address(address)
    assert isinstance(result["dns_servers"], list)
    assert result["dns_servers"]
    for address in result["dns_servers"]:
        ipaddress.ip_address(address)
    assert isinstance(result["vpn"]["active"], bool)
    assert isinstance(result["vpn"]["detected_interfaces"], list)
    assert result["public"] is None


def test_public_network_lookup_returns_structured_provider_data():
    result = ProviderBackedNetworkConfigCommand().execute(check_public=True)

    assert result["success"] is True
    assert result["public"] == {
        "ip": "203.0.113.10",
        "country": "CO",
        "region": "Bogota",
        "city": "Bogota",
        "isp": "QZX Test Network",
    }


def test_resolver_backend_failure_degrades_to_resolv_conf():
    result = ResolverFallbackNetworkConfigCommand().execute(check_public=False)

    assert result["success"] is True
    assert result["interfaces"]["eth0"]["ipv4"] == ["192.0.2.10"]
    assert result["dns_servers"] == ["192.0.2.53"]


def test_native_network_output_decodes_problematic_bytes_without_crashing():
    result = GetNetworkConfigCommand._run_system_command(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(bytes([0x81]))",
        ]
    )

    assert result.returncode == 0
    assert isinstance(result.stdout, str)
    assert len(result.stdout) == 1


def test_invalid_public_lookup_choice_is_not_silently_treated_as_false():
    result = GetNetworkConfigCommand().execute(check_public="sometimes")

    assert result["success"] is False
    assert result["error_code"] == "invalid_check_public"
    assert result["error"]
    assert result["remediation"]
    assert "true or false" in result["message"]
