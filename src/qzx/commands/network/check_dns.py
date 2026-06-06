#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CheckDns Command - Queries A, AAAA, MX, TXT, NS, and CNAME records for a domain.
"""

import os
import sys
import socket
import subprocess
import platform
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class CheckDnsCommand(CommandBase):
    """
    Command to inspect and return all common DNS records for a specific domain name.
    """
    
    name = "checkDns"
    description = "Queries A, AAAA, MX, TXT, NS, and CNAME DNS records for a given domain"
    category = "network"
    
    parameters = [
        {
            'name': 'domain',
            'description': 'Domain name to query (e.g. google.com)',
            'required': True
        }
    ]
    
    examples = [
        {
            'command': 'qzx checkDns google.com',
            'description': 'Get all DNS records for google.com'
        }
    ]
    
    def execute(self, domain):
        """
        Queries DNS records for a domain
        
        Args:
            domain (str): Domain to query
            
        Returns:
            Dictionary with resolved DNS records
        """
        domain = domain.strip().lower()
        if not domain:
            return {
                "success": False,
                "error": "Domain name must not be empty.",
                "message": "Domain name must not be empty."
            }
            
        results = {
            "A": [],
            "AAAA": [],
            "MX": [],
            "TXT": [],
            "NS": [],
            "CNAME": []
        }
        
        # Fallback to basic socket resolution for A/AAAA
        try:
            addr_info = socket.getaddrinfo(domain, None)
            for item in addr_info:
                ip = item[4][0]
                if ":" in ip:
                    if ip not in results["AAAA"]:
                        results["AAAA"].append(ip)
                else:
                    if ip not in results["A"]:
                        results["A"].append(ip)
        except Exception:
            pass
            
        # Use nslookup to query detailed records (MX, TXT, NS, CNAME)
        record_types = ["MX", "TXT", "NS", "CNAME", "A", "AAAA"]
        errors = []
        
        for r_type in record_types:
            try:
                # Run nslookup
                if platform.system().lower() == "windows":
                    cmd = ["nslookup", f"-query={r_type.lower()}", domain]
                else:
                    cmd = ["nslookup", f"-type={r_type}", domain]
                    
                res = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5,
                    check=False
                )
                
                if res.returncode == 0:
                    parsed = self._parse_nslookup(res.stdout, r_type, domain)
                    for item in parsed:
                        if item not in results[r_type]:
                            results[r_type].append(item)
            except Exception as e:
                errors.append(f"Error querying {r_type}: {str(e)}")
                
        # Clean results (remove empty lists if they couldn't be resolved)
        summary = {k: len(v) for k, v in results.items()}
        
        msg = f"DNS records resolved for '{domain}':\n"
        for r_type, count in summary.items():
            if count > 0:
                values = ", ".join(results[r_type][:3])
                if len(results[r_type]) > 3:
                    values += f" (+{count - 3} more)"
                msg += f"- {r_type} ({count}): {values}\n"
            else:
                msg += f"- {r_type}: None found\n"
                
        return {
            "success": True,
            "domain": domain,
            "records": results,
            "summary": summary,
            "errors": errors,
            "message": msg
        }
        
    def _parse_nslookup(self, stdout, record_type, domain):
        """Parses nslookup stdout to extract record values"""
        records = []
        lines = stdout.splitlines()
        
        # Skip local resolver info (usually first few lines containing Server/Address)
        data_started = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # nslookup puts answers after "Non-authoritative answer:" or similar markers
            if "non-authoritative" in line.lower() or "answer:" in line.lower():
                data_started = True
                continue
            if line.startswith("Server:") or line.startswith("Address:"):
                # Ensure we don't capture local resolver address
                continue
                
            # Simple line checks
            if record_type == "MX":
                if "mail exchanger" in line:
                    # e.g.: google.com     mail exchanger = 10 smtp.google.com
                    parts = line.split("mail exchanger =")
                    if len(parts) == 2:
                        records.append(parts[1].strip())
            elif record_type == "TXT":
                if "text =" in line:
                    # e.g.: google.com     text = "v=spf1 include:_spf.google.com ~all"
                    parts = line.split("text =")
                    if len(parts) == 2:
                        records.append(parts[1].strip().strip('"'))
            elif record_type == "NS":
                if "nameserver =" in line:
                    # e.g.: google.com     nameserver = ns1.google.com
                    parts = line.split("nameserver =")
                    if len(parts) == 2:
                        records.append(parts[1].strip())
            elif record_type == "CNAME":
                if "canonical name =" in line:
                    parts = line.split("canonical name =")
                    if len(parts) == 2:
                        records.append(parts[1].strip())
            elif record_type in ("A", "AAAA"):
                # Parse standard address line, e.g. "Address: 142.251.163.100" or just "142.251.163.100"
                if line.startswith("Address:") or line.startswith("Addresses:"):
                    addr = line.split(":", 1)[1].strip()
                    if addr and not addr.startswith("::") and not addr.startswith("0.0.0.0"):
                        records.extend([a.strip() for a in addr.split() if a.strip()])
                elif data_started and (line.replace(".", "").isdigit() or ":" in line):
                    # Direct address line
                    records.extend([a.strip() for a in line.split() if a.strip()])
                    
        return records
