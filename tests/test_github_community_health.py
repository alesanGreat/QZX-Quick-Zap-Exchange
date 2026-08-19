#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Keep QZX's public support and private security routes unambiguous."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SECURITY = REPOSITORY_ROOT / "SECURITY.md"
SUPPORT = REPOSITORY_ROOT / ".github" / "SUPPORT.md"
ISSUE_CONFIG = REPOSITORY_ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml"
PRIVATE_REPORT_URL = (
    "https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/"
    "security/advisories/new"
)


def test_private_security_route_is_discoverable_without_losing_email_fallback():
    security = SECURITY.read_text(encoding="utf-8")
    support = SUPPORT.read_text(encoding="utf-8")
    support_words = " ".join(support.split())
    issue_config = ISSUE_CONFIG.read_text(encoding="utf-8")

    assert PRIVATE_REPORT_URL in security
    assert PRIVATE_REPORT_URL in support
    assert PRIVATE_REPORT_URL in issue_config
    assert "qzx@yumbale.com" in security
    assert "Do not open a public issue" in security
    assert "not a public issue or discussion" in support_words


def test_support_uses_one_platform_evidence_vocabulary():
    support = SUPPORT.read_text(encoding="utf-8")

    assert "## Reproducible bugs and platform evidence" in support
    assert "platform evidence report" in support
    assert "compatibility report" not in support.casefold()
