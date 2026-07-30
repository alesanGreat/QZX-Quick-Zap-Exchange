#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Compatibility tests for the deprecated bootstrapProject command."""

from qzx.commands.development.bootstrap_project import (
    BootstrapProjectCommand,
)


def test_legacy_preview_delegates_with_deprecation_metadata(tmp_path):
    result = BootstrapProjectCommand().execute(
        tmp_path,
        tech="python",
        dry_run=True,
        components="structure",
    )

    assert result["success"] is True, result
    assert result["deprecated"] is True
    assert result["replacement"] == "planProjectBootstrap"
    assert result["supported_through"] == "QZX 0.2.x"
    assert result["details"]["execution"]["files_written"] == 0
    assert not (tmp_path / "src").exists()


def test_legacy_live_mode_is_removed_without_writing(tmp_path):
    target = tmp_path / "untouched"

    result = BootstrapProjectCommand().execute(
        target,
        tech="python",
        dry_run=False,
    )

    assert result["success"] is False
    assert result["error_code"] == "unsafe_legacy_execution_removed"
    assert result["deprecated"] is True
    assert result["details"]["files_written"] == 0
    assert result["details"]["commands_run"] == 0
    assert target.exists() is False


def test_invalid_legacy_dry_run_is_rejected_without_writing(tmp_path):
    result = BootstrapProjectCommand().execute(
        tmp_path,
        tech="python",
        dry_run="perhaps",
    )

    assert result["success"] is False
    assert result["error_code"] == "invalid_dry_run"
    assert result["details"]["files_written"] == 0
    assert list(tmp_path.iterdir()) == []
