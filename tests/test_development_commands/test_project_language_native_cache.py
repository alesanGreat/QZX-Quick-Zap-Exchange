"""Native provisioning and aggregation must not trade accuracy for speed."""

import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

from qzx.commands.development import _project_language_native as native
from qzx.commands.development.project_languages import ProjectLanguagesCommand


def _source_fingerprint():
    fingerprint = native._source_native_fingerprint()
    assert fingerprint is not None
    return fingerprint


def test_native_import_does_not_eagerly_load_pygments():
    repository = Path(__file__).resolve().parents[2]
    code = (
        "import sys; "
        "import qzx.commands.development.project_languages; "
        "print('pygments' in sys.modules)"
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "False"


def test_native_payload_prefers_structured_pyo3_api(tmp_path):
    expected = {
        "engine": "Tokei",
        "engine_version": "15.0.0",
        "files": [],
        "inaccurate_languages": [],
    }

    class StructuredNative:
        @staticmethod
        def scan_project(path, excluded, max_bytes):
            assert path == str(tmp_path.resolve())
            assert excluded
            assert max_bytes > 0
            return expected

        @staticmethod
        def scan_project_json(*_args):
            raise AssertionError("legacy JSON path should not run")

    payload = native._native_payload(
        ProjectLanguagesCommand(),
        [tmp_path],
        native_module=StructuredNative(),
    )

    assert payload is expected


def test_native_payload_falls_back_to_legacy_json_api(tmp_path):
    expected = {
        "engine": "Tokei",
        "engine_version": "15.0.0",
        "files": [],
        "inaccurate_languages": [],
    }

    class LegacyNative:
        @staticmethod
        def scan_project_json(_path, _excluded, _max_bytes):
            import json

            return json.dumps(expected)

    assert native._native_payload(
        ProjectLanguagesCommand(),
        [tmp_path],
        native_module=LegacyNative(),
    ) == expected


def test_native_cache_selects_only_current_source_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setenv("QZX_NATIVE_CACHE", str(tmp_path))
    current = _source_fingerprint()
    for fingerprint in ("stale-source", current):
        root = tmp_path / "project_languages" / fingerprint
        root.mkdir(parents=True)
        (root / "_project_languages_native.pyd").write_bytes(
            b"discovery-only fixture"
        )
    assert native._native_cache_candidates() == [
        tmp_path
        / "project_languages"
        / current
        / "_project_languages_native.pyd"
    ]


def test_missing_current_build_does_not_load_stale_binary(tmp_path, monkeypatch):
    monkeypatch.setenv("QZX_NATIVE_CACHE", str(tmp_path))
    current = _source_fingerprint()
    stale = "stale-source"
    assert stale != current
    root = tmp_path / "project_languages" / stale
    root.mkdir(parents=True)
    (root / "_project_languages_native.pyd").write_bytes(b"not safe to load")
    assert native._native_cache_candidates() == []


def test_native_aggregation_only_resolves_retained_examples(tmp_path):
    class CountingCommand(ProjectLanguagesCommand):
        def __init__(self):
            self.display_calls = []

        def _relative_display(self, path, root):
            self.display_calls.append((Path(path), Path(root)))
            return Path(path).name

    command = CountingCommand()
    statistics = {}
    for index in range(25):
        record = {
            "path": str(tmp_path / f"sample{index}.py"),
            "language": "Python",
            "bytes": 10,
            "total_lines": 3,
            "code_lines": 1,
            "comment_lines": 1,
            "blank_lines": 1,
        }
        native._record_native(command, record, tmp_path, statistics)
    assert len(command.display_calls) == command.MAX_EXAMPLES_PER_GROUP
    assert statistics["Python"]["file_count"] == 25
    assert statistics["Python"]["code_lines"] == 25
    assert statistics["Python"]["example_files"] == [
        f"sample{i}.py" for i in range(5)
    ]


def _builder():
    path = Path(__file__).resolve().parents[2] / "scripts" / "build_native_project_languages.py"
    spec = importlib.util.spec_from_file_location("qzx_native_builder_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_builder_rejects_sources_changed_during_compilation():
    builder = _builder()
    current = builder.adapter._source_native_fingerprint()
    assert current
    impossible = "0" * 24 if current != "0" * 24 else "f" * 24
    with pytest.raises(RuntimeError, match="sources changed"):
        builder._assert_source_unchanged(impossible)


def test_builder_does_not_install_failed_native_smoke(tmp_path):
    builder = _builder()
    binary = tmp_path / "compiled.dll"
    binary.write_bytes(b"deliberately invalid extension")
    with pytest.raises(subprocess.CalledProcessError):
        builder._install_verified(binary, _source_fingerprint())


def test_repeated_install_keeps_identical_binary(tmp_path):
    builder = _builder()
    fingerprint = _source_fingerprint()
    suffix = importlib.machinery.EXTENSION_SUFFIXES[0]
    candidate = tmp_path / ("_project_languages_native" + suffix)
    candidate.write_bytes(b"same already-verified binary")
    cache = tmp_path / "cache"
    installed = cache / fingerprint / candidate.name
    installed.parent.mkdir(parents=True)
    installed.write_bytes(candidate.read_bytes())
    original_stat = installed.stat()

    assert builder._install_candidate(
        candidate,
        fingerprint,
        cache_root=cache,
    ) == installed
    assert installed.stat().st_mtime_ns == original_stat.st_mtime_ns
    assert installed.stat().st_ino == original_stat.st_ino
