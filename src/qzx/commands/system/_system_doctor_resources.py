"""Internal mixin extracted from systemDoctor without behavior changes."""

import os
import platform
import socket
import subprocess

try:
    import psutil
except ImportError:
    psutil = None


def _cpu_base_info():
    logical = os.cpu_count() or 0
    return {
        "cores_logical": logical,
        "cores_physical": logical,
        "usage_percent": 0.0,
        "temperature_c": None,
    }


def _populate_cpu_from_psutil(info, quick):
    info["cores_logical"] = psutil.cpu_count(logical=True)
    info["cores_physical"] = psutil.cpu_count(logical=False) or info["cores_logical"]
    info["usage_percent"] = psutil.cpu_percent(interval=0.1)
    if quick or not hasattr(psutil, "sensors_temperatures"):
        return
    try:
        temperatures = psutil.sensors_temperatures()
        if temperatures:
            for entries in temperatures.values():
                if entries:
                    info["temperature_c"] = entries[0].current
                    break
    except Exception:
        pass


def _populate_cpu_fallback(info):
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "cpu", "get", "LoadPercentage"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            lines = [line.strip() for line in result.stdout.split("\n") if line.strip()]
            if len(lines) > 1:
                info["usage_percent"] = float(lines[1])
        else:
            with open("/proc/loadavg", "r", encoding="utf-8") as file_handle:
                load = float(file_handle.read().split()[0])
            info["usage_percent"] = min(
                100.0,
                (load / (info["cores_logical"] or 1)) * 100.0,
            )
    except Exception:
        pass


def _psutil_ram():
    virtual = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "virtual": {
            "total_bytes": virtual.total,
            "used_bytes": virtual.used,
            "free_bytes": virtual.free,
            "percent": virtual.percent,
        },
        "swap": {
            "total_bytes": swap.total,
            "used_bytes": swap.used,
            "free_bytes": swap.free,
            "percent": swap.percent,
        },
    }


def _windows_ram_fallback():
    try:
        result = subprocess.run(
            [
                "wmic",
                "OS",
                "get",
                "FreePhysicalMemory,TotalVisibleMemorySize",
                "/Value",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        data = {}
        for line in result.stdout.split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = int(value.strip())
        total = data.get("TotalVisibleMemorySize", 0) * 1024
        free = data.get("FreePhysicalMemory", 0) * 1024
        used = total - free
        percent = round((used / total) * 100, 1) if total else 0
        return {
            "virtual": {
                "total_bytes": total,
                "used_bytes": used,
                "free_bytes": free,
                "percent": percent,
            },
            "swap": "not_available",
        }
    except Exception:
        return None


def _psutil_partitions():
    partitions = []
    for partition in psutil.disk_partitions(all=False):
        if "cdrom" in partition.opts or not partition.mountpoint:
            continue
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            partitions.append(
                {
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total_bytes": usage.total,
                    "used_bytes": usage.used,
                    "free_bytes": usage.free,
                    "percent": usage.percent,
                }
            )
        except Exception:
            pass
    return partitions


def _append_windows_partition(partitions, current):
    if "DeviceID" not in current:
        return
    device = current["DeviceID"]
    free = int(current.get("FreeSpace", 0) or 0)
    size = int(current.get("Size", 0) or 0)
    used = size - free
    percent = round((used / size) * 100, 1) if size else 0
    partitions.append(
        {
            "device": device,
            "mountpoint": device + "\\",
            "fstype": "unknown",
            "total_bytes": size,
            "used_bytes": used,
            "free_bytes": free,
            "percent": percent,
        }
    )


def _windows_partitions():
    partitions = []
    try:
        result = subprocess.run(
            ["wmic", "logicaldisk", "get", "DeviceID,FreeSpace,Size", "/Value"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        current = {}
        for line in result.stdout.split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                current[key.strip()] = value.strip()
            elif not line.strip() and current:
                _append_windows_partition(partitions, current)
                current = {}
    except Exception:
        pass
    return partitions


class SystemDoctorResourcesMixin:
    def _check_cpu(self, quick):
        info = _cpu_base_info()
        if psutil:
            _populate_cpu_from_psutil(info, quick)
        else:
            _populate_cpu_fallback(info)
        return info

    def _check_ram(self):
        if psutil:
            return _psutil_ram()
        if platform.system() == "Windows":
            fallback = _windows_ram_fallback()
            if fallback is not None:
                return fallback
        return "not_available"

    def _check_disk(self, quick):
        if psutil:
            partitions = _psutil_partitions()
        elif platform.system() == "Windows":
            partitions = _windows_partitions()
        else:
            partitions = []
        return {"partitions": partitions}

    def _check_network(self, quick):
        net_info = {"interfaces": [], "dns_ok": False, "external_ip": None}
        if psutil:
            try:
                addrs = psutil.net_if_addrs()
                for name, info_list in addrs.items():
                    ips = []
                    for addr in info_list:
                        if addr.family == socket.AF_INET:
                            ips.append(addr.address)
                    if ips:
                        net_info["interfaces"].append({"name": name, "ips": ips})
            except Exception:
                pass
        else:
            try:
                hostname = socket.gethostname()
                ips = socket.gethostbyname_ex(hostname)[2]
                net_info["interfaces"].append(
                    {"name": "hostname_resolve", "ips": ips}
                )
            except Exception:
                pass

        try:
            socket.setdefaulttimeout(3.0)
            socket.gethostbyname("google.com")
            net_info["dns_ok"] = True
        except Exception:
            net_info["dns_ok"] = False
        return net_info
