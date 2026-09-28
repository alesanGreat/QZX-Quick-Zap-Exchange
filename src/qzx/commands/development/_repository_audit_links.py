"""Markdown-link auditing for repository audits."""

from concurrent.futures import ThreadPoolExecutor
import os
import re
import urllib.parse
import urllib.request

from ._repository_audit_results import record_finding, record_scan_issue

MAX_LINK_CHECK_WORKERS = 8
MIN_PARALLEL_HTTP_LINKS = 4


def _local_link_path(link, root, repository):
    clean = link.split("#")[0].split("?")[0]
    if not clean:
        return None
    if clean.startswith("/"):
        return os.path.join(repository, clean.lstrip("/"))
    return os.path.join(root, clean)


def _inspect_http_link(command, link, parsed):
    if command._is_documentation_placeholder_url(parsed):
        return False, ""
    if parsed.username is not None or parsed.password is not None:
        return True, "Embedded URL credentials are unsafe; network check skipped"
    if parsed.hostname is None:
        return True, "HTTP URL has no hostname"
    try:
        request = urllib.request.Request(
            link,
            headers={"User-Agent": "QZX-Link-Checker"},
        )
        with command._open_url(request, timeout=2.0) as response:
            if response.status >= 400:
                return True, f"HTTP {response.status}"
            return False, ""
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
    if target and not os.path.exists(target):
        return True, "Local file not found"
    return False, ""


def _http_cache_key(link):
    return link if link.casefold().startswith(("http://", "https://")) else None


def _requires_network_fetch(command, link):
    try:
        parsed = urllib.parse.urlsplit(link)
    except ValueError:
        return False
    if parsed.scheme.casefold() not in {"http", "https"}:
        return False
    if command._is_documentation_placeholder_url(parsed):
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    return parsed.hostname is not None


def _prime_http_link_cache(command, links, root, repository, link_cache):
    pending = []
    seen = set()
    for _text, link in links:
        cache_key = _http_cache_key(link)
        if cache_key is None or cache_key in link_cache or cache_key in seen:
            continue
        seen.add(cache_key)
        pending.append(cache_key)
    if not pending:
        return

    def inspect(link):
        return _inspect_link(command, link, root, repository)

    network_checks = sum(_requires_network_fetch(command, link) for link in pending)
    if network_checks < MIN_PARALLEL_HTTP_LINKS:
        outcomes = [inspect(link) for link in pending]
    else:
        workers = min(MAX_LINK_CHECK_WORKERS, network_checks)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            outcomes = list(executor.map(inspect, pending))
    for link, outcome in zip(pending, outcomes, strict=True):
        link_cache[link] = outcome


def _record_broken_link(results, relative, text, link, reason):
    results["broken_links"].append(
        {
            "file": relative,
            "link": link,
            "text": text,
            "reason": reason,
        }
    )
    record_finding(
        results,
        "low",
        "broken_links",
        f"Broken documentation link in {relative}: {link} ({reason})",
    )


def _link_outcome(command, link, root, repository, link_cache):
    cache_key = _http_cache_key(link)
    if cache_key is not None and cache_key in link_cache:
        return link_cache[cache_key]
    outcome = _inspect_link(command, link, root, repository)
    if cache_key is not None:
        link_cache[cache_key] = outcome
    return outcome


def flush_markdown_links(command, pending_links, repository, results, link_cache):
    if not pending_links:
        return
    links = [(text, link) for _relative, text, link, _root in pending_links]
    _prime_http_link_cache(
        command,
        links,
        repository,
        repository,
        link_cache,
    )
    for relative, text, link, root in pending_links:
        broken, reason = _link_outcome(
            command,
            link,
            root,
            repository,
            link_cache,
        )
        if broken:
            _record_broken_link(results, relative, text, link, reason)
    pending_links.clear()


def audit_markdown_links(
    command,
    path,
    root,
    relative,
    repository,
    results,
    link_cache=None,
    pending_links=None,
):
    if link_cache is None:
        link_cache = {}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", handle.read())
        if pending_links is not None:
            pending_links.extend(
                (relative, text, link, root)
                for text, link in links
            )
            return
        _prime_http_link_cache(command, links, root, repository, link_cache)
        for text, link in links:
            broken, reason = _link_outcome(
                command,
                link,
                root,
                repository,
                link_cache,
            )
            if broken:
                _record_broken_link(results, relative, text, link, reason)
    except Exception as exc:
        record_scan_issue(results, relative, "scan_markdown_links", exc)
