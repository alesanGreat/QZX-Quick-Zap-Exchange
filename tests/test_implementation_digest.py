#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the canonical QZX command implementation fingerprint."""

from __future__ import annotations

import copy

from qzx.core.command_loader import CommandLoader
from qzx.core.implementation_digest import (
    command_implementation_digest,
    command_implementation_digest_for_lifecycle,
    implementation_source_paths,
    load_lifecycle_digest_document,
)


def command_class(name: str):
    command = CommandLoader().get_command(name)
    assert command is not None
    return type(command)


def test_implementation_digest_is_stable_and_source_scoped():
    version = command_class("version")

    digest = command_implementation_digest(version)
    paths = implementation_source_paths(version)

    assert digest.startswith("sha256:")
    assert len(digest) == 71
    assert "src/qzx/commands/system/version.py" in paths
    assert "src/qzx/core/command_loader.py" in paths
    assert "src/qzx/resources/command-lifecycle.json" in paths
    assert "src/qzx/_build_info.py" not in paths
    assert command_implementation_digest(version) == digest


def test_lifecycle_change_invalidates_only_the_semantic_fingerprint_input():
    version = command_class("version")
    lifecycle = load_lifecycle_digest_document()
    changed = copy.deepcopy(lifecycle)
    changed["commands"]["version"]["note"] = "Fingerprint regression fixture."

    original = command_implementation_digest_for_lifecycle(version, lifecycle)
    modified = command_implementation_digest_for_lifecycle(version, changed)

    assert original == command_implementation_digest(version)
    assert modified != original
