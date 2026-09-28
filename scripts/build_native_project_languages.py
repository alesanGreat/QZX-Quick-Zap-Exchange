#!/usr/bin/env python3
"""Provision the source-matched native backend; never build during analysis."""

from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from qzx.commands.development import _project_language_native as adapter  # noqa: E402


SMOKE_CODE = """
import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('qzx._project_languages_native', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
source = Path(sys.argv[2])
source.write_text("# comment\\nprint('QZX')\\n\\n", encoding='utf-8')
payload = module.scan_project(str(source), [], 5242880)
legacy_payload = json.loads(module.scan_project_json(str(source), [], 5242880))
assert payload == legacy_payload
assert payload['engine'] == 'Tokei'
assert len(payload['files']) == 1
record = payload['files'][0]
assert record['language'] == 'Python'
assert (record['code_lines'], record['comment_lines'], record['blank_lines']) == (1, 1, 1)
assert record['excluded_reason'] is None
assert callable(module.scan_projects)
assert callable(module.scan_projects_json)
"""


def _process_options():
    if os.name == "nt":
        return {"creationflags": subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW}
    return {}


def _compiled_library(target_dir):
    names = {
        "win32": "_project_languages_native.dll",
        "darwin": "lib_project_languages_native.dylib",
    }
    return target_dir / "release" / names.get(sys.platform, "lib_project_languages_native.so")


def _compile(target_dir, offline):
    arguments = ["cargo", "build", "--release", "--locked", "-j", "1",
                 "--target-dir", str(target_dir)]
    if offline:
        arguments.append("--offline")
    environment = dict(os.environ, PYO3_PYTHON=sys.executable, CARGO_BUILD_JOBS="1")
    subprocess.run(arguments, cwd=PROJECT_ROOT / "native" / "project_languages",
                   env=environment, check=True, **_process_options())


def _assert_source_unchanged(fingerprint):
    if adapter._source_native_fingerprint() != fingerprint:
        raise RuntimeError("Native sources changed during provisioning; no binary was installed. Retry the build.")


def _install_candidate(candidate, fingerprint, cache_root=None):
    root = adapter._native_cache_directory() if cache_root is None else Path(cache_root)
    destination = root / fingerprint / candidate.name
    # Repeated provisioning must not replace an identical DLL in use.
    if destination.is_file() and destination.read_bytes() == candidate.read_bytes():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(destination.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        shutil.copyfile(candidate, staging)
        _assert_source_unchanged(fingerprint)
        staging.replace(destination)
    finally:
        staging.unlink(missing_ok=True)
    return destination


def _install_verified(binary, fingerprint):
    suffix = importlib.machinery.EXTENSION_SUFFIXES[0]
    with tempfile.TemporaryDirectory(prefix="qzx-native-verify-") as temporary:
        root = Path(temporary)
        candidate = root / ("_project_languages_native" + suffix)
        shutil.copyfile(binary, candidate)
        subprocess.run([sys.executable, "-P", "-B", "-c", SMOKE_CODE,
                        str(candidate), str(root / "sample.py")], check=True,
                       **_process_options())
        _assert_source_unchanged(fingerprint)
        return _install_candidate(candidate, fingerprint)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-dir", type=Path,
                        help="Reuse an existing external Cargo target directory.")
    parser.add_argument("--offline", action="store_true",
                        help="Use already provisioned Cargo dependencies without network access.")
    args = parser.parse_args(argv)
    fingerprint = adapter._source_native_fingerprint()
    if not fingerprint:
        parser.error("Run this script from a complete QZX source checkout with Cargo.lock.")
    target = (args.target_dir or adapter._native_cache_directory() / "build").expanduser().resolve()
    if target == PROJECT_ROOT or PROJECT_ROOT in target.parents:
        parser.error("Cargo outputs must remain outside the source checkout.")
    try:
        _compile(target, args.offline)
        _assert_source_unchanged(fingerprint)
        destination = _install_verified(_compiled_library(target), fingerprint)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(json.dumps({"success": False, "message": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps({"success": True, "message": "Verified native projectLanguages backend installed.",
                      "fingerprint": fingerprint, "path": str(destination),
                      "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
