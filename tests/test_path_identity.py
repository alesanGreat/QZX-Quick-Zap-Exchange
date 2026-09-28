"""Canonical identities resolve aliases freshly through explicit path boundaries."""

import os
from pathlib import Path

import pytest

from qzx.core import path_identity


@pytest.mark.parametrize("name", ["source.py", "with spaces.py", "área 日本語.py"])
def test_relative_and_absolute_aliases_have_same_identity(tmp_path, monkeypatch, name):
    source = tmp_path / name
    source.write_text("pass\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert path_identity.canonical_path_key(name) == path_identity.canonical_path_key(source)
    assert path_identity.canonical_path_key(Path(".") / name) == path_identity.canonical_path_key(
        source.resolve()
    )


def test_missing_path_preserves_portable_resolution(tmp_path):
    source = tmp_path / "missing.py"
    assert path_identity.canonical_path_key(source) == os.path.normcase(
        str(source.resolve())
    )


def test_explicit_portable_boundary_uses_pathlib(tmp_path):
    assert path_identity._canonical_path_key(tmp_path, None) == os.path.normcase(
        str(tmp_path.resolve())
    )


@pytest.mark.parametrize(
    "error",
    [OSError("access unavailable"), ValueError("invalid native input")],
)
def test_native_resolution_error_preserves_portable_behavior(tmp_path, error):
    def failing_resolver(_):
        raise error

    assert path_identity._canonical_path_key(
        tmp_path,
        failing_resolver,
    ) == os.path.normcase(str(tmp_path.resolve()))


def test_existing_identity_needs_one_final_path_lookup(tmp_path):
    calls = []

    def resolver(raw):
        calls.append(raw)
        return str(tmp_path.resolve())

    assert path_identity._canonical_path_key(tmp_path, resolver)
    assert calls == [os.path.abspath(os.fspath(tmp_path))]


def test_native_resolution_is_fresh_on_every_call(tmp_path):
    first = str((tmp_path / "first").resolve())
    second = str((tmp_path / "second").resolve())
    resolutions = [first, second]

    def resolver(_):
        return resolutions.pop(0)

    before = path_identity._canonical_path_key(tmp_path / "alias", resolver)
    after = path_identity._canonical_path_key(tmp_path / "alias", resolver)
    assert before == os.path.normcase(first)
    assert after == os.path.normcase(second)
    assert before != after
    assert resolutions == []


def test_native_resolver_can_canonicalize_multiple_alias_forms(tmp_path):
    canonical = str((tmp_path / "canonical.py").resolve())

    def resolver(_):
        return canonical

    first = path_identity._canonical_path_key(tmp_path / "one.py", resolver)
    second = path_identity._canonical_path_key(tmp_path / "two.py", resolver)
    assert first == second == os.path.normcase(canonical)


def test_bytes_are_not_silently_treated_as_text_paths():
    with pytest.raises(TypeError):
        path_identity.canonical_path_key(b"not a text path")
