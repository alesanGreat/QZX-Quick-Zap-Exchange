"""Repository-audit phases with bounded filesystem and network work."""

import hashlib
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request

IGNORED_DIRECTORIES = {
    ".git", "node_modules", "dist", "build", ".pytest_cache", "__pycache__",
    ".dropbox", ".dropbox.cache", "artifacts",
}
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".php", ".cpp", ".h", ".c",
    ".json", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".txt",
    ".md", ".html", ".css", ".sh", ".bat",
}
BINARY_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".o", ".obj", ".class", ".pyc",
    ".zip", ".tar", ".gz", ".rar",
}
LOCKFILES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "composer.lock", "Cargo.lock"}
SECRET_PATTERNS = (
    (re.compile(r"(?i)(api_key|apikey|secret|password|passwd|private_key|token)\s*[:=]\s*['\"]([a-zA-Z0-9_\-.=+/]{8,})['\"]"), "Potential hardcoded credentials/key"),
    (re.compile(r"AIzaSy[a-zA-Z0-9_-]{33}"), "Google API Key"),
    (re.compile(r"amzn\.mws\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"), "Amazon MWS Auth Token"),
    (re.compile(r"-----\s*BEGIN[ A-Z0-9_-]*PRIVATE KEY\s*-----"), "Private Key block"),
)


def _new_results():
    return {
        "secrets": [], "large_files": [], "duplicates": [], "broken_links": [],
        "binaries": [], "gitignore_issues": [], "license": "missing",
        "dependency_vulnerabilities": [],
        "summary": {"risk_level": "low", "total_findings": 0, "findings": []},
    }


def _finding(results, severity, category, message):
    results["summary"]["findings"].append(
        {"severity": severity, "category": category, "message": message}
    )


def _git_repository(path):
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"], cwd=path,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except Exception:
        return False


def _audit_license(path, results):
    candidates = {"license", "license.txt", "license.md", "copying", "copying.txt"}
    for filename in os.listdir(path):
        if filename.lower() in candidates:
            results["license"] = filename
            return
    _finding(results, "medium", "license", "No LICENSE file found in repository root")


def _audit_symlink(path, root, relative, results):
    target = os.readlink(path)
    absolute = os.path.join(root, target) if not os.path.isabs(target) else target
    if not os.path.exists(absolute):
        results["broken_links"].append({"link": relative, "target": target})
        _finding(results, "low", "broken_links", f"Broken symbolic link: {relative} -> {target}")


def _hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _audit_size_and_duplicate(path, relative, size, hashes, results):
    if size > 500 * 1024:
        results["large_files"].append({"path": relative, "size_bytes": size})
        _finding(results, "low", "large_files", f"Large file in repository ({size // 1024} KB): {relative}")
    if size >= 5 * 1024 * 1024:
        return
    try:
        digest = _hash_file(path)
        original = hashes.get(digest)
        if original is None:
            hashes[digest] = relative
            return
        results["duplicates"].append({"file": relative, "duplicate_of": original, "size_bytes": size})
        _finding(results, "low", "duplicates", f"Duplicate file content: {relative} is identical to {original}")
    except Exception:
        pass


def _redacted_context(line, match):
    value_group = 2 if match.lastindex and match.lastindex >= 2 else 0
    start = match.start(value_group)
    end = match.end(value_group)
    return (line[:start] + "<redacted>" + line[end:]).strip()[:100]


def _audit_secrets(path, relative, size, results):
    if size >= 1024 * 1024 or os.path.basename(path) in LOCKFILES:
        return
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for line_number, line in enumerate(handle, 1):
                for pattern, description in SECRET_PATTERNS:
                    match = pattern.search(line)
                    if not match:
                        continue
                    value = match.group(2) if match.lastindex and match.lastindex >= 2 else match.group(0)
                    if any(word in value.lower() for word in ("your_", "placeholder", "mock", "my_", "test_", "foo", "bar", "example")):
                        continue
                    results["secrets"].append({"file": relative, "line": line_number, "type": description, "context": _redacted_context(line, match)})
                    _finding(results, "critical", "secrets", f"Hardcoded secret ({description}) found in {relative} at line {line_number}")
    except Exception:
        pass


