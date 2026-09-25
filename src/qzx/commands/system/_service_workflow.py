"""Service list filtering and presentation for listSystemServices."""

from __future__ import annotations

import platform


def _unsupported(operating_system):
    return {
        "success": False,
        "error_code": "unsupported_operating_system",
        "error": f"Unsupported operating system: {operating_system}",
        "message": (
            "No native service collector is available for this operating system."
        ),
        "details": {"operating_system": operating_system},
    }


def _message(status_filter, manager, services):
    lines = [
        f"System Services Diagnostics (Filter: '{status_filter}'):",
        f"- Service manager: {manager}",
        f"- Services found: {len(services)}",
    ]
    if not services:
        lines.append("- No matching services found.")
        return "\n".join(lines)
    lines.extend(["", "Top Services:"])
    for service in services[:10]:
        lines.append(
            "  - [{}] {} ({})".format(
                service["status"].upper(),
                service["name"],
                service["display_name"][:60],
            )
        )
    if len(services) > 10:
        lines.append(f"  ... and {len(services) - 10} more.")
    return "\n".join(lines)


def execute_system_services(command, status="all"):
    """Run the public listSystemServices workflow."""
    status_filter = str(status).strip().lower()
    if status_filter not in {"all", "running", "stopped"}:
        status_filter = "all"
    operating_system = platform.system().lower()
    collectors = {
        "windows": command._collect_windows_services,
        "linux": command._collect_linux_services,
        "darwin": command._collect_launchd_services,
        "freebsd": command._collect_freebsd_services,
        "openbsd": command._collect_openbsd_services,
        "sunos": command._collect_smf_services,
    }
    collector = collectors.get(operating_system)
    if collector is None:
        return _unsupported(operating_system)
    try:
        services, manager, errors = collector()
    except Exception as exc:
        return {
            "success": False,
            "error_code": "service_discovery_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "message": (
                "Failed to list services through the native manager "
                f"on {operating_system}."
            ),
            "details": {"operating_system": operating_system},
        }
    if status_filter != "all":
        services = [
            service for service in services
            if service["status"] == status_filter
        ]
    services.sort(key=lambda item: item["name"].lower())
    return {
        "success": True,
        "operating_system": operating_system,
        "service_manager": manager,
        "status_filter": status_filter,
        "total_services": len(services),
        "services": services,
        "errors": errors,
        "message": _message(status_filter, manager, services),
    }
