#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CheckSslCertificate Command - Validates SSL/TLS certificates for a remote host.
"""

import os
import sys
import socket
import ssl
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class CheckSslCertificateCommand(CommandBase):
    """
    Command to fetch, parse, and analyze the SSL/TLS certificate of a remote server.
    """
    
    name = "checkSslCertificate"
    description = "Inspects the SSL/TLS certificate of a hostname, checking validity dates and issuers"
    category = "network"
    
    parameters = [
        {
            'name': 'host',
            'description': 'Hostname of the server to check (e.g. google.com)',
            'required': True
        },
        {
            'name': 'port',
            'description': 'Port number (defaults to 443)',
            'required': False,
            'default': '443'
        }
    ]
    
    examples = [
        {
            'command': 'qzx checkSslCertificate google.com',
            'description': 'Inspect the SSL certificate for google.com on port 443'
        },
        {
            'command': 'qzx checkSslCertificate expired.badssl.com 443',
            'description': 'Inspect certificate for expired.badssl.com'
        }
    ]
    
    def execute(self, host, port='443'):
        """
        Retrieves and parses the SSL certificate
        
        Args:
            host (str): Remote host name
            port (str/int): Connection port
            
        Returns:
            Dictionary with SSL certificate information
        """
        host = host.strip()
        if not host:
            return {
                "success": False,
                "error": "Host name must not be empty.",
                "message": "Host name must not be empty."
            }
            
        try:
            port_num = int(port)
        except ValueError:
            return {
                "success": False,
                "error": f"Port must be an integer, received '{port}'",
                "message": f"Failed to check SSL: Port must be an integer, received '{port}'"
            }
            
        try:
            # Create default SSL context
            context = ssl.create_default_context()
            
            # Disable hostname check and certificate validation temporarily to inspect expired/invalid certificates too
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            print(f"Connecting securely to {host}:{port_num}...")
            
            with socket.create_connection((host, port_num), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    ssl_version = ssock.version()
                    
            if not cert:
                # If cert is empty, it could mean connection is not using certificate (verify mode CERT_NONE is on,
                # but binary cert can be fetched manually if empty)
                # Let's request binary certificate and load it manually
                try:
                    with socket.create_connection((host, port_num), timeout=5) as sock:
                        with context.wrap_socket(sock, server_hostname=host) as ssock:
                            der_cert = ssock.getpeercert(binary_form=True)
                            cert = ssl.DER_cert_to_dict(der_cert)
                except Exception as der_err:
                    return {
                        "success": False,
                        "error": f"Could not retrieve certificate details: {str(der_err)}",
                        "message": f"Connection succeeded but no SSL certificate details could be parsed for '{host}'."
                    }
            
            # Parse Dates
            not_before_str = cert.get("notBefore", "")
            not_after_str = cert.get("notAfter", "")
            
            start_date = self._parse_date(not_before_str)
            expiry_date = self._parse_date(not_after_str)
            
            now = datetime.now(timezone.utc)
            
            days_left = 0
            is_valid = False
            is_expired = True
            
            if expiry_date:
                is_expired = now > expiry_date
                time_diff = expiry_date - now
                days_left = time_diff.days
                
                # Check if currently valid (started and not expired)
                if start_date:
                    is_valid = (now >= start_date) and (now <= expiry_date)
                else:
                    is_valid = not is_expired
                    
            # Extract Subject and Issuer commonNames
            subject_dict = self._parse_rdn(cert.get("subject", []))
            issuer_dict = self._parse_rdn(cert.get("issuer", []))
            
            subject_cn = subject_dict.get("commonName", "unknown")
            issuer_cn = issuer_dict.get("commonName", "unknown")
            
            # Extract Subject Alt Names (SANs)
            sans = []
            for alt_name in cert.get("subjectAltName", []):
                if alt_name[0] == "DNS":
                    sans.append(alt_name[1])
                    
            # Check host matching CN or SAN
            hostname_match = self._match_hostname(host, subject_cn, sans)
            
            status_text = "VALID" if (is_valid and hostname_match) else "INVALID"
            if is_expired:
                status_text += " (EXPIRED)"
            elif not hostname_match:
                status_text += " (HOSTNAME_MISMATCH)"
                
            msg = f"SSL Certificate Diagnostic for '{host}':\n"
            msg += f"- Status: {status_text}\n"
            msg += f"- Common Name (CN): {subject_cn}\n"
            msg += f"- Issuer: {issuer_cn}\n"
            msg += f"- SSL Version: {ssl_version}\n"
            msg += f"- Cipher Suite: {cipher[0]} ({cipher[1]} bits)\n"
            if expiry_date:
                msg += f"- Expiry Date: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')} UTC ({days_left} days left)\n"
            if sans:
                msg += f"- Alt Names (SAN): {', '.join(sans[:5])}"
                if len(sans) > 5:
                    msg += f" (+{len(sans) - 5} more)"
                    
            return {
                "success": True,
                "host": host,
                "port": port_num,
                "is_valid": is_valid and hostname_match,
                "is_expired": is_expired,
                "hostname_match": hostname_match,
                "days_remaining": days_left,
                "subject": subject_dict,
                "issuer": issuer_dict,
                "subject_alt_names": sans,
                "ssl_version": ssl_version,
                "cipher_suite": cipher[0],
                "cipher_bits": cipher[1],
                "dates": {
                    "not_before": start_date.strftime('%Y-%m-%d %H:%M:%S') if start_date else None,
                    "not_after": expiry_date.strftime('%Y-%m-%d %H:%M:%S') if expiry_date else None
                },
                "message": msg
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to check SSL certificate for {host}: {str(e)}"
            }
            
    def _parse_date(self, date_str):
        """Helper to parse certificate date strings"""
        if not date_str:
            return None
        # Try a few formats
        for fmt in ("%b %d %H:%M:%S %Y %Z", "%b  %d %H:%M:%S %Y %Z", "%b %d %H:%M:%S %Y", "%Y%m%d%H%M%SZ"):
            try:
                # Add explicit timezone offset info as UTC since SSL certificates specify GMT/UTC
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                pass
        return None
        
    def _parse_rdn(self, rdn_structure):
        """Parses RDN tuple structure into a flat dictionary"""
        flat = {}
        for rdn in rdn_structure:
            for item in rdn:
                if len(item) == 2:
                    flat[item[0]] = item[1]
        return flat
        
    def _match_hostname(self, host, cn, sans):
        """Checks if hostname matches certificate Common Name or Subject Alt Names (supports wildcards)"""
        import fnmatch
        host = host.lower()
        candidates = [cn.lower()] + [san.lower() for san in sans]
        
        for cand in candidates:
            if cand == host:
                return True
            # Wildcard checking, e.g. *.google.com matches mail.google.com but not google.com or a.b.google.com
            if "*" in cand:
                # fnmatch will translate *.google.com to regex. Let's do simple matching.
                # E.g. replace '*' with one subdomain component
                if fnmatch.fnmatch(host, cand):
                    return True
        return False
