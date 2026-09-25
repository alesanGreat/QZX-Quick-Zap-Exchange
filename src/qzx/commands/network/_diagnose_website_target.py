"""Target and timeout normalization for diagnoseWebsite."""

from __future__ import annotations

import re
import urllib.parse

from qzx.commands.network._diagnose_website_results import failure

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_UNSAFE_INPUT = re.compile(r"[\s\\`\"'$&;|<>^!%()\[\]{}*]")
_SCHEME = re.compile(r"^([a-z][a-z0-9+.-]*)://", re.IGNORECASE)
_SAFE_PATH = re.compile(r"^[a-zA-Z0-9/_.~:-]*$")
_SAFE_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalize_target(target):
    """Normalize a public hostname/HTTPS URL or return the stable input error."""
    raw, error = _validated_raw_target(target)
    if error:
        return None, error
    parsed, port, error = _parsed_target(raw)
    if error:
        return None, error
    error = _validated_components(parsed, port, raw)
    if error:
        return None, error
    host, error = _normalized_host(parsed.hostname, raw)
    if error:
        return None, error
    endpoint = _endpoint(host, port, parsed.path)
    return {
        "input": raw,
        "target": endpoint,
        "host": host,
        "port": port,
        "path": parsed.path or "/",
        "url": endpoint,
    }, None


def normalize_timeout(timeout, target):
    """Normalize the bounded HTTP timeout or return the stable input error."""
    try:
        timeout_value = float(timeout)
    except (TypeError, ValueError):
        return None, failure(
            "invalid_timeout",
            f"Timeout must be a number between 0.1 and 60 seconds, received '{timeout}'.",
            target=target,
        )
    if not 0.1 <= timeout_value <= 60:
        return None, failure(
            "invalid_timeout",
            f"Timeout {timeout_value:g} is outside the supported 0.1-60 second range.",
            target=target,
        )
    return timeout_value, None


def _validated_raw_target(target):
    if not isinstance(target, str):
        return None, failure(
            "invalid_target",
            "Website target must be a domain name or HTTPS URL.",
            target=target,
        )
    raw = target.strip()
    if not raw or len(raw) > 2048:
        return None, failure(
            "invalid_target",
            "Website target must contain between 1 and 2048 characters.",
            target=raw,
        )
    if _CONTROL_CHARACTERS.search(raw) or _UNSAFE_INPUT.search(raw):
        return None, failure(
            "unsafe_target",
            "Website target contains whitespace or shell-sensitive characters that are not accepted by this workflow.",
            target=raw,
        )
    if any(character in raw for character in "?@#"):
        return None, failure(
            "private_target_component",
            "Query strings, fragments, and user-info are intentionally excluded from website diagnosis targets.",
            target=raw,
        )
    return raw, None


def _parsed_target(raw):
    scheme_match = _SCHEME.match(raw)
    if scheme_match and scheme_match.group(1).lower() != "https":
        return None, None, failure(
            "unsupported_scheme",
            "diagnoseWebsite currently accepts HTTPS targets only; omit the scheme to use HTTPS by default.",
            target=raw,
        )
    candidate = raw if scheme_match else "https://" + raw
    try:
        parsed = urllib.parse.urlsplit(candidate)
        port = parsed.port or 443
    except ValueError:
        return None, None, failure(
            "invalid_target",
            "Website target contains an invalid hostname or port.",
            target=raw,
        )
    return parsed, port, None


def _validated_components(parsed, port, raw):
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return failure(
            "invalid_target",
            "Website target must be a valid domain name or HTTPS URL.",
            target=raw,
        )
    if parsed.username or parsed.password:
        return failure(
            "private_target_component",
            "Embedded credentials are intentionally excluded from website diagnosis targets.",
            target=raw,
        )
    if parsed.query or parsed.fragment:
        return failure(
            "private_target_component",
            "Query strings and fragments are intentionally excluded from website diagnosis targets.",
            target=raw,
        )
    if not 1 <= port <= 65535:
        return failure(
            "invalid_target",
            "Website target port must be between 1 and 65535.",
            target=raw,
        )
    if not _SAFE_PATH.fullmatch(parsed.path):
        return failure(
            "unsafe_target",
            "Website path contains characters outside the shell-neutral subset supported by this workflow.",
            target=raw,
        )
    return None


def _normalized_host(hostname, raw):
    try:
        host = hostname.rstrip(".").lower().encode("idna").decode("ascii")
    except UnicodeError:
        return None, failure(
            "invalid_target",
            "Website target contains a hostname that cannot be represented as a DNS name.",
            target=raw,
        )
    labels = host.split(".")
    invalid = (
        not host
        or len(host) > 254
        or re.fullmatch(r"[0-9.]+", host)
        or re.fullmatch(r"0x[0-9a-f]+", host)
        or not all(_SAFE_LABEL.fullmatch(label) for label in labels)
    )
    if invalid:
        return None, failure(
            "invalid_target",
            "Website target must contain a valid DNS hostname rather than a numeric address.",
            target=raw,
        )
    return host, None


def _endpoint(host, port, path):
    port_suffix = "" if port == 443 else f":{port}"
    endpoint = f"https://{host}{port_suffix}"
    if path and path != "/":
        endpoint += path
    return endpoint
