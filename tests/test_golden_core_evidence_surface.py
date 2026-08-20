#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Keep the independent Golden Core evidence entrypoint safe and discoverable."""

from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ISSUE_FORMS = REPOSITORY_ROOT / ".github" / "ISSUE_TEMPLATE"
FORM = ISSUE_FORMS / "golden_core_evidence.yml"
GENERAL_FORM = ISSUE_FORMS / "compatibility_report.yml"
GOLDEN_CORE_DOC = REPOSITORY_ROOT / "docs" / "golden-core.md"
README = REPOSITORY_ROOT / "README.md"
CONTRIBUTING = REPOSITORY_ROOT / "CONTRIBUTING.md"
FORM_URL = (
    "https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/"
    "issues/new?template=golden_core_evidence.yml"
)
GENERAL_FORM_URL = (
    "https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/"
    "issues/new?template=compatibility_report.yml"
)
INPUT_ID_PATTERN = re.compile(r"^    id: ([A-Za-z0-9_-]+)$", re.MULTILINE)


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
    assert GENERAL_FORM_URL in golden_core
    assert GENERAL_FORM_URL in readme
    assert GENERAL_FORM_URL in contributing


def test_general_platform_evidence_form_remains_available_for_every_command():
    form = GENERAL_FORM.read_text(encoding="utf-8")

    for required_fragment in (
        "name: Platform evidence (any command)",
        "  - compatibility",
        "Successful command observation",
        "Reproducible failure or boundary result",
        "Portability counterexample",
        "This issue and every attachment are public",
        "exact Python implementation/version/build",
        "mocked output is not represented as platform evidence",
        "not a universal compatibility, certification, adoption, or maturity claim",
    ):
        assert required_fragment in form
    assert FORM_URL in form


def test_all_issue_forms_use_unique_machine_readable_input_ids():
    forms = sorted(ISSUE_FORMS.glob("*.yml"))

    assert FORM in forms
    assert GENERAL_FORM in forms
    for path in forms:
        if path.name == "config.yml":
            continue
        content = path.read_text(encoding="utf-8")
        ids = INPUT_ID_PATTERN.findall(content)
        assert ids, f"{path.name} has no machine-readable input ids"
        assert len(ids) == len(set(ids)), f"{path.name} repeats an input id"
        assert "name:" in content
        assert "description:" in content
        assert "body:" in content
