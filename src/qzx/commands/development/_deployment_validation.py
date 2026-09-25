"""Fail-closed validation for ``deployProject``."""

import os
import urllib.parse
from pathlib import Path, PurePosixPath


def failure(error_code, message, **details):
    return {"success": False, "error_code": error_code, "error": message, "message": message, "details": details}


def validate_target_path(command, value):
    raw_path = str(value).strip()
    if any(character in raw_path for character in "\r\n\0"):
        return command._failure("invalid_target_path", "target_path must not contain control characters.")
    target = PurePosixPath(raw_path)
    normalized = str(target)
    if not raw_path.startswith("/") or normalized in {"/", "."} or normalized != raw_path.rstrip("/") or ".." in target.parts:
        return command._failure("unsafe_target_path", "target_path must be a normalized absolute POSIX path below '/', such as /srv/example/current.", target_path=raw_path)
    if target.name.startswith(".qzx-"):
        return command._failure("reserved_target_path", "target_path basename must not use QZX's .qzx- prefix.", target_path=raw_path)
    return {"success": True, "path": normalized}


def validate_health_url(command, value):
    if value in {None, ""}:
        return {"success": True, "url": None}
    url = str(value).strip()
    parsed = urllib.parse.urlsplit(url)
    try:
        parsed_port = parsed.port
    except ValueError:
        parsed_port = -1
    invalid = (
        parsed.scheme not in {"http", "https"} or not parsed.hostname
        or parsed_port == -1 or parsed.username is not None
        or parsed.password is not None or bool(parsed.query) or bool(parsed.fragment)
    )
    if invalid:
        return command._failure("invalid_health_url", "health_url must be an HTTP(S) URL without embedded credentials, a query string, or a fragment.")
    return {"success": True, "url": url}


def _artifact(command, raw):
    path = Path(os.path.abspath(os.fspath(raw["path"])))
    if not path.exists():
        return None, command._failure("artifact_not_found", f"Artifact path '{path}' does not exist.", artifact_path=str(path))
    if path.is_symlink() or not path.is_dir():
        return None, command._failure("artifact_not_directory", f"Artifact path '{path}' must be a real directory, not a file or symbolic link.", artifact_path=str(path))
    return path, None


def _host_and_port(command, raw):
    host = str(raw["target_host"]).strip()
    if not host or host.startswith("-") or not command._host_pattern.fullmatch(host):
        return None, command._failure("invalid_target_host", "target_host must use a plain host or user@host value without whitespace, options, or shell syntax.", target_host=host)
    try:
        port = int(raw["port"])
    except (TypeError, ValueError):
        port = -1
    if not 1 <= port <= 65535:
        return None, command._failure("invalid_port", f"port must be between 1 and 65535; got {raw['port']!r}.")
    return (host, port), None


def _optional_file(command, value, label, error_code):
    if value in {None, ""}:
        return None, None
    path = Path(os.path.abspath(os.fspath(value)))
    if not path.is_file():
        description = "SSH key" if label == "ssh_key" else "OpenSSH known_hosts file"
        return None, command._failure(error_code, f"{description} '{path}' is not a regular file.", **{label: str(path)})
    return path, None


def _health_options(command, raw):
    health = command._validate_health_url(raw["health_url"])
    if not health["success"]:
        return None, health
    expected = str(raw["health_expect"]) if raw["health_expect"] is not None else None
    if expected is not None and len(expected) > 2_000:
        return None, command._failure("health_expect_too_large", "health_expect must not exceed 2,000 characters.", characters=len(expected))
    ranges = {
        "health_attempts": (raw["health_attempts"], int, 1, 20),
        "health_interval": (raw["health_interval"], float, 0.0, 30.0),
        "health_timeout": (raw["health_timeout"], float, 0.1, 30.0),
    }
    converted = {}
    for name, (value, converter, minimum, maximum) in ranges.items():
        try:
            parsed = converter(value)
        except (TypeError, ValueError):
            parsed = minimum - 1
        if not minimum <= parsed <= maximum:
            return None, command._failure(f"invalid_{name}", f"{name} must be between {minimum} and {maximum}; got {value!r}.")
        converted[name] = parsed
    return (health["url"], expected, converted), None


def validate_inputs(command, **raw):
    artifact, failure = _artifact(command, raw)
    if failure:
        return failure
    dry_run = command._parse_bool(raw["dry_run"])
    if dry_run is None:
        return command._failure("invalid_boolean", f"dry_run must be true or false; got {raw['dry_run']!r}.")
    host_port, failure = _host_and_port(command, raw)
    if failure:
        return failure
    target = command._validate_target_path(raw["target_path"])
    if not target["success"]:
        return target
    deployment_id = str(raw["deployment_id"]).strip() if raw["deployment_id"] is not None else command._new_deployment_id()
    if not command._deployment_id_pattern.fullmatch(deployment_id):
        return command._failure("invalid_deployment_id", "deployment_id must be 1-64 ASCII letters, digits, dots, underscores, or hyphens and must start with a letter or digit.", deployment_id=deployment_id)
    ssh_key, failure = _optional_file(command, raw["ssh_key"], "ssh_key", "ssh_key_not_found")
    if failure:
        return failure
    known_hosts, failure = _optional_file(command, raw["known_hosts"], "known_hosts", "known_hosts_not_found")
    if failure:
        return failure
    health, failure = _health_options(command, raw)
    if failure:
        return failure
    url, expected, converted = health
    host, port = host_port
    return {"success": True, "values": {
        "target_host": host, "target_path": target["path"], "artifact_path": artifact,
        "port": port, "ssh_key": ssh_key, "known_hosts": known_hosts,
        "health_url": url, "health_expect": expected,
        "health_attempts": converted["health_attempts"],
        "health_interval": converted["health_interval"],
        "health_timeout": converted["health_timeout"],
        "deployment_id": deployment_id, "dry_run": dry_run,
    }}


def validate_backup_target(command, target, values):
    validation = command._validate_inputs(
        target_host=values.get("target_host"), target_path=values.get("target_path"),
        path=target, port=values.get("port", 22), ssh_key=values.get("ssh_key"),
        known_hosts=values.get("known_hosts"), health_url=values.get("health_url"),
        health_expect=values.get("health_expect"), health_attempts=values.get("health_attempts", 5),
        health_interval=values.get("health_interval", 2.0), health_timeout=values.get("health_timeout", 5.0),
        deployment_id=values.get("deployment_id"), dry_run=False,
    )
    if not validation["success"]:
        return validation
    if not validation["values"]["health_url"]:
        return command._failure("health_url_required", "A live deployment requires health_url so QZX can verify the promoted release and roll it back automatically.")
    return None
