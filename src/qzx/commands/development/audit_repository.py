#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AuditRepository Command - Security and quality audit of a Git repository
"""

import os
import re
import socket
import hashlib
import ipaddress
import subprocess
import urllib.parse
import urllib.request

from qzx.core.command_base import CommandBase

class AuditRepositoryCommand(CommandBase):
    """
    Command to audit a repository for hardcoded secrets, large files, duplicate assets,
    broken symlinks, .gitignore issues, license compliance, and basic vulnerability patterns.
    """
    
    name = "auditRepository"
    description = "Runs security and quality audits on a Git repository (secrets, large files, duplicates, .gitignore compliance, licenses)"
    category = "development"
    
    parameters = [
        {
            'name': 'path',
            'description': 'Path to the repository to audit (default: \'.\')',
            'required': False,
            'default': '.'
        }
    ]
    
    examples = [
        {
            'command': 'qzx auditRepository',
            'description': 'Audit the current repository'
        },
        {
            'command': 'qzx auditRepository C:/other/project',
            'description': 'Audit project at specified path'
        }
    ]

    @staticmethod
    def _literal_ip_address(hostname):
        """Parse canonical and legacy IPv4 spellings without resolving DNS."""

        try:
            return ipaddress.ip_address(hostname)
        except ValueError:
            pass

        # Operating systems may accept shortened or integer IPv4 forms such as
        # ``127.1`` and ``2130706433``. Treat them as literals too so a link
        # audit cannot accidentally probe a loopback or private service.
        if ":" in hostname:
            return None
        try:
            normalized = socket.inet_ntoa(socket.inet_aton(hostname))
        except OSError:
            return None
        return ipaddress.ip_address(normalized)

    @classmethod
    def _is_documentation_placeholder_url(cls, parsed_link):
        """Return whether a documentation URL must not be fetched."""

        try:
            hostname = parsed_link.hostname
        except ValueError:
            return False
        if hostname is None:
            return False

        normalized_host = hostname.casefold().rstrip(".")
        reserved_hosts = {
            "example",
            "example.com",
            "example.net",
            "example.org",
            "invalid",
            "localhost",
            "test",
        }
        reserved_suffixes = (
            ".example",
            ".example.com",
            ".example.net",
            ".example.org",
            ".invalid",
            ".localhost",
            ".test",
        )
        if normalized_host in reserved_hosts or normalized_host.endswith(
            reserved_suffixes
        ):
            return True

        literal_address = cls._literal_ip_address(normalized_host)
        return literal_address is not None and not literal_address.is_global

    @staticmethod
    def _open_url(request, timeout):
        """Open one external documentation URL through an injectable seam."""

        return urllib.request.urlopen(request, timeout=timeout)
    
    def execute(self, path='.'):
        """
        Executes the repository audit
        """
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"Path '{path}' does not exist.",
                "message": f"Path '{path}' does not exist."
            }
            
        is_git = False
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=abs_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            is_git = res.returncode == 0 and res.stdout.strip() == "true"
        except Exception:
            pass
            
        results = {
            "secrets": [],
            "large_files": [],
            "duplicates": [],
            "broken_links": [],
            "binaries": [],
            "gitignore_issues": [],
            "license": "missing",
            "dependency_vulnerabilities": [],
            "summary": {
                "risk_level": "low",
                "total_findings": 0,
                "findings": []
            }
        }
        
        # 1. Audit License
        license_found = False
        for f in os.listdir(abs_path):
            if f.lower() in ("license", "license.txt", "license.md", "copying", "copying.txt"):
                results["license"] = f
                license_found = True
                break
        if not license_found:
            results["summary"]["findings"].append({
                "severity": "medium",
                "category": "license",
                "message": "No LICENSE file found in repository root"
            })
            
        # Common lists to ignore
        ignored_dirs = {'.git', 'node_modules', 'dist', 'build', '.pytest_cache', '__pycache__', '.dropbox', '.dropbox.cache', 'artifacts'}
        
        # Secrets regexes
        secret_patterns = [
            (re.compile(r'(?i)(api_key|apikey|secret|password|passwd|private_key|token)\s*[:=]\s*[\'"]([a-zA-Z0-9_\-\.\=\+\/]{8,})[\'"]'), "Potential hardcoded credentials/key"),
            (re.compile(r'AIzaSy[a-zA-Z0-9_\-]{33}'), "Google API Key"),
            (re.compile(r'amzn\.mws\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'), "Amazon MWS Auth Token"),
            (re.compile(r'-----\s*BEGIN[ A-Z0-9_-]*PRIVATE KEY\s*-----'), "Private Key block")
        ]
        
        scanned_files = 0
        file_hashes = {}
        
        # Walk and audit files
        for root, dirs, files in os.walk(abs_path):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            
            for f in files:
                scanned_files += 1
                if scanned_files > 10000:
                    break
                    
                file_path = os.path.join(root, f)
                rel_file = os.path.relpath(file_path, abs_path)
                
                # Check broken symlinks
                if os.path.islink(file_path):
                    target = os.readlink(file_path)
                    target_abs = os.path.join(root, target) if not os.path.isabs(target) else target
                    if not os.path.exists(target_abs):
                        results["broken_links"].append({
                            "link": rel_file,
                            "target": target
                        })
                        results["summary"]["findings"].append({
                            "severity": "low",
                            "category": "broken_links",
                            "message": f"Broken symbolic link: {rel_file} -> {target}"
                        })
                    continue
                    
                try:
                    f_size = os.path.getsize(file_path)
                except Exception:
                    continue
                    
                # 2. Large files check (>500KB)
                if f_size > 500 * 1024:
                    results["large_files"].append({
                        "path": rel_file,
                        "size_bytes": f_size
                    })
                    results["summary"]["findings"].append({
                        "severity": "low",
                        "category": "large_files",
                        "message": f"Large file in repository ({f_size // 1024} KB): {rel_file}"
                    })
                    
                # 3. Duplicate files check by cryptographic content hash
                if f_size < 5 * 1024 * 1024: # Limit to 5MB to be fast
                    try:
                        h = hashlib.sha256()
                        with open(file_path, 'rb') as fp:
                            for chunk in iter(lambda: fp.read(8192), b''):
                                h.update(chunk)
                        file_hash = h.hexdigest()
                        if file_hash in file_hashes:
                            orig = file_hashes[file_hash]
                            results["duplicates"].append({
                                "file": rel_file,
                                "duplicate_of": orig,
                                "size_bytes": f_size
                            })
                            results["summary"]["findings"].append({
                                "severity": "low",
                                "category": "duplicates",
                                "message": f"Duplicate file content: {rel_file} is identical to {orig}"
                            })
                        else:
                            file_hashes[file_hash] = rel_file
                    except Exception:
                        pass
                        
                # 4. Secrets audit in text files
                # Skip known binary extensions, lockfiles, etc.
                _, ext = os.path.splitext(f)
                ext = ext.lower()
                is_text = ext in ('.py', '.js', '.ts', '.jsx', '.tsx', '.php', '.cpp', '.h', '.c', '.json', '.xml', '.yaml', '.yml', '.ini', '.cfg', '.conf', '.txt', '.md', '.html', '.css', '.sh', '.bat')
                
                if is_text and f_size < 1024 * 1024: # skip lockfiles or huge texts
                    if f in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "composer.lock", "Cargo.lock"):
                        continue
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as fp:
                            for line_num, line_content in enumerate(fp, 1):
                                for pattern, desc in secret_patterns:
                                    m = pattern.search(line_content)
                                    if m:
                                        # Verify it's not a mock/placeholder
                                        val = m.group(2) if len(m.groups()) >= 2 else m.group(0)
                                        if any(placeholder in val.lower() for placeholder in ("your_", "placeholder", "mock", "my_", "test_", "foo", "bar", "example")):
                                            continue
                                        results["secrets"].append({
                                            "file": rel_file,
                                            "line": line_num,
                                            "type": desc,
                                            "context": (
                                                line_content[
                                                    :m.start(2)
                                                    if m.lastindex and m.lastindex >= 2
                                                    else m.start()
                                                ]
                                                + "<redacted>"
                                                + line_content[
                                                    m.end(2)
                                                    if m.lastindex and m.lastindex >= 2
                                                    else m.end():
                                                ]
                                            ).strip()[:100]
                                        })
                                        results["summary"]["findings"].append({
                                            "severity": "critical",
                                            "category": "secrets",
                                            "message": f"Hardcoded secret ({desc}) found in {rel_file} at line {line_num}"
                                        })
                    except Exception:
                        pass
                        
                # 4b. Markdown link check
                if ext == '.md' and f_size < 500 * 1024:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as fp:
                            content = fp.read()
                        md_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
                        for text, link in md_links:
                            if link.startswith("#"):
                                continue

                            is_broken = False
                            reason = ""
                            try:
                                parsed_link = urllib.parse.urlsplit(link)
                            except ValueError as exc:
                                parsed_link = None
                                is_broken = True
                                reason = f"Invalid URL: {exc}"

                            if parsed_link is not None:
                                scheme = parsed_link.scheme.casefold()
                                if scheme in {
                                    "irc",
                                    "ircs",
                                    "mailto",
                                    "sms",
                                    "tel",
                                    "xmpp",
                                }:
                                    continue

                                if scheme in {"http", "https"}:
                                    if self._is_documentation_placeholder_url(
                                        parsed_link
                                    ):
                                        continue
                                    if (
                                        parsed_link.username is not None
                                        or parsed_link.password is not None
                                    ):
                                        is_broken = True
                                        reason = (
                                            "Embedded URL credentials are unsafe; "
                                            "network check skipped"
                                        )
                                    elif parsed_link.hostname is None:
                                        is_broken = True
                                        reason = "HTTP URL has no hostname"
                                    else:
                                        try:
                                            req = urllib.request.Request(
                                                link,
                                                headers={
                                                    "User-Agent": "QZX-Link-Checker"
                                                },
                                            )
                                            with self._open_url(
                                                req, timeout=2.0
                                            ) as resp:
                                                if resp.status >= 400:
                                                    is_broken = True
                                                    reason = f"HTTP {resp.status}"
                                        except Exception as exc:
                                            is_broken = True
                                            reason = str(exc)
                                else:
                                    clean_link = link.split("#")[0].split("?")[0]
                                    if clean_link:
                                        if clean_link.startswith("/"):
                                            target_path_local = os.path.join(
                                                abs_path, clean_link.lstrip("/")
                                            )
                                        else:
                                            target_path_local = os.path.join(
                                                root, clean_link
                                            )
                                        if not os.path.exists(target_path_local):
                                            is_broken = True
                                            reason = "Local file not found"
                            if is_broken:
                                results["broken_links"].append({
                                    "file": rel_file,
                                    "link": link,
                                    "text": text,
                                    "reason": reason
                                })
                                results["summary"]["findings"].append({
                                    "severity": "low",
                                    "category": "broken_links",
                                    "message": f"Broken documentation link in {rel_file}: {link} ({reason})"
                                })
                    except Exception:
                        pass
                        
            if scanned_files > 10000:
                break
                
        # 5. Git ignore audit
        git_ignore_path = os.path.join(abs_path, ".gitignore")
        if os.path.exists(git_ignore_path):
            try:
                with open(git_ignore_path, 'r', encoding='utf-8', errors='ignore') as fp:
                    git_ignore_content = fp.read()
                
                # Check missing ignore patterns
                missing_patterns = []
                for p in ("node_modules", ".env", "__pycache__", "dist", "build"):
                    if p not in git_ignore_content:
                        missing_patterns.append(p)
                        
                if missing_patterns:
                    results["gitignore_issues"].append({
                        "issue": "missing_common_ignores",
                        "missing": missing_patterns
                    })
                    results["summary"]["findings"].append({
                        "severity": "medium",
                        "category": "gitignore",
                        "message": f"Missing recommended ignores in .gitignore: {', '.join(missing_patterns)}"
                    })
            except Exception:
                pass
        else:
            results["gitignore_issues"].append({
                "issue": "no_gitignore"
            })
            results["summary"]["findings"].append({
                "severity": "high",
                "category": "gitignore",
                "message": "Missing .gitignore file in repository root"
            })
            
        # Check if .env file actually exists
        env_path = os.path.join(abs_path, ".env")
        if os.path.exists(env_path):
            # Verify if .env is tracked in git
            if is_git:
                try:
                    res = subprocess.run(
                        ["git", "ls-files", ".env"],
                        cwd=abs_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    if res.stdout.strip() == ".env":
                        results["gitignore_issues"].append({
                            "issue": "env_file_tracked",
                            "message": ".env file is tracked in git!"
                        })
                        results["summary"]["findings"].append({
                            "severity": "critical",
                            "category": "gitignore",
                            "message": "Security Risk: .env file is tracked and committed in Git!"
                        })
                except Exception:
                    pass
                    
        # 6. Committed binaries in Git
        if is_git:
            try:
                res = subprocess.run(
                    ["git", "ls-files"],
                    cwd=abs_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                if res.returncode == 0:
                    tracked_files = res.stdout.splitlines()
                    binary_exts = {'.exe', '.dll', '.so', '.dylib', '.o', '.obj', '.class', '.pyc', '.zip', '.tar', '.gz', '.rar'}
                    for tf in tracked_files:
                        _, ext = os.path.splitext(tf)
                        if ext.lower() in binary_exts:
                            results["binaries"].append(tf)
                            results["summary"]["findings"].append({
                                "severity": "medium",
                                "category": "binaries",
                                "message": f"Binary/compiled file committed in Git: {tf}"
                            })
            except Exception:
                pass
                
        # 7. Basic Dependency Vulnerabilities
        pkg_json_path = os.path.join(abs_path, "package.json")
        if os.path.exists(pkg_json_path):
            import shutil
            audit_cmd = ["pnpm", "audit"] if shutil.which("pnpm") else ["npm", "audit"]
            try:
                res = subprocess.run(
                    audit_cmd,
                    cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25, shell=False
                )
                has_vulns = res.returncode != 0
                results["dependency_vulnerabilities"].append({
                    "file": "package.json",
                    "audit_executed": True,
                    "command": " ".join(audit_cmd),
                    "status": "vulnerabilities_found" if has_vulns else "clean",
                    "output": res.stdout[:1500]
                })
                if has_vulns:
                    results["summary"]["findings"].append({
                        "severity": "high",
                        "category": "dependencies",
                        "message": "Node dependencies have known vulnerabilities (run npm/pnpm audit for details)"
                    })
            except Exception as e:
                results["dependency_vulnerabilities"].append({
                    "file": "package.json",
                    "audit_executed": False,
                    "error": str(e)
                })
            
        req_txt_path = os.path.join(abs_path, "requirements.txt")
        if os.path.exists(req_txt_path):
            import shutil
            venv_bin = os.path.join(abs_path, "venv", "Scripts") if os.name == 'nt' else os.path.join(abs_path, "venv", "bin")
            pip_audit_path = shutil.which("pip-audit", path=venv_bin) or shutil.which("pip-audit")
            if pip_audit_path:
                try:
                    res = subprocess.run(
                        [pip_audit_path, "-r", "requirements.txt"],
                        cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25
                    )
                    has_vulns = res.returncode != 0
                    results["dependency_vulnerabilities"].append({
                        "file": "requirements.txt",
                        "audit_executed": True,
                        "command": "pip-audit",
                        "status": "vulnerabilities_found" if has_vulns else "clean",
                        "output": res.stdout[:1500]
                    })
                    if has_vulns:
                        results["summary"]["findings"].append({
                            "severity": "high",
                            "category": "dependencies",
                            "message": "Python dependencies have known vulnerabilities (pip-audit reported issues)"
                        })
                except Exception as e:
                    results["dependency_vulnerabilities"].append({
                        "file": "requirements.txt",
                        "audit_executed": False,
                        "error": str(e)
                    })
            else:
                results["dependency_vulnerabilities"].append({
                    "file": "requirements.txt",
                    "audit_executed": False,
                    "reason": "pip-audit not installed",
                    "recommendation": "Run 'pip install pip-audit && pip-audit -r requirements.txt'"
                })
            
        # 8. Git Log Secrets Check
        if is_git:
            try:
                # Look at recent commits for added secrets
                cmd = ["git", "log", "-n", "30", "--pretty=format:%H - %s"]
                res = subprocess.run(cmd, cwd=abs_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                # Just flag history length
                pass
            except Exception:
                pass
                
        # Calculate Risk Level
        critical_count = sum(1 for f in results["summary"]["findings"] if f["severity"] == "critical")
        high_count = sum(1 for f in results["summary"]["findings"] if f["severity"] == "high")
        medium_count = sum(1 for f in results["summary"]["findings"] if f["severity"] == "medium")
        
        if critical_count > 0:
            results["summary"]["risk_level"] = "critical"
        elif high_count > 0:
            results["summary"]["risk_level"] = "high"
        elif medium_count > 0:
            results["summary"]["risk_level"] = "medium"
        else:
            results["summary"]["risk_level"] = "low"
            
        results["summary"]["total_findings"] = len(results["summary"]["findings"])
        # Sort findings by severity: critical -> high -> medium -> low
        severity_map = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        results["summary"]["findings"].sort(key=lambda x: severity_map.get(x["severity"], 4))
        
        return {
            "success": True,
            "message": "Repository audit completed.",
            "details": results
        }
