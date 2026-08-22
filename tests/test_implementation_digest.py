#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the canonical QZX command implementation fingerprint."""

from __future__ import annotations

import copy

from qzx.core.command_loader import CommandLoader
from qzx.core.implementation_digest import (
    canonicalize_source_bytes,
    command_implementation_digest,
    command_implementation_digest_for_lifecycle,
    digest_source_paths,
    implementation_source_paths,
    load_lifecycle_digest_document,
)


def command_class(name: str):
    command = CommandLoader().get_command(name)
    assert command is not None
    return type(command)


def test_source_fingerprint_normalizes_utf8_bom_and_line_endings():
    lf = b"alpha\nbeta\n"
    crlf = b"alpha\r\nbeta\r\n"
    cr = b"alpha\rbeta\r"
    bom_crlf = b"\xef\xbb\xbf" + crlf

    expected = b"alpha\nbeta\n"
    assert canonicalize_source_bytes(lf) == expected
    assert canonicalize_source_bytes(crlf) == expected
    assert canonicalize_source_bytes(cr) == expected
    assert canonicalize_source_bytes(bom_crlf) == expected


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


def test_repository_source_digest_is_order_and_eol_independent():
    paths = [
        "src/qzx/core/implementation_digest.py",
        "src/qzx/commands/system/version.py",
    ]

    forward = digest_source_paths(paths)
    reversed_digest = digest_source_paths(list(reversed(paths)))
    duplicate_digest = digest_source_paths(paths + [paths[0]])

    assert forward.startswith("sha256:")
    assert len(forward) == 71
    assert reversed_digest == forward
    assert duplicate_digest == forward


def test_repository_source_digest_rejects_escape_and_missing_paths():
    import pytest

    with pytest.raises(ValueError, match="parent traversal"):
        digest_source_paths(["../outside.txt"])
    with pytest.raises(FileNotFoundError):
        digest_source_paths(["src/qzx/does-not-exist.py"])
