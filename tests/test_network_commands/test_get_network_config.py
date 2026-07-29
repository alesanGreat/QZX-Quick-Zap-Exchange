#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Real-network tests for getNetworkConfig."""

import ipaddress
import socket
import sys

from qzx.commands.network.get_network_config import GetNetworkConfigCommand


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


def test_public_network_lookup_returns_a_real_public_ip():
    result = GetNetworkConfigCommand().execute(check_public=True)

    assert result["success"] is True
    ipaddress.ip_address(result["public"]["ip"])
    assert result["public"]["country"] != "unknown"


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
