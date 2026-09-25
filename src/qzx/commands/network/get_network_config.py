#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetNetworkConfig Command - Retrieves local network interfaces, DNS settings, public IP, and VPN detection.
"""

import locale
import os
import platform
import subprocess
import urllib.request

from qzx.commands.network._network_config_local import (
    collect_interfaces,
    configured_dns_servers,
    local_hostname_and_ips,
)
from qzx.commands.network._network_config_parsers import (
    parse_ifconfig,
    parse_ip_addr,
    parse_ipconfig_all,
    parse_resolv_conf,
)
from qzx.commands.network._network_config_workflow import execute_network_config
from qzx.core.command_base import CommandBase

class GetNetworkConfigCommand(CommandBase):
    """
    Command to retrieve detailed network status including active interfaces, gateways, public IP, and VPN status.
    """
    
    name = "getNetworkConfig"
    description = "Displays comprehensive network status (interfaces, local IPs, DNS, public IP, VPN detection)"
    category = "network"
    
    parameters = [
        {
            'name': 'check_public',
            'description': 'Whether to fetch public IP and location info (true/false)',
            'required': False,
            'default': True,
            'type': 'bool'
        }
    ]
    
    examples = [
        {
            'command': 'qzx getNetworkConfig',
            'description': 'Get full network diagnostics including public IP and VPN status'
        },
        {
            'command': 'qzx getNetworkConfig false',
            'description': 'Get local network info only, skipping public IP resolution'
        }
    ]

    @staticmethod
    def _run_system_command(command):
        """Run a native network command without assuming UTF-8 output."""
        encoding = "oem" if os.name == "nt" else locale.getpreferredencoding(False)
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding=encoding,
            errors="replace",
            timeout=5,
            check=False,
        )

    @staticmethod
    def _system_name():
        """Return the host operating-system family."""
        return platform.system()

    @staticmethod
    def _open_url(request, timeout):
        """Open a public network-information endpoint."""
        return urllib.request.urlopen(request, timeout=timeout)

    @staticmethod
    def _collect_interfaces():
        """Collect locale-independent interface data from host APIs."""
        return collect_interfaces()

    @staticmethod
    def _configured_dns_servers():
        """Read configured resolvers without making discovery depend on DNS."""
        return configured_dns_servers()

    @staticmethod
    def _local_hostname_and_ips():
        """Return hostname plus non-loopback addresses."""
        return local_hostname_and_ips()

    def execute(self, check_public=True):
        """Gather local network diagnostics and optional public network data."""
        return execute_network_config(self, check_public)

    def _parse_ipconfig_all(self, stdout):
        """Parse Windows ipconfig /all output."""
        return parse_ipconfig_all(stdout)

    def _parse_ip_addr(self, stdout):
        """Parse Linux ip addr output."""
        return parse_ip_addr(stdout)

    def _parse_ifconfig(self, stdout):
        """Parse Linux/macOS ifconfig output."""
        return parse_ifconfig(stdout)

    def _parse_resolv_conf(self):
        """Parse DNS servers from resolv.conf on Unix systems."""
        return parse_resolv_conf()
