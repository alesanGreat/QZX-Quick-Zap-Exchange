"""Internal mixin extracted from systemDoctor without behavior changes."""

import os
import platform
import subprocess

try:
    import psutil
except ImportError:
    psutil = None


def _windows_services():
    services = []
    for name in ("Winmgmt", "LanmanServer", "wuauserv", "Dhcp", "EventLog"):
        try:
            result = subprocess.run(
                ["sc", "query", name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            status = "unknown"
            for line in result.stdout.split("\n"):
                if "STATE" in line:
                    status = line.split(":", 1)[1].strip()
                    break
            services.append({"name": name, "status": status})
        except Exception:
            pass
    return services


def _linux_services():
    services = []
    try:
        result = subprocess.run(
            [
                "systemctl",
                "list-units",
                "--type=service",
                "--state=running",
                "--no-legend",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        for line in result.stdout.split("\n"):
            parts = line.split()
            if line.strip() and len(parts) >= 3:
                services.append({"name": parts[0], "status": "running"})
    except Exception:
        pass
    return services


def _psutil_ports():
    ports = []
    try:
        for connection in psutil.net_connections(kind="inet"):
            if connection.status != "LISTEN":
                continue
            ports.append(
                {
                    "port": connection.laddr.port,
                    "ip": connection.laddr.ip,
                    "pid": connection.pid,
                    "name": (
                        psutil.Process(connection.pid).name()
                        if connection.pid
                        else "unknown"
                    ),
                }
            )
    except Exception:
        pass
    return ports


def _windows_netstat_ports():
    ports = []
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        for line in result.stdout.split("\n"):
            if "LISTENING" not in line:
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            address = parts[1]
            pid = parts[4]
            ports.append(
                {
                    "port": int(address.split(":")[-1]),
                    "ip": address,
                    "pid": int(pid) if pid.isdigit() else None,
                    "name": "unknown",
                }
            )
    except Exception:
        pass
    return ports


def _unique_ports(ports):
    unique_ports = []
    seen = set()
    for port in ports:
        key = (port["port"], port["ip"])
        if key not in seen:
            seen.add(key)
            unique_ports.append(port)
    return sorted(unique_ports, key=lambda item: item["port"])[:50]


class SystemDoctorEnvironmentMixin:
    def _check_path(self):
        path_env = os.environ.get("PATH", "")
        entries = [entry.strip() for entry in path_env.split(os.pathsep) if entry.strip()]
        valid = []
        broken = []
        for entry in entries:
            if os.path.exists(entry) and os.path.isdir(entry):
                valid.append(entry)
            else:
                broken.append(entry)
        return {
            "total_entries": len(entries),
            "valid_count": len(valid),
            "broken_count": len(broken),
            "broken": broken,
        }

    def _check_services(self):
        if platform.system().lower() == "windows":
            critical_services = _windows_services()
        else:
            critical_services = _linux_services()
        return {"critical_services": critical_services}

    def _check_ports(self):
        system_name = platform.system().lower()
        if psutil and system_name != "sunos":
            ports = _psutil_ports()
        elif system_name == "sunos":
            return {
                "status": "not_available",
                "listening": [],
                "reason": (
                    "System-wide listening-port enumeration is unavailable "
                    "through psutil on SunOS."
                ),
            }
        elif system_name == "windows":
            ports = _windows_netstat_ports()
        else:
            ports = []
        return {"listening": _unique_ports(ports)}
