#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetNetworkConfig Command - Retrieves local network interfaces, DNS settings, public IP, and VPN detection.
"""

import os
import sys
import socket
import platform
import subprocess
import urllib.request
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

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
            'default': 'true'
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
    
    def execute(self, check_public='true'):
        """
        Gathers network configuration info
        
        Args:
            check_public (str/bool): Query public IP APIs
            
        Returns:
            Dictionary with network configuration details
        """
        is_windows = platform.system().lower() == "windows"
        
        if isinstance(check_public, str):
            resolve_pub = check_public.lower() in ('true', 'yes', 'y', '1', 't')
        else:
            resolve_pub = bool(check_public)
            
        local_hostname = socket.gethostname()
        local_ips = []
        
        try:
            # Basic hostname resolution
            _, _, ips = socket.gethostbyname_ex(local_hostname)
            local_ips = [ip for ip in ips if not ip.startswith("127.")]
        except Exception:
            pass
            
        # Parse interfaces and gateways via ipconfig / ifconfig
        interfaces = {}
        vpn_active = False
        vpn_interfaces = []
        dns_servers = []
        
        try:
            if is_windows:
                # Run ipconfig /all
                res = subprocess.run(
                    ["ipconfig", "/all"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5,
                    check=False
                )
                if res.returncode == 0:
                    interfaces, vpn_interfaces, dns_servers = self._parse_ipconfig_all(res.stdout)
            else:
                # Linux/macOS
                res = subprocess.run(
                    ["ip", "addr"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5,
                    check=False
                )
                if res.returncode == 0:
                    interfaces, vpn_interfaces = self._parse_ip_addr(res.stdout)
                else:
                    # Fallback to ifconfig
                    res = subprocess.run(
                        ["ifconfig"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=5,
                        check=False
                    )
                    if res.returncode == 0:
                        interfaces, vpn_interfaces = self._parse_ifconfig(res.stdout)
                        
                # Read DNS from resolv.conf
                dns_servers = self._parse_resolv_conf()
        except Exception:
            pass
            
        vpn_active = len(vpn_interfaces) > 0
        
        # Get public IP & Location Info
        public_info = {
            "ip": "unknown",
            "country": "unknown",
            "region": "unknown",
            "city": "unknown",
            "isp": "unknown"
        }
        
        if resolve_pub:
            try:
                # Query ipinfo.io (reliable and returns location)
                req = urllib.request.Request(
                    "https://ipinfo.io/json",
                    headers={"User-Agent": "QZX Network Client"}
                )
                with urllib.request.urlopen(req, timeout=4) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    public_info["ip"] = data.get("ip", "unknown")
                    public_info["country"] = data.get("country", "unknown")
                    public_info["region"] = data.get("region", "unknown")
                    public_info["city"] = data.get("city", "unknown")
                    public_info["isp"] = data.get("org", "unknown")
            except Exception:
                # Fallback to simple ipify
                try:
                    req = urllib.request.Request(
                        "https://api.ipify.org?format=json",
                        headers={"User-Agent": "QZX Network Client"}
                    )
                    with urllib.request.urlopen(req, timeout=3) as response:
                        data = json.loads(response.read().decode("utf-8"))
                        public_info["ip"] = data.get("ip", "unknown")
                except Exception:
                    pass
                    
        # Formulate output message
        msg = f"Network Diagnostics for host '{local_hostname}':\n"
        if local_ips:
            msg += f"- Local IPs: {', '.join(local_ips)}\n"
        msg += f"- Active Interfaces: {len(interfaces)}\n"
        if dns_servers:
            msg += f"- DNS Servers: {', '.join(dns_servers)}\n"
        if resolve_pub:
            msg += f"- Public IP: {public_info['ip']} ({public_info['city']}, {public_info['country']})\n"
            if public_info['isp'] != "unknown":
                msg += f"  - ISP: {public_info['isp']}\n"
        msg += f"- VPN Detected: {'YES' if vpn_active else 'NO'}"
        if vpn_active:
            msg += f" (via: {', '.join(vpn_interfaces)})"
            
        return {
            "success": True,
            "hostname": local_hostname,
            "local_ips": local_ips,
            "dns_servers": dns_servers,
            "vpn": {
                "active": vpn_active,
                "detected_interfaces": vpn_interfaces
            },
            "interfaces": interfaces,
            "public": public_info if resolve_pub else None,
            "message": msg
        }
        
    def _parse_ipconfig_all(self, stdout):
        """Parses Windows ipconfig /all output"""
        interfaces = {}
        vpn_interfaces = []
        dns_servers = []
        
        current_adapter = None
        dns_section = False
        
        for line in stdout.splitlines():
            line_strip = line.strip()
            if not line_strip:
                continue
                
            # Adapter start line, e.g. "Ethernet adapter Ethernet:" or "Wireless LAN adapter Wi-Fi:"
            if "adapter" in line and line.endswith(":"):
                current_adapter = line.split("adapter", 1)[1].rstrip(":").strip()
                interfaces[current_adapter] = {
                    "ipv4": [],
                    "ipv6": [],
                    "description": "",
                    "mac": ""
                }
                dns_section = False
                continue
                
            # Check if this adapter is a VPN
            if current_adapter:
                lower_adapter = current_adapter.lower()
                is_vpn = any(keyword in lower_adapter for keyword in ["tap", "vpn", "tun", "wireguard", "forti", "cisco", "anyconnect"])
                
                # Check line properties
                if ":" in line_strip:
                    parts = line_strip.split(":", 1)
                    key = parts[0].strip().replace(".", "")
                    value = parts[1].strip()
                    
                    if "Description" in key:
                        interfaces[current_adapter]["description"] = value
                        # Double check description for VPN indicators
                        lower_desc = value.lower()
                        if any(k in lower_desc for k in ["tap", "vpn", "tun", "wireguard", "forti", "cisco", "anyconnect", "virtual adapter"]):
                            is_vpn = True
                    elif "Physical Address" in key:
                        interfaces[current_adapter]["mac"] = value
                    elif "IPv4 Address" in key or "IP Address" in key:
                        # Strip (Preferred) if present
                        ip = value.split("(")[0].strip()
                        interfaces[current_adapter]["ipv4"].append(ip)
                    elif "IPv6 Address" in key:
                        ip = value.split("(")[0].strip()
                        interfaces[current_adapter]["ipv6"].append(ip)
                    elif "DNS Servers" in key:
                        dns_section = True
                        if value:
                            dns_servers.append(value)
                elif dns_section:
                    # Continued DNS servers list (no colon on the line)
                    if line_strip:
                        dns_servers.append(line_strip)
                            
                # If marked as VPN and not in list
                if is_vpn and current_adapter not in vpn_interfaces:
                    # Only add if it actually has an IP configured (meaning active tunnel)
                    if interfaces[current_adapter]["ipv4"] or interfaces[current_adapter]["ipv6"]:
                        vpn_interfaces.append(current_adapter)
                        
        # Remove empty interfaces
        active_interfaces = {
            k: v for k, v in interfaces.items()
            if v["ipv4"] or v["ipv6"]
        }
        
        return active_interfaces, vpn_interfaces, dns_servers
        
    def _parse_ip_addr(self, stdout):
        """Parses Linux ip addr output"""
        interfaces = {}
        vpn_interfaces = []
        current_iface = None
        
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
                
            # Interface start, e.g. "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>..."
            if line[0].isdigit() and ":" in line:
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    current_iface = parts[1].strip()
                    interfaces[current_iface] = {
                        "ipv4": [],
                        "ipv6": []
                    }
                continue
                
            if current_iface:
                # IPv4 line, e.g. "inet 192.168.1.10/24 ..."
                if line.startswith("inet "):
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[1].split("/")[0]
                        interfaces[current_iface]["ipv4"].append(ip)
                # IPv6 line, e.g. "inet6 fe80::.../64 ..."
                elif line.startswith("inet6 "):
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[1].split("/")[0]
                        interfaces[current_iface]["ipv6"].append(ip)
                        
                # Detect VPN
                lower_iface = current_iface.lower()
                if any(k in lower_iface for k in ["tun", "tap", "vpn", "wg"]):
                    if current_iface not in vpn_interfaces:
                        if interfaces[current_iface]["ipv4"] or interfaces[current_iface]["ipv6"]:
                            vpn_interfaces.append(current_iface)
                            
        # Filter active
        active = {k: v for k, v in interfaces.items() if v["ipv4"] or v["ipv6"]}
        return active, vpn_interfaces
        
    def _parse_ifconfig(self, stdout):
        """Parses Linux/macOS ifconfig output"""
        interfaces = {}
        vpn_interfaces = []
        current_iface = None
        
        for line in stdout.splitlines():
            # Interface start line: e.g. "en0: flags=8863<UP,BROADCAST,SMART,RUNNING...>"
            if line and not line.startswith(" ") and not line.startswith("\t") and ":" in line:
                current_iface = line.split(":", 1)[0].strip()
                interfaces[current_iface] = {
                    "ipv4": [],
                    "ipv6": []
                }
                continue
                
            if current_iface:
                line_strip = line.strip()
                # e.g. "inet 192.168.1.5 netmask 0xffffff00 broadcast 192.168.1.255"
                if line_strip.startswith("inet "):
                    parts = line_strip.split()
                    if len(parts) >= 2:
                        interfaces[current_iface]["ipv4"].append(parts[1])
                elif line_strip.startswith("inet6 "):
                    parts = line_strip.split()
                    if len(parts) >= 2:
                        # strip interface index (e.g. fe80::1%lo0 -> fe80::1)
                        ip = parts[1].split("%")[0]
                        interfaces[current_iface]["ipv6"].append(ip)
                        
                # Detect VPN
                lower_iface = current_iface.lower()
                if any(k in lower_iface for k in ["tun", "tap", "vpn", "wg"]):
                    if current_iface not in vpn_interfaces:
                        if interfaces[current_iface]["ipv4"] or interfaces[current_iface]["ipv6"]:
                            vpn_interfaces.append(current_iface)
                            
        # Filter active
        active = {k: v for k, v in interfaces.items() if v["ipv4"] or v["ipv6"]}
        return active, vpn_interfaces
        
    def _parse_resolv_conf(self):
        """Parses DNS servers from resolv.conf on Unix systems"""
        servers = []
        conf_path = "/etc/resolv.conf"
        if os.path.exists(conf_path):
            try:
                with open(conf_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("nameserver "):
                            parts = line.split()
                            if len(parts) >= 2:
                                servers.append(parts[1])
            except Exception:
                pass
        return servers
