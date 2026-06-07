#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SystemDoctor Command - Comprehensive system diagnostic check
"""

import os
import sys
import platform
import subprocess
import socket
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

# Optional psutil import
try:
    import psutil
except ImportError:
    psutil = None

class SystemDoctorCommand(CommandBase):
    """
    Command to run a comprehensive diagnostic of the host operating system.
    """
    
    name = "systemDoctor"
    description = "Performs a complete diagnostic of the CPU, RAM, disks, network, PATH, services, ports, and system errors"
    category = "system"
    
    parameters = [
        {
            'name': 'quick',
            'description': 'If True, perform only a quick essential system check (default: False)',
            'required': False,
            'default': False
        }
    ]
    
    examples = [
        {
            'command': 'qzx systemDoctor',
            'description': 'Run full system diagnostic'
        },
        {
            'command': 'qzx systemDoctor --quick True',
            'description': 'Run quick essential check'
        }
    ]
    
    def execute(self, quick=False):
        """
        Executes the system diagnostic check
        """
        # Parse boolean if passed as string
        if isinstance(quick, str):
            quick = quick.strip().lower() in ('true', '1', 'yes')
            
        results = {
            "cpu": "not_available",
            "ram": "not_available",
            "disk": "not_available",
            "network": "not_available",
            "path": "not_available",
            "services": "not_available",
            "ports": "not_available",
            "startup": "not_available",
            "errors": "not_available",
            "smart": "not_available",
            "health_score": 100,
            "recommendations": []
        }
        
        issues = []
        
        # 1. CPU
        try:
            results["cpu"] = self._check_cpu(quick)
            if isinstance(results["cpu"], dict):
                usage = results["cpu"].get("usage_percent", 0)
                if usage > 85:
                    issues.append(("High CPU usage", f"CPU load is currently at {usage}%", "medium"))
        except Exception as e:
            results["cpu"] = {"error": str(e)}
            
        # 2. RAM
        try:
            results["ram"] = self._check_ram()
            if isinstance(results["ram"], dict) and "virtual" in results["ram"]:
                vmem = results["ram"]["virtual"]
                percent = vmem.get("percent", 0)
                if percent > 90:
                    issues.append(("Critical memory usage", f"RAM usage is at {percent}%", "high"))
                elif percent > 75:
                    issues.append(("High memory usage", f"RAM usage is at {percent}%", "medium"))
        except Exception as e:
            results["ram"] = {"error": str(e)}
            
        # 3. Disk
        try:
            results["disk"] = self._check_disk(quick)
            if isinstance(results["disk"], dict) and "partitions" in results["disk"]:
                for part in results["disk"]["partitions"]:
                    use_pct = part.get("percent", 0)
                    mount = part.get("mountpoint", "")
                    if use_pct > 90:
                        issues.append(("Critical disk space", f"Partition '{mount}' is {use_pct}% full", "high"))
                    elif use_pct > 80:
                        issues.append(("Low disk space", f"Partition '{mount}' is {use_pct}% full", "medium"))
        except Exception as e:
            results["disk"] = {"error": str(e)}
            
        # 4. Network
        try:
            results["network"] = self._check_network(quick)
            if isinstance(results["network"], dict):
                if not results["network"].get("dns_ok", False):
                    issues.append(("DNS Failure", "Failed to resolve external domain (google.com)", "high"))
        except Exception as e:
            results["network"] = {"error": str(e)}
            
        # 5. PATH
        try:
            results["path"] = self._check_path()
            if isinstance(results["path"], dict):
                broken = results["path"].get("broken", [])
                if broken:
                    issues.append(("Broken PATH entries", f"Found {len(broken)} non-existent directories in PATH", "low"))
        except Exception as e:
            results["path"] = {"error": str(e)}
            
        # 6. Services (skip if quick)
        if not quick:
            try:
                results["services"] = self._check_services()
            except Exception as e:
                results["services"] = {"error": str(e)}
                
        # 7. Ports (skip if quick)
        if not quick:
            try:
                results["ports"] = self._check_ports()
            except Exception as e:
                results["ports"] = {"error": str(e)}
                
        # 8. Startup (skip if quick)
        if not quick:
            try:
                results["startup"] = self._check_startup()
            except Exception as e:
                results["startup"] = {"error": str(e)}
                
        # 9. Errors (skip if quick)
        if not quick:
            try:
                results["errors"] = self._check_errors()
                if isinstance(results["errors"], dict) and results["errors"].get("error_count", 0) > 0:
                    issues.append(("System errors found", f"Detected recent system error log events", "medium"))
            except Exception as e:
                results["errors"] = {"error": str(e)}
                
        # 9b. SMART Check (skip if quick)
        if not quick:
            try:
                results["smart"] = self._check_smart()
                if isinstance(results["smart"], dict) and results["smart"].get("status") == "available":
                    for drive in results["smart"].get("drives", []):
                        status = drive.get("health_status")
                        disk_label = drive.get("disk")
                        if status == "FAILED":
                            issues.append(("Disk SMART Failure", f"Physical drive '{disk_label}' is reporting SMART Failure status!", "high"))
                        elif status == "WARNING":
                            issues.append(("Disk SMART Warning", f"Physical drive '{disk_label}' has SMART health warnings!", "medium"))
            except Exception as e:
                results["smart"] = {"error": str(e)}
                
        # Calculate health score (0-100)
        score = 100
        for title, msg, severity in issues:
            if severity == "high":
                score -= 20
            elif severity == "medium":
                score -= 10
            elif severity == "low":
                score -= 5
        results["health_score"] = max(0, min(100, score))
        
        # Generate recommendations
        recommendations = []
        for title, msg, severity in issues:
            recommendations.append({
                "title": title,
                "description": msg,
                "severity": severity
            })
        results["recommendations"] = recommendations
        
        return {
            "success": True,
            "message": "System diagnostic completed successfully.",
            "details": results
        }
        
    def _check_cpu(self, quick):
        info = {
            "cores_logical": os.cpu_count() or 0,
            "cores_physical": os.cpu_count() or 0,
            "usage_percent": 0.0,
            "temperature_c": None
        }
        
        if psutil:
            info["cores_logical"] = psutil.cpu_count(logical=True)
            info["cores_physical"] = psutil.cpu_count(logical=False) or info["cores_logical"]
            info["usage_percent"] = psutil.cpu_percent(interval=0.1)
            
            # Try to get temperature
            if not quick and hasattr(psutil, "sensors_temperatures"):
                try:
                    temps = psutil.sensors_temperatures()
                    if temps:
                        for name, entries in temps.items():
                            if entries:
                                info["temperature_c"] = entries[0].current
                                break
                except:
                    pass
        else:
            # Fallback if no psutil
            try:
                if platform.system() == "Windows":
                    cmd = ["wmic", "cpu", "get", "LoadPercentage"]
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', check=False)
                    lines = [l.strip() for l in res.stdout.split("\n") if l.strip()]
                    if len(lines) > 1:
                        info["usage_percent"] = float(lines[1])
                else:
                    # Linux uptime/loadavg fallback
                    with open("/proc/loadavg", "r") as f:
                        load = float(f.read().split()[0])
                        info["usage_percent"] = min(100.0, (load / (info["cores_logical"] or 1)) * 100.0)
            except:
                pass
        return info
        
    def _check_ram(self):
        if psutil:
            vmem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            return {
                "virtual": {
                    "total_bytes": vmem.total,
                    "used_bytes": vmem.used,
                    "free_bytes": vmem.free,
                    "percent": vmem.percent
                },
                "swap": {
                    "total_bytes": swap.total,
                    "used_bytes": swap.used,
                    "free_bytes": swap.free,
                    "percent": swap.percent
                }
            }
        else:
            # Minimal fallback
            if platform.system() == "Windows":
                # WMIC fallback
                try:
                    cmd = ["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/Value"]
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', check=False)
                    data = {}
                    for line in res.stdout.split("\n"):
                        if "=" in line:
                            k, v = line.split("=", 1)
                            data[k.strip()] = int(v.strip())
                    total = data.get("TotalVisibleMemorySize", 0) * 1024
                    free = data.get("FreePhysicalMemory", 0) * 1024
                    used = total - free
                    pct = round((used / total) * 100, 1) if total else 0
                    return {
                        "virtual": {"total_bytes": total, "used_bytes": used, "free_bytes": free, "percent": pct},
                        "swap": "not_available"
                    }
                except:
                    pass
            return "not_available"
            
    def _check_disk(self, quick):
        partitions = []
        if psutil:
            parts = psutil.disk_partitions(all=False)
            for p in parts:
                # Skip cdrom or empty mountpoints on Windows
                if 'cdrom' in p.opts or not p.mountpoint:
                    continue
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    partitions.append({
                        "device": p.device,
                        "mountpoint": p.mountpoint,
                        "fstype": p.fstype,
                        "total_bytes": usage.total,
                        "used_bytes": usage.used,
                        "free_bytes": usage.free,
                        "percent": usage.percent
                    })
                except:
                    pass
        else:
            # Fallback
            if platform.system() == "Windows":
                try:
                    cmd = ["wmic", "logicaldisk", "get", "DeviceID,FreeSpace,Size", "/Value"]
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', check=False)
                    curr = {}
                    for line in res.stdout.split("\n"):
                        if "=" in line:
                            k, v = line.split("=", 1)
                            curr[k.strip()] = v.strip()
                        elif not line.strip() and curr:
                            if "DeviceID" in curr:
                                dev = curr["DeviceID"]
                                free = int(curr.get("FreeSpace", 0) or 0)
                                size = int(curr.get("Size", 0) or 0)
                                used = size - free
                                pct = round((used / size) * 100, 1) if size else 0
                                partitions.append({
                                    "device": dev,
                                    "mountpoint": dev + "\\",
                                    "fstype": "unknown",
                                    "total_bytes": size,
                                    "used_bytes": used,
                                    "free_bytes": free,
                                    "percent": pct
                                })
                            curr = {}
                except:
                    pass
        return {"partitions": partitions}
        
    def _check_network(self, quick):
        net_info = {
            "interfaces": [],
            "dns_ok": False,
            "external_ip": None
        }
        
        # interfaces & IPs
        if psutil:
            try:
                addrs = psutil.net_if_addrs()
                for name, info_list in addrs.items():
                    ips = []
                    for addr in info_list:
                        if addr.family == socket.AF_INET:
                            ips.append(addr.address)
                    if ips:
                        net_info["interfaces"].append({
                            "name": name,
                            "ips": ips
                        })
            except:
                pass
        else:
            try:
                hostname = socket.gethostname()
                ips = socket.gethostbyname_ex(hostname)[2]
                net_info["interfaces"].append({
                    "name": "hostname_resolve",
                    "ips": ips
                })
            except:
                pass
                
        # basic DNS connectivity
        try:
            socket.setdefaulttimeout(3.0)
            socket.gethostbyname("google.com")
            net_info["dns_ok"] = True
        except:
            net_info["dns_ok"] = False
            
        return net_info
        
    def _check_path(self):
        path_env = os.environ.get("PATH", "")
        sep = os.pathsep
        entries = [e.strip() for e in path_env.split(sep) if e.strip()]
        
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
            "broken": broken
        }
        
    def _check_services(self):
        is_windows = platform.system().lower() == "windows"
        critical_services = []
        
        if is_windows:
            # Query standard Windows services
            services_to_check = ["Winmgmt", "LanmanServer", "wuauserv", "Dhcp", "EventLog"]
            for name in services_to_check:
                try:
                    res = subprocess.run(
                        ["sc", "query", name],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        check=False
                    )
                    status = "unknown"
                    for line in res.stdout.split("\n"):
                        if "STATE" in line:
                            status = line.split(":", 1)[1].strip()
                            break
                    critical_services.append({
                        "name": name,
                        "status": status
                    })
                except:
                    pass
        else:
            # Linux systemd check
            try:
                res = subprocess.run(
                    ["systemctl", "list-units", "--type=service", "--state=running", "--no-legend"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    check=False
                )
                for line in res.stdout.split("\n"):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 3:
                            critical_services.append({
                                "name": parts[0],
                                "status": "running"
                            })
            except:
                pass
                
        return {"critical_services": critical_services}
        
    def _check_ports(self):
        ports = []
        if psutil:
            try:
                conns = psutil.net_connections(kind='inet')
                for c in conns:
                    if c.status == 'LISTEN':
                        ports.append({
                            "port": c.laddr.port,
                            "ip": c.laddr.ip,
                            "pid": c.pid,
                            "name": psutil.Process(c.pid).name() if c.pid else "unknown"
                        })
            except:
                pass
        else:
            # fallback to netstat
            try:
                if platform.system() == "Windows":
                    cmd = ["netstat", "-ano"]
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', check=False)
                    for line in res.stdout.split("\n"):
                        if "LISTENING" in line:
                            parts = line.split()
                            if len(parts) >= 4:
                                addr = parts[1]
                                pid = parts[4]
                                port = addr.split(":")[-1]
                                ports.append({
                                    "port": int(port),
                                    "ip": addr,
                                    "pid": int(pid) if pid.isdigit() else None,
                                    "name": "unknown"
                                })
            except:
                pass
        # Unique ports sorted
        unique_ports = []
        seen = set()
        for p in ports:
            key = (p["port"], p["ip"])
            if key not in seen:
                seen.add(key)
                unique_ports.append(p)
        return {"listening": sorted(unique_ports, key=lambda x: x["port"])[:50]} # Cap at 50
        
    def _check_startup(self):
        startup = []
        is_windows = platform.system().lower() == "windows"
        if is_windows:
            try:
                import winreg
                reg_paths = [
                    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU\\Run"),
                    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM\\Run")
                ]
                for hkey, subkey, label in reg_paths:
                    try:
                        with winreg.OpenKey(hkey, subkey, 0, winreg.KEY_READ) as key:
                            info = winreg.QueryInfoKey(key)
                            for i in range(info[1]):
                                name, val, _ = winreg.EnumValue(key, i)
                                startup.append({
                                    "name": name,
                                    "command": val,
                                    "source": label
                                })
                    except:
                        pass
            except:
                pass
        return {"startup_programs": startup}
        
    def _check_errors(self):
        errors = []
        is_windows = platform.system().lower() == "windows"
        if is_windows:
            try:
                # Query System event log for errors in the last 24h/newest 10
                cmd = ["powershell", "-NoProfile", "-Command", 
                       "Get-EventLog -LogName System -EntryType Error -Newest 5 | Select-Object EventID, Source, Message, TimeGenerated | ConvertTo-Json -Compress"]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', check=False)
                if res.returncode == 0 and res.stdout.strip():
                    raw_data = json.loads(res.stdout.strip())
                    data_list = raw_data if isinstance(raw_data, list) else [raw_data]
                    for d in data_list:
                        errors.append({
                            "event_id": d.get("EventID"),
                            "source": d.get("Source"),
                            "message": d.get("Message", "").strip(),
                            "time": d.get("TimeGenerated")
                        })
            except:
                pass
        else:
            # Linux syslog errors
            try:
                if os.path.exists("/var/log/syslog"):
                    cmd = ["tail", "-n", "50", "/var/log/syslog"]
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', check=False)
                    for line in res.stdout.split("\n"):
                        if "error" in line.lower() or "fail" in line.lower():
                            errors.append({
                                "message": line.strip()
                            })
            except:
                pass
        return {
            "error_count": len(errors),
            "recent_errors": errors
        }

    def _check_smart(self):
        """
        Retrieves health status of physical disks using SMART technology.
        """
        system = platform.system().lower()
        if system not in ('windows', 'linux'):
            return "not_available"
            
        # Check if smartctl is installed/available
        import shutil
        smartctl_bin = shutil.which("smartctl") or shutil.which("smartctl.cmd")
        if not smartctl_bin:
            return {
                "status": "not_available",
                "message": "smartctl command not found. Please install smartmontools."
            }
            
        drives = []
        # Try to scan drives via smartctl --scan
        try:
            scan_res = subprocess.run(
                [smartctl_bin, "--scan"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=False
            )
            if scan_res.returncode == 0:
                for line in scan_res.stdout.splitlines():
                    # Format: /dev/sda -d ata # /dev/sda, ATA device
                    parts = line.strip().split()
                    if parts:
                        dev_path = parts[0]
                        drives.append((dev_path, dev_path))
        except:
            pass
            
        # If smartctl --scan didn't yield anything, use OS physical drive fallback list
        if not drives:
            if system == 'windows':
                try:
                    res = subprocess.run(["wmic", "diskdrive", "get", "DeviceID"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', check=False)
                    if res.returncode == 0:
                        for line in res.stdout.splitlines():
                            line = line.strip()
                            if line and "DeviceID" not in line:
                                drive_name = line.split("\\")[-1]
                                if drive_name:
                                    drives.append((drive_name, f"\\\\.\\{drive_name}"))
                except:
                    pass
                if not drives:
                    drives.append(("PhysicalDrive0", "\\\\.\\PhysicalDrive0"))
            elif system == 'linux':
                try:
                    res = subprocess.run(["lsblk", "-d", "-n", "-o", "NAME"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', check=False)
                    if res.returncode == 0:
                        for line in res.stdout.splitlines():
                            name = line.strip()
                            if name:
                                drives.append((name, f"/dev/{name}"))
                except:
                    pass
                if not drives:
                    drives.append(("sda", "/dev/sda"))
                    
        disk_reports = []
        for label, path in drives:
            try:
                # Get drive health status using smartctl -H
                res = subprocess.run(
                    [smartctl_bin, "-H", path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    check=False
                )
                
                # Check for PASSED, FAILED or WARNING
                health = "UNKNOWN"
                stdout = res.stdout.upper()
                if "PASSED" in stdout:
                    health = "PASSED"
                elif "FAILED" in stdout or "FAILING" in stdout:
                    health = "FAILED"
                elif "WARNING" in stdout:
                    health = "WARNING"
                
                disk_reports.append({
                    "disk": label,
                    "device_path": path,
                    "health_status": health,
                    "output": res.stdout.strip()
                })
            except Exception as e:
                disk_reports.append({
                    "disk": label,
                    "device_path": path,
                    "health_status": "ERROR",
                    "error": str(e)
                })
                
        return {
            "status": "available",
            "drives": disk_reports
        }
