"""Workflow orchestration for getNetworkConfig."""

from __future__ import annotations

import json
import urllib.request


def invalid_public_choice(value):
    return {
        "success": False,
        "error_code": "invalid_check_public",
        "error": f"check_public must be a boolean value, got '{value}'.",
        "remediation": "Pass true to query public services or false to skip them.",
        "message": (
            "Network inspection did not start because check_public "
            "must be true or false."
        ),
    }


def _collection_issue(stage, error):
    return {
        "stage": stage,
        "error": f"{type(error).__name__}: {error}",
    }


def _safe_interfaces(command, collection_issues):
    try:
        return command._collect_interfaces()
    except Exception as exc:
        collection_issues.append(_collection_issue("interfaces", exc))
        return {}, []


def _safe_dns(command, collection_issues):
    try:
        return command._configured_dns_servers()
    except Exception as exc:
        collection_issues.append(_collection_issue("dns", exc))
        return []


def _unix_fallback(command):
    result = command._run_system_command(["ip", "addr"])
    if result.returncode == 0:
        return command._parse_ip_addr(result.stdout)
    result = command._run_system_command(["ifconfig"])
    if result.returncode == 0:
        return command._parse_ifconfig(result.stdout)
    return {}, []


def _native_fallback(
    command,
    is_windows,
    interfaces,
    vpns,
    dns_servers,
    collection_issues,
):
    try:
        if is_windows:
            result = command._run_system_command(["ipconfig", "/all"])
            if result.returncode != 0:
                return interfaces, vpns, dns_servers
            fallback, fallback_vpns, fallback_dns = command._parse_ipconfig_all(
                result.stdout
            )
            return (
                interfaces or fallback,
                vpns if interfaces else fallback_vpns,
                dns_servers or fallback_dns,
            )
        fallback, fallback_vpns = _unix_fallback(command)
        return (
            interfaces or fallback,
            vpns if interfaces else fallback_vpns,
            dns_servers or command._parse_resolv_conf(),
        )
    except Exception as exc:
        collection_issues.append(_collection_issue("native_fallback", exc))
        return interfaces, vpns, dns_servers


def _unknown_public_info():
    return {
        "ip": "unknown",
        "country": "unknown",
        "region": "unknown",
        "city": "unknown",
        "isp": "unknown",
    }


def _read_json(command, url, timeout):
    request = urllib.request.Request(
        url, headers={"User-Agent": "QZX Network Client"}
    )
    with command._open_url(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _public_info(command, collection_issues):
    info = _unknown_public_info()
    try:
        data = _read_json(command, "https://ipinfo.io/json", 4)
        info.update(
            {
                "ip": data.get("ip", "unknown"),
                "country": data.get("country", "unknown"),
                "region": data.get("region", "unknown"),
                "city": data.get("city", "unknown"),
                "isp": data.get("org", "unknown"),
            }
        )
        return info
    except Exception as exc:
        collection_issues.append(_collection_issue("public_ipinfo", exc))
    try:
        data = _read_json(command, "https://api.ipify.org?format=json", 3)
        info["ip"] = data.get("ip", "unknown")
    except Exception as exc:
        collection_issues.append(_collection_issue("public_ipify", exc))
    return info


def _message(
    hostname,
    local_ips,
    interfaces,
    dns_servers,
    public,
    vpns,
    collection_issues,
):
    message = f"Network Diagnostics for host '{hostname}':\n"
    if local_ips:
        message += f"- Local IPs: {', '.join(local_ips)}\n"
    message += f"- Active Interfaces: {len(interfaces)}\n"
    if dns_servers:
        message += f"- DNS Servers: {', '.join(dns_servers)}\n"
    if public is not None:
        message += (
            f"- Public IP: {public['ip']} "
            f"({public['city']}, {public['country']})\n"
        )
        if public["isp"] != "unknown":
            message += f"  - ISP: {public['isp']}\n"
    active = bool(vpns)
    message += f"- VPN Detected: {'YES' if active else 'NO'}"
    if active:
        message += f" (via: {', '.join(vpns)})"
    if collection_issues:
        message += (
            f"\n- Diagnostics degraded: {len(collection_issues)} "
            "collection issue(s); see collection_issues."
        )
    return message


def execute_network_config(command, check_public=True):
    """Run the public getNetworkConfig workflow."""
    resolve_public = command._parse_bool(check_public)
    if resolve_public is None:
        return invalid_public_choice(check_public)
    collection_issues = []
    is_windows = command._system_name().lower() == "windows"
    hostname, local_ips = command._local_hostname_and_ips()
    interfaces, vpns = _safe_interfaces(command, collection_issues)
    dns_servers = _safe_dns(command, collection_issues)
    interfaces, vpns, dns_servers = _native_fallback(
        command,
        is_windows,
        interfaces,
        vpns,
        dns_servers,
        collection_issues,
    )
    public = (
        _public_info(command, collection_issues)
        if resolve_public
        else None
    )
    return {
        "success": True,
        "diagnostics_degraded": bool(collection_issues),
        "collection_issues": collection_issues,
        "hostname": hostname,
        "local_ips": local_ips,
        "dns_servers": dns_servers,
        "vpn": {"active": bool(vpns), "detected_interfaces": vpns},
        "interfaces": interfaces,
        "public": public,
        "message": _message(
            hostname,
            local_ips,
            interfaces,
            dns_servers,
            public,
            vpns,
            collection_issues,
        ),
    }
