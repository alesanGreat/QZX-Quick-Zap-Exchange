"""Platform text parsers for getNetworkConfig."""

from __future__ import annotations

import os


VPN_NAMES = ("tap", "vpn", "tun", "wireguard", "forti", "cisco", "anyconnect")
UNIX_VPN_NAMES = ("tun", "tap", "vpn", "wg")


def _active_interfaces(interfaces):
    return {
        name: values
        for name, values in interfaces.items()
        if values["ipv4"] or values["ipv6"]
    }


def _vpn_has_address(interfaces, name):
    values = interfaces[name]
    return bool(values["ipv4"] or values["ipv6"])


def _append_vpn(vpn_interfaces, interfaces, name):
    if name not in vpn_interfaces and _vpn_has_address(interfaces, name):
        vpn_interfaces.append(name)


def _windows_adapter_name(line):
    if "adapter" not in line or not line.endswith(":"):
        return None
    return line.split("adapter", 1)[1].rstrip(":").strip()


def _windows_property(interfaces, adapter, key, value, dns_servers):
    vpn_hint = False
    if "Description" in key:
        interfaces[adapter]["description"] = value
        lower = value.lower()
        vpn_hint = any(name in lower for name in (*VPN_NAMES, "virtual adapter"))
    elif "Physical Address" in key:
        interfaces[adapter]["mac"] = value
    elif "IPv4 Address" in key or "IP Address" in key:
        interfaces[adapter]["ipv4"].append(value.split("(")[0].strip())
    elif "IPv6 Address" in key:
        interfaces[adapter]["ipv6"].append(value.split("(")[0].strip())
    elif "DNS Servers" in key and value:
        dns_servers.append(value)
    return vpn_hint


def parse_ipconfig_all(stdout):
    """Parse Windows ipconfig /all output."""
    interfaces, vpn_interfaces, dns_servers = {}, [], []
    adapter = None
    dns_section = False
    vpn_hint = False
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        new_adapter = _windows_adapter_name(raw_line)
        if new_adapter is not None:
            adapter = new_adapter
            interfaces[adapter] = {
                "ipv4": [], "ipv6": [], "description": "", "mac": ""
            }
            dns_section = False
            vpn_hint = any(name in adapter.lower() for name in VPN_NAMES)
            continue
        if not adapter:
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().replace(".", "")
            value = value.strip()
            property_vpn = _windows_property(
                interfaces, adapter, key, value, dns_servers
            )
            vpn_hint = vpn_hint or property_vpn
            dns_section = "DNS Servers" in key
        elif dns_section:
            dns_servers.append(line)
        if vpn_hint:
            _append_vpn(vpn_interfaces, interfaces, adapter)
    return _active_interfaces(interfaces), vpn_interfaces, dns_servers


def _unix_interface_start(line):
    if not line or not line[0].isdigit() or ":" not in line:
        return None
    parts = line.split(":", 2)
    return parts[1].strip() if len(parts) >= 2 else None


def _append_unix_address(interfaces, name, line):
    if line.startswith("inet "):
        parts = line.split()
        if len(parts) >= 2:
            interfaces[name]["ipv4"].append(parts[1].split("/")[0])
    elif line.startswith("inet6 "):
        parts = line.split()
        if len(parts) >= 2:
            interfaces[name]["ipv6"].append(parts[1].split("/")[0])


def _mark_unix_vpn(interfaces, vpn_interfaces, name):
    if any(value in name.lower() for value in UNIX_VPN_NAMES):
        _append_vpn(vpn_interfaces, interfaces, name)


def parse_ip_addr(stdout):
    """Parse Linux ip addr output."""
    interfaces, vpn_interfaces = {}, []
    current = None
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        started = _unix_interface_start(line)
        if started is not None:
            current = started
            interfaces[current] = {"ipv4": [], "ipv6": []}
            continue
        if not current:
            continue
        _append_unix_address(interfaces, current, line)
        _mark_unix_vpn(interfaces, vpn_interfaces, current)
    return _active_interfaces(interfaces), vpn_interfaces


def _ifconfig_start(raw_line):
    if not raw_line or raw_line.startswith((" ", "\t")) or ":" not in raw_line:
        return None
    return raw_line.split(":", 1)[0].strip()


def _append_ifconfig_address(interfaces, name, line):
    parts = line.split()
    if len(parts) < 2:
        return
    if line.startswith("inet "):
        interfaces[name]["ipv4"].append(parts[1])
    elif line.startswith("inet6 "):
        interfaces[name]["ipv6"].append(parts[1].split("%")[0])


def parse_ifconfig(stdout):
    """Parse Linux/macOS ifconfig output."""
    interfaces, vpn_interfaces = {}, []
    current = None
    for raw_line in stdout.splitlines():
        started = _ifconfig_start(raw_line)
        if started is not None:
            current = started
            interfaces[current] = {"ipv4": [], "ipv6": []}
            continue
        if not current:
            continue
        line = raw_line.strip()
        _append_ifconfig_address(interfaces, current, line)
        _mark_unix_vpn(interfaces, vpn_interfaces, current)
    return _active_interfaces(interfaces), vpn_interfaces


def parse_resolv_conf(path="/etc/resolv.conf"):
    """Read nameservers from resolv.conf."""
    servers = []
    if not os.path.exists(path):
        return servers
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0] == "nameserver":
                servers.append(parts[1])
    return servers
