#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Behavioral tests for the narrow QZX version/identity command."""

from qzx import __version__
from qzx.commands.system.version import VersionCommand
from qzx.identity import product_identity


def test_execute_reports_only_stable_qzx_identity():
    result = VersionCommand().execute()
    identity = product_identity()

    assert result == {
        "success": True,
        "message": f"QZX {__version__} — Quick Zap Exchange.",
        "version": __version__,
        "attribution": identity["attribution"],
        "license": identity["license"],
    }
    assert "system_info" not in result
    assert "qzx_info" not in result
