#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Keep Result Contract adoption forms aligned with supported MCP profiles."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MCP_VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "validate_mcp_result_contract.py"
PILOT_FORM = (
    REPOSITORY_ROOT / ".github" / "ISSUE_TEMPLATE" / "result_contract_pilot.yml"
)
ADOPTION_FORM = (
    REPOSITORY_ROOT / ".github" / "ISSUE_TEMPLATE" / "result_contract_adoption.yml"
)

spec = importlib.util.spec_from_file_location("qzx_mcp_validator", MCP_VALIDATOR_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)


def test_result_contract_forms_offer_every_supported_mcp_revision():
    pilot = PILOT_FORM.read_text(encoding="utf-8")
    adoption = ADOPTION_FORM.read_text(encoding="utf-8")

    for version in validator.MCP_SPECIFICATION_VERSIONS:
        assert f"MCP {version}" in pilot
        assert f"MCP {version}" in adoption


def test_pilot_form_can_route_non_mcp_and_unknown_revision_cases():
    pilot = PILOT_FORM.read_text(encoding="utf-8")

    assert "id: mcp_revision" in pilot
    assert "Not using MCP for this pilot" in pilot
    assert "Not sure yet" in pilot
