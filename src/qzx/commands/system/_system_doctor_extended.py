"""Internal mixin extracted from systemDoctor without behavior changes."""

import json
import os
import platform
import shutil
import subprocess


def _windows_recent_errors():
    errors = []
    try:
        command = [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-EventLog -LogName System -EntryType Error -Newest 5 | "
                "Select-Object EventID, Source, Message, TimeGenerated | "
                "ConvertTo-Json -Compress"
            ),
        ]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            raw_data = json.loads(result.stdout.strip())
            data_list = raw_data if isinstance(raw_data, list) else [raw_data]
            for entry in data_list:
                errors.append(
                    {
                        "event_id": entry.get("EventID"),
                        "source": entry.get("Source"),
                        "message": entry.get("Message", "").strip(),
                        "time": entry.get("TimeGenerated"),
                    }
                )
    except Exception:
        pass
    return errors


def _linux_recent_errors():
    errors = []
    try:
        if not os.path.exists("/var/log/syslog"):
            return errors
        result = subprocess.run(
            ["tail", "-n", "50", "/var/log/syslog"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        for line in result.stdout.split("\n"):
            if "error" in line.lower() or "fail" in line.lower():
                errors.append({"message": line.strip()})
    except Exception:
        pass
    return errors


def _scan_smartctl_drives(smartctl_bin):
    drives = []
    try:
        result = subprocess.run(
            [smartctl_bin, "--scan"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if parts:
                    device_path = parts[0]
                    drives.append((device_path, device_path))
    except Exception:
        pass
    return drives


def _windows_fallback_drives():
    drives = []
    try:
        result = subprocess.run(
            ["wmic", "diskdrive", "get", "DeviceID"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and "DeviceID" not in line:
                    drive_name = line.split("\\")[-1]
                    if drive_name:
                        drives.append((drive_name, f"\\\\.\\{drive_name}"))
    except Exception:
        pass
    if not drives:
        drives.append(("PhysicalDrive0", "\\\\.\\PhysicalDrive0"))
    return drives


def _linux_fallback_drives():
    drives = []
    try:
        result = subprocess.run(
            ["lsblk", "-d", "-n", "-o", "NAME"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                name = line.strip()
                if name:
                    drives.append((name, f"/dev/{name}"))
    except Exception:
        pass
    if not drives:
        drives.append(("sda", "/dev/sda"))
    return drives


def _smart_health(stdout):
    normalized = stdout.upper()
    if "PASSED" in normalized:
        return "PASSED"
    if "FAILED" in normalized or "FAILING" in normalized:
        return "FAILED"
    if "WARNING" in normalized:
        return "WARNING"
    return "UNKNOWN"


def _smart_report(smartctl_bin, label, path):
    try:
        result = subprocess.run(
            [smartctl_bin, "-H", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return {
            "disk": label,
            "device_path": path,
            "health_status": _smart_health(result.stdout),
            "output": result.stdout.strip(),
        }
    except Exception as error:
        return {
            "disk": label,
            "device_path": path,
            "health_status": "ERROR",
            "error": str(error),
        }


class SystemDoctorExtendedMixin:
    def _check_startup(self):
        startup = []
        if platform.system().lower() == "windows":
            try:
                import winreg

                reg_paths = [
                    (
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Run",
                        "HKCU\\Run",
                    ),
                    (
                        winreg.HKEY_LOCAL_MACHINE,
                        r"Software\Microsoft\Windows\CurrentVersion\Run",
                        "HKLM\\Run",
                    ),
                ]
                for hkey, subkey, label in reg_paths:
                    try:
                        with winreg.OpenKey(hkey, subkey, 0, winreg.KEY_READ) as key:
                            info = winreg.QueryInfoKey(key)
                            for index in range(info[1]):
                                name, value, _ = winreg.EnumValue(key, index)
                                startup.append(
                                    {"name": name, "command": value, "source": label}
                                )
                    except Exception:
                        pass
            except Exception:
                pass
        return {"startup_programs": startup}

    def _check_errors(self):
        if platform.system().lower() == "windows":
            errors = _windows_recent_errors()
        else:
            errors = _linux_recent_errors()
        return {"error_count": len(errors), "recent_errors": errors}

    def _check_smart(self):
        system = platform.system().lower()
        if system not in ("windows", "linux"):
            return "not_available"
        smartctl_bin = shutil.which("smartctl") or shutil.which("smartctl.cmd")
        if not smartctl_bin:
            return {
                "status": "not_available",
                "message": "smartctl command not found. Please install smartmontools.",
            }

        drives = _scan_smartctl_drives(smartctl_bin)
        if not drives:
            drives = (
                _windows_fallback_drives()
                if system == "windows"
                else _linux_fallback_drives()
            )
        disk_reports = [
            _smart_report(smartctl_bin, label, drive_path)
            for label, drive_path in drives
        ]
        return {"status": "available", "drives": disk_reports}
