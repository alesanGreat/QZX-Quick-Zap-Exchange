"""Internal mixin extracted from systemDoctor without behavior changes."""

def _initial_results():
    return {
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
        "recommendations": [],
    }


def _safe_check(results, key, check):
    try:
        results[key] = check()
        return True
    except Exception as error:
        results[key] = {"error": str(error)}
        return False


def _cpu_issues(result):
    if not isinstance(result, dict):
        return []
    usage = result.get("usage_percent", 0)
    if usage > 85:
        return [("High CPU usage", f"CPU load is currently at {usage}%", "medium")]
    return []


def _ram_issues(result):
    if not isinstance(result, dict) or "virtual" not in result:
        return []
    percent = result["virtual"].get("percent", 0)
    if percent > 90:
        return [("Critical memory usage", f"RAM usage is at {percent}%", "high")]
    if percent > 75:
        return [("High memory usage", f"RAM usage is at {percent}%", "medium")]
    return []


def _disk_issues(result):
    if not isinstance(result, dict) or "partitions" not in result:
        return []
    issues = []
    for part in result["partitions"]:
        use_pct = part.get("percent", 0)
        mount = part.get("mountpoint", "")
        if use_pct > 90:
            issues.append(
                ("Critical disk space", f"Partition '{mount}' is {use_pct}% full", "high")
            )
        elif use_pct > 80:
            issues.append(
                ("Low disk space", f"Partition '{mount}' is {use_pct}% full", "medium")
            )
    return issues


def _network_issues(result):
    if isinstance(result, dict) and not result.get("dns_ok", False):
        return [
            (
                "DNS Failure",
                "Failed to resolve external domain (google.com)",
                "high",
            )
        ]
    return []


def _path_issues(result):
    if not isinstance(result, dict):
        return []
    broken = result.get("broken", [])
    if broken:
        return [
            (
                "Broken PATH entries",
                f"Found {len(broken)} non-existent directories in PATH",
                "low",
            )
        ]
    return []


def _error_issues(result):
    if isinstance(result, dict) and result.get("error_count", 0) > 0:
        return [
            (
                "System errors found",
                "Detected recent system error log events",
                "medium",
            )
        ]
    return []


def _full_checks(command, results, issues):
    _safe_check(results, "services", command._check_services)
    _safe_check(results, "ports", command._check_ports)
    _safe_check(results, "startup", command._check_startup)
    if _safe_check(results, "errors", command._check_errors):
        issues.extend(_error_issues(results["errors"]))
    if _safe_check(results, "smart", command._check_smart):
        issues.extend(command._smart_issues(results["smart"]))


class SystemDoctorCoreMixin:
    def execute(self, quick=False):
        """Execute the system diagnostic check."""
        if isinstance(quick, str):
            quick = quick.strip().lower() in ("true", "1", "yes")

        results = _initial_results()
        issues = []
        checks = (
            ("cpu", lambda: self._check_cpu(quick), _cpu_issues),
            ("ram", self._check_ram, _ram_issues),
            ("disk", lambda: self._check_disk(quick), _disk_issues),
            ("network", lambda: self._check_network(quick), _network_issues),
            ("path", self._check_path, _path_issues),
        )
        for key, check, issue_builder in checks:
            if _safe_check(results, key, check):
                issues.extend(issue_builder(results[key]))
        if not quick:
            _full_checks(self, results, issues)

        results["health_score"], results["recommendations"] = self._score_issues(issues)
        return {
            "success": True,
            "message": "System diagnostic completed successfully.",
            "details": results,
        }

    @staticmethod
    def _smart_issues(smart_result):
        """Map normalized SMART results to deterministic diagnostic issues."""
        issues = []
        if not isinstance(smart_result, dict):
            return issues
        if smart_result.get("status") != "available":
            return issues

        for drive in smart_result.get("drives", []):
            status = drive.get("health_status")
            disk_label = drive.get("disk")
            if status == "FAILED":
                issues.append(
                    (
                        "Disk SMART Failure",
                        (
                            f"Physical drive '{disk_label}' is reporting "
                            "SMART Failure status!"
                        ),
                        "high",
                    )
                )
            elif status == "WARNING":
                issues.append(
                    (
                        "Disk SMART Warning",
                        f"Physical drive '{disk_label}' has SMART health warnings!",
                        "medium",
                    )
                )
        return issues

    @staticmethod
    def _score_issues(issues):
        """Calculate the score and recommendations from normalized issues."""
        deductions = {"high": 20, "medium": 10, "low": 5}
        score = 100 - sum(
            deductions.get(severity, 0) for _title, _message, severity in issues
        )
        recommendations = [
            {
                "title": title,
                "description": message,
                "severity": severity,
            }
            for title, message, severity in issues
        ]
        return max(0, min(100, score)), recommendations
