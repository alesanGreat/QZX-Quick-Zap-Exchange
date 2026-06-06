#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ListSystemServices Command - Lists running and stopped system services (Windows Services / Systemd services).
"""

import os
import sys
import platform
import subprocess
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class ListSystemServicesCommand(CommandBase):
    """
    Command to inspect active and stopped system services on the OS.
    """
    
    name = "listSystemServices"
    description = "Lists system services and their running status (supports Windows and Linux)"
    category = "system"
    
    parameters = [
        {
            'name': 'status',
            'description': 'Filter by service status (running, stopped, all - defaults to all)',
            'required': False,
            'default': 'all'
        }
    ]
    
    examples = [
        {
            'command': 'qzx listSystemServices',
            'description': 'List all system services'
        },
        {
            'command': 'qzx listSystemServices running',
            'description': 'List only active running system services'
        }
    ]
    
    def execute(self, status='all'):
        """
        Retrieves system services
        
        Args:
            status (str): Status filter (running, stopped, all)
            
        Returns:
            Dictionary listing all matching services
        """
        status_filter = status.strip().lower()
        if status_filter not in ('all', 'running', 'stopped'):
            status_filter = 'all'
            
        is_windows = platform.system().lower() == "windows"
        services = []
        errors = []
        
        try:
            if is_windows:
                # 1. Attempt PowerShell query (clean JSON output)
                ps_cmd = [
                    "powershell", "-NoProfile", "-Command",
                    "Get-Service | Select-Object Name, DisplayName, @{Name='Status';Expression={$_.Status.ToString()}} | ConvertTo-Json -Compress"
                ]
                try:
                    res = subprocess.run(
                        ps_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=5,
                        check=False
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        # Parse JSON output
                        raw_data = json.loads(res.stdout.strip())
                        # Convert to list if it was a single object
                        data_list = raw_data if isinstance(raw_data, list) else [raw_data]
                        
                        for item in data_list:
                            name = item.get("Name", "unknown")
                            display = item.get("DisplayName", "")
                            stat = item.get("Status", "unknown").lower()
                            
                            # Filter
                            if status_filter == 'all' or stat == status_filter:
                                services.append({
                                    "name": name,
                                    "display_name": display,
                                    "status": stat
                                })
                    else:
                        raise RuntimeError("PowerShell query empty or failed")
                except Exception as ps_err:
                    errors.append(f"PowerShell query failed, falling back to sc query: {str(ps_err)}")
                    # 2. Fallback to sc query
                    sc_res = subprocess.run(
                        ["sc", "query", "type=", "service", "state=", "all"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=5,
                        check=False
                    )
                    if sc_res.returncode == 0:
                        services.extend(self._parse_sc_query(sc_res.stdout, status_filter))
            else:
                # Linux systemctl list-units
                res = subprocess.run(
                    ["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--no-pager"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5,
                    check=False
                )
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        parts = line.split(None, 4)
                        if len(parts) >= 4:
                            name = parts[0]
                            active_state = parts[2]
                            desc = parts[4] if len(parts) > 4 else ""
                            
                            stat = "running" if active_state == "active" else "stopped"
                            if status_filter == 'all' or stat == status_filter:
                                services.append({
                                    "name": name,
                                    "display_name": desc,
                                    "status": stat
                                })
                else:
                    errors.append("Failed to list Linux systemctl service units.")
                    
            # Sort services alphabetically by name
            services.sort(key=lambda x: x["name"].lower())
            
            # Formulate output message
            total = len(services)
            msg = f"System Services Diagnostics (Filter: '{status_filter}'):\n"
            msg += f"- Services found: {total}\n"
            
            if total > 0:
                msg += "\nTop Services:\n"
                for index, s in enumerate(services[:10]):
                    msg += f"  - [{s['status'].upper()}] {s['name']} ({s['display_name'][:60]})\n"
                if total > 10:
                    msg += f"  ... and {total - 10} more."
            else:
                msg += "- No matching services found."
                
            return {
                "success": True,
                "status_filter": status_filter,
                "total_services": total,
                "services": services,
                "errors": errors,
                "message": msg
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to list system services: {str(e)}"
            }
            
    def _parse_sc_query(self, stdout, status_filter):
        """Parses Windows sc query output"""
        services = []
        current_service = None
        
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
                
            if line.startswith("SERVICE_NAME:"):
                current_service = line.split(":", 1)[1].strip()
            elif current_service and line.startswith("STATE"):
                # e.g.: STATE              : 4  RUNNING
                parts = line.split(":", 1)
                if len(parts) == 2:
                    val = parts[1].strip()
                    stat = "stopped"
                    if "RUNNING" in val:
                        stat = "running"
                        
                    if status_filter == 'all' or stat == status_filter:
                        services.append({
                            "name": current_service,
                            "display_name": current_service,
                            "status": stat
                        })
                current_service = None
                
        return services
