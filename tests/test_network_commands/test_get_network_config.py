#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Real-network tests for getNetworkConfig."""

import ipaddress
import socket

from qzx.commands.network.get_network_config import GetNetworkConfigCommand


def test_local_network_config_comes_from_the_real_host():
    result = GetNetworkConfigCommand().execute(check_public=False)

    assert result["success"] is True
    assert result["hostname"] == socket.gethostname()
    assert isinstance(result["local_ips"], list)
    for address in result["local_ips"]:
        ipaddress.ip_address(address)
    assert isinstance(result["interfaces"], dict)
    assert isinstance(result["dns_servers"], list)
    assert isinstance(result["vpn"]["active"], bool)
    assert isinstance(result["vpn"]["detected_interfaces"], list)
    assert result["public"] is None


def test_public_network_lookup_returns_a_real_public_ip():
    result = GetNetworkConfigCommand().execute(check_public=True)

    assert result["success"] is True
    ipaddress.ip_address(result["public"]["ip"])
    assert result["public"]["country"] != "unknown"
