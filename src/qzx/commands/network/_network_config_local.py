"""Host API collection for getNetworkConfig."""

from __future__ import annotations

import socket

import psutil


VPN_KEYWORDS = (
    "tap", "vpn", "tun", "wireguard", "forti", "cisco",
    "anyconnect", "tailscale", "zerotier",
)


def _interface_row(name, stats):
    interface_stats = stats.get(name)
    return {
        "ipv4": [],
        "ipv6": [],
        "description": name,
        "mac": "",
        "is_up": interface_stats.isup if interface_stats is not None else True,
        "speed_mbps": interface_stats.speed if interface_stats is not None else 0,
        "mtu": interface_stats.mtu if interface_stats is not None else None,
    }


def _fill_addresses(row, addresses):
    for address in addresses:
        if address.family == socket.AF_INET:
            row["ipv4"].append(address.address)
        elif address.family == socket.AF_INET6:
            row["ipv6"].append(address.address.split("%", 1)[0])
        elif address.family == psutil.AF_LINK:
            row["mac"] = address.address


def _is_vpn_interface(name):
    lowered = name.lower()
    return lowered.startswith("wg") or any(
        keyword in lowered for keyword in VPN_KEYWORDS
    )


def collect_interfaces():
    """Collect locale-independent interface data from host APIs."""
    interfaces, vpn_interfaces = {}, []
    stats = psutil.net_if_stats()
    for name, addresses in psutil.net_if_addrs().items():
        row = _interface_row(name, stats)
        _fill_addresses(row, addresses)
        if not row["is_up"] or not (row["ipv4"] or row["ipv6"]):
            continue
        interfaces[name] = row
        if _is_vpn_interface(name):
            vpn_interfaces.append(name)
    return interfaces, vpn_interfaces


def configured_dns_servers():
    """Read configured resolvers through dnspython."""
    import dns.resolver

    resolver = dns.resolver.Resolver(configure=True)
    return list(dict.fromkeys(str(server) for server in resolver.nameservers))


def local_hostname_and_ips():
    """Return hostname plus non-loopback addresses from basic resolution."""
    hostname = socket.gethostname()
    try:
        _name, _aliases, addresses = socket.gethostbyname_ex(hostname)
        return hostname, [ip for ip in addresses if not ip.startswith("127.")]
    except Exception:
        return hostname, []
