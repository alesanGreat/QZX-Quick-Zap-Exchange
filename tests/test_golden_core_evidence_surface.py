#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Keep the independent Golden Core evidence entrypoint safe and discoverable."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FORM = REPOSITORY_ROOT / ".github" / "ISSUE_TEMPLATE" / "golden_core_evidence.yml"
GOLDEN_CORE_DOC = REPOSITORY_ROOT / "docs" / "golden-core.md"
README = REPOSITORY_ROOT / "README.md"
CONTRIBUTING = REPOSITORY_ROOT / "CONTRIBUTING.md"
FORM_URL = (
    "https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/"
    "issues/new?template=golden_core_evidence.yml"
)


def test_golden_core_evidence_form_routes_real_platform_findings():
    form = FORM.read_text(encoding="utf-8")

    for required_fragment in (
        "name: Golden Core platform evidence",
        "  - golden-core",
        "  - help wanted",
        "Canonical sanitized Golden Core capture",
        "Selected-command manual reproduction",
        "Reproducible failure or boundary result",
        "Counterexample or portability limitation",
        "id: revision",
        "id: environment",
        "id: evidence",
        "id: limitations",
        "id: credit",
    ):
        assert required_fragment in form


def test_golden_core_evidence_form_requires_manual_privacy_review():
    form = FORM.read_text(encoding="utf-8")

    for required_fragment in (
        "This issue and every attachment are public",
        "automated sanitization is not a guarantee",
        "I manually reviewed the evidence",
        "private paths, remotes, personal data, proprietary content",
        "this is not a private security report",
        "I am authorized to publish this evidence",
    ):
        assert required_fragment in form


def test_golden_core_evidence_form_preserves_claim_boundaries():
    form = FORM.read_text(encoding="utf-8")

    assert "Full 40-character Git commit SHA" in form
    assert "mocked results as real platform evidence" in form
    assert "does not automatically establish universal compatibility" in form
    assert "independent adoption, certification, or Beta readiness" in form


def test_golden_core_evidence_entrypoint_is_discoverable():
    golden_core = GOLDEN_CORE_DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    contributing = CONTRIBUTING.read_text(encoding="utf-8")

    assert "### Submit independent platform evidence" in golden_core
    assert "defense in depth" in golden_core
    assert FORM_URL in golden_core
    assert FORM_URL in readme
    assert FORM_URL in contributing