def _local_link_path(link, root, repository):
    clean = link.split("#")[0].split("?")[0]
    if not clean:
        return None
    return os.path.join(repository, clean.lstrip("/")) if clean.startswith("/") else os.path.join(root, clean)


def _inspect_http_link(command, link, parsed):
    if command._is_documentation_placeholder_url(parsed):
        return False, ""
    if parsed.username is not None or parsed.password is not None:
        return True, "Embedded URL credentials are unsafe; network check skipped"
    if parsed.hostname is None:
        return True, "HTTP URL has no hostname"
    try:
        request = urllib.request.Request(link, headers={"User-Agent": "QZX-Link-Checker"})
        with command._open_url(request, timeout=2.0) as response:
            return (True, f"HTTP {response.status}") if response.status >= 400 else (False, "")
    except Exception as exc:
        return True, str(exc)


def _inspect_link(command, link, root, repository):
    if link.startswith("#"):
        return False, ""
    try:
        parsed = urllib.parse.urlsplit(link)
    except ValueError as exc:
        return True, f"Invalid URL: {exc}"
    scheme = parsed.scheme.casefold()
    if scheme in {"irc", "ircs", "mailto", "sms", "tel", "xmpp"}:
        return False, ""
    if scheme in {"http", "https"}:
        return _inspect_http_link(command, link, parsed)
    target = _local_link_path(link, root, repository)
    return (True, "Local file not found") if target and not os.path.exists(target) else (False, "")


def _audit_markdown_links(command, path, root, relative, repository, results):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", handle.read())
        for text, link in links:
            broken, reason = _inspect_link(command, link, root, repository)
            if broken:
                results["broken_links"].append({"file": relative, "link": link, "text": text, "reason": reason})
                _finding(results, "low", "broken_links", f"Broken documentation link in {relative}: {link} ({reason})")
    except Exception:
        pass


def _audit_file(command, path, root, repository, hashes, results):
    relative = os.path.relpath(path, repository)
    if os.path.islink(path):
        _audit_symlink(path, root, relative, results)
        return
    try:
        size = os.path.getsize(path)
    except Exception:
        return
    _audit_size_and_duplicate(path, relative, size, hashes, results)
    extension = os.path.splitext(path)[1].lower()
    if extension in TEXT_EXTENSIONS:
        _audit_secrets(path, relative, size, results)
    if extension == ".md" and size < 500 * 1024:
        _audit_markdown_links(command, path, root, relative, repository, results)


def _audit_files(command, repository, results):
    scanned, hashes = 0, {}
    for root, directories, files in os.walk(repository):
        directories[:] = [name for name in directories if name not in IGNORED_DIRECTORIES]
        for filename in files:
            scanned += 1
            if scanned > 10_000:
                break
            _audit_file(command, os.path.join(root, filename), root, repository, hashes, results)
        if scanned > 10_000:
            break


def _audit_gitignore(repository, is_git, results):
    path = os.path.join(repository, ".gitignore")
    if not os.path.exists(path):
        results["gitignore_issues"].append({"issue": "no_gitignore"})
        _finding(results, "high", "gitignore", "Missing .gitignore file in repository root")
    else:
        try:
            content = open(path, "r", encoding="utf-8", errors="ignore").read()
            missing = [pattern for pattern in ("node_modules", ".env", "__pycache__", "dist", "build") if pattern not in content]
            if missing:
                results["gitignore_issues"].append({"issue": "missing_common_ignores", "missing": missing})
                _finding(results, "medium", "gitignore", f"Missing recommended ignores in .gitignore: {', '.join(missing)}")
        except Exception:
            pass
    _audit_tracked_env(repository, is_git, results)


