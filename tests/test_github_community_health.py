#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Keep QZX's public support and private security routes unambiguous."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SECURITY = REPOSITORY_ROOT / "SECURITY.md"
SUPPORT = REPOSITORY_ROOT / ".github" / "SUPPORT.md"
ISSUE_CONFIG = REPOSITORY_ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml"
CODEOWNERS = REPOSITORY_ROOT / ".github" / "CODEOWNERS"
PULL_REQUEST_TEMPLATE = REPOSITORY_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
DISCUSSIONS_URL = (
    "https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/discussions"
)
SECURITY_POLICY_URL = (
    "https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/security/policy"
)
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
    assert SECURITY_POLICY_URL in support
    assert SECURITY_POLICY_URL in issue_config
    assert "security/advisories/new" not in issue_config
    assert "qzx@yumbale.com" in security
    assert "Do not open a public issue" in security
    assert "do not use a public issue or discussion" in support_words.casefold()


def test_support_uses_one_platform_evidence_vocabulary():
    support = SUPPORT.read_text(encoding="utf-8")

    assert "## Reproducible bugs and platform evidence" in support
    assert "platform evidence report" in support
    assert "compatibility report" not in support.casefold()


def test_support_and_review_routes_match_project_governance():
    support = SUPPORT.read_text(encoding="utf-8")
    issue_config = ISSUE_CONFIG.read_text(encoding="utf-8")
    codeowners = CODEOWNERS.read_text(encoding="utf-8").splitlines()
    pull_request_template = PULL_REQUEST_TEMPLATE.read_text(encoding="utf-8")

    assert DISCUSSIONS_URL in support
    assert DISCUSSIONS_URL in issue_config
    assert codeowners == [
        "# Alejandro Sánchez created and maintains QZX.",
        "* @alesanGreat",
    ]
    for required_heading in (
        "## Summary",
        "## Adoption, interoperability, or trust",
        "## Validation",
        "## Related issue",
        "## Review checklist",
    ):
        assert required_heading in pull_request_template
    assert "DCO `Signed-off-by`" in pull_request_template
    assert "blob/main/CONTRIBUTING.md" in pull_request_template
    assert "../CONTRIBUTING.md" not in pull_request_template