def _audit_tracked_env(repository, is_git, results):
    if not is_git or not os.path.exists(os.path.join(repository, ".env")):
        return
    try:
        result = subprocess.run(["git", "ls-files", ".env"], cwd=repository, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if result.stdout.strip() == ".env":
            results["gitignore_issues"].append({"issue": "env_file_tracked", "message": ".env file is tracked in git!"})
            _finding(results, "critical", "gitignore", "Security Risk: .env file is tracked and committed in Git!")
    except Exception:
        pass


def _audit_binaries(repository, is_git, results):
    if not is_git:
        return
    try:
        tracked = subprocess.run(["git", "ls-files"], cwd=repository, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if tracked.returncode != 0:
            return
        for path in tracked.stdout.splitlines():
            if os.path.splitext(path)[1].lower() in BINARY_EXTENSIONS:
                results["binaries"].append(path)
                _finding(results, "medium", "binaries", f"Binary/compiled file committed in Git: {path}")
    except Exception:
        pass


def _dependency_result(results, filename, command, process):
    vulnerable = process.returncode != 0
    results["dependency_vulnerabilities"].append({
        "file": filename, "audit_executed": True, "command": command,
        "status": "vulnerabilities_found" if vulnerable else "clean",
        "output": process.stdout[:1500],
    })
    if vulnerable:
        ecosystem = "Node" if filename == "package.json" else "Python"
        _finding(results, "high", "dependencies", f"{ecosystem} dependencies have known vulnerabilities ({command} reported issues)")


def _audit_dependencies(repository, results):
    package = os.path.join(repository, "package.json")
    if os.path.exists(package):
        argv = ["pnpm", "audit"] if shutil.which("pnpm") else ["npm", "audit"]
        try:
            process = subprocess.run(argv, cwd=repository, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25, shell=False)
            _dependency_result(results, "package.json", " ".join(argv), process)
        except Exception as exc:
            results["dependency_vulnerabilities"].append({"file": "package.json", "audit_executed": False, "error": str(exc)})
    _audit_python_dependencies(repository, results)


def _audit_python_dependencies(repository, results):
    requirements = os.path.join(repository, "requirements.txt")
    if not os.path.exists(requirements):
        return
    binary_dir = os.path.join(repository, "venv", "Scripts" if os.name == "nt" else "bin")
    executable = shutil.which("pip-audit", path=binary_dir) or shutil.which("pip-audit")
    if not executable:
        results["dependency_vulnerabilities"].append({"file": "requirements.txt", "audit_executed": False, "reason": "pip-audit not installed", "recommendation": "Run 'pip install pip-audit && pip-audit -r requirements.txt'"})
        return
    try:
        process = subprocess.run([executable, "-r", "requirements.txt"], cwd=repository, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25)
        _dependency_result(results, "requirements.txt", "pip-audit", process)
    except Exception as exc:
        results["dependency_vulnerabilities"].append({"file": "requirements.txt", "audit_executed": False, "error": str(exc)})


def _finalize(results):
    findings = results["summary"]["findings"]
    counts = {severity: sum(item["severity"] == severity for item in findings) for severity in ("critical", "high", "medium")}
    results["summary"]["risk_level"] = next((severity for severity in ("critical", "high", "medium") if counts[severity]), "low")
    results["summary"]["total_findings"] = len(findings)
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda item: order.get(item["severity"], 4))


def execute_repository_audit(command, path="."):
    """Run every bounded audit phase and return the stable public contract."""
    repository = os.path.abspath(path)
    if not os.path.exists(repository):
        message = f"Path '{path}' does not exist."
        return {"success": False, "error": message, "message": message}
    is_git = _git_repository(repository)
    results = _new_results()
    _audit_license(repository, results)
    _audit_files(command, repository, results)
    _audit_gitignore(repository, is_git, results)
    _audit_binaries(repository, is_git, results)
    _audit_dependencies(repository, results)
    _finalize(results)
    return {"success": True, "message": "Repository audit completed.", "details": results}
