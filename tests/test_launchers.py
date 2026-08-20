"""Integration checks for the repository-local QZX launchers."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from qzx import __version__
from qzx._build_info import ATTRIBUTION


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _launcher_command():
    if os.name == "nt":
        return ["cmd.exe", "/d", "/c", str(REPOSITORY_ROOT / "qzx.bat")]
    return [str(REPOSITORY_ROOT / "qzx.sh")]


def test_local_launcher_emits_parseable_json_from_checkout():
    """The documented local launcher must preserve the JSON-only contract."""
    environment = os.environ.copy()
    environment["QZX_TELEMETRY"] = "0"
    completed = subprocess.run(
        [*_launcher_command(), "version", "--json"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert completed.stderr == ""
    payload = json.loads(completed.stdout)
    assert payload["success"] is True
    assert payload["version"] == __version__
    assert payload["meta"]["command"] == "version"


def test_local_launcher_propagates_command_not_found_exit_code():
    """Both launchers must preserve the CLI's automation-friendly status."""
    environment = os.environ.copy()
    environment["QZX_TELEMETRY"] = "0"
    completed = subprocess.run(
        [*_launcher_command(), "qzx-command-that-does-not-exist", "--json"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 127, completed.stderr or completed.stdout
    assert completed.stderr == ""
    payload = json.loads(completed.stdout)
    assert payload["success"] is False
    assert payload["error_code"] == "command_not_found"


def test_local_launcher_uses_fast_human_welcome(tmp_path):
    """The no-argument launcher should greet before loading the full CLI."""
    environment = os.environ.copy()
    environment["QZX_TELEMETRY"] = "0"
    environment["QZX_STATE_DIR"] = str(tmp_path)
    completed = subprocess.run(
        _launcher_command(),
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert completed.stderr == ""
    assert ATTRIBUTION in completed.stdout
    assert "Welcome Professor!" in completed.stdout
    assert "QZX welcome screen (basic view) displayed." in completed.stdout
    assert "Run 'qzx listCommands'" in completed.stdout
    assert "Run 'qzx terminal'" in completed.stdout


def test_local_launcher_does_not_write_bytecode_into_checkout(tmp_path):
    """Repository launchers must keep the source tree free of Python caches."""

    checkout = tmp_path / "checkout"
    shutil.copytree(
        REPOSITORY_ROOT / "src",
        checkout / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.py[co]"),
    )
    launcher_name = "qzx.bat" if os.name == "nt" else "qzx.sh"
    launcher = shutil.copy2(REPOSITORY_ROOT / launcher_name, checkout)
    environment = os.environ.copy()
    environment["QZX_PYTHON"] = sys.executable
    environment["QZX_TELEMETRY"] = "0"
    environment.pop("PYTHONDONTWRITEBYTECODE", None)
    environment.pop("PYTHONPYCACHEPREFIX", None)
    command = (
        ["cmd.exe", "/d", "/c", str(launcher)]
        if os.name == "nt"
        else [str(launcher)]
    )

    completed = subprocess.run(
        [*command, "version", "--json"],
        cwd=checkout,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert json.loads(completed.stdout)["success"] is True
    assert list(checkout.rglob("__pycache__")) == []
    assert list(checkout.rglob("*.py[co]")) == []


def test_lightweight_runtime_metadata_matches_manifest():
    """Generated startup constants must not become a second source of truth."""
    manifest = json.loads(
        (
            REPOSITORY_ROOT
            / "src"
            / "qzx"
            / "resources"
            / "product-manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert __version__ == manifest["channels"]["development"]["version"]
    assert ATTRIBUTION == manifest["product"]["attribution"]
    completed = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "scripts" / "sync_runtime_metadata.py"),
        ],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_windows_launcher_finds_managed_python_when_path_has_no_python(tmp_path):
    """qzx.bat must recover a managed Python root after a PATH reset."""
    if os.name != "nt":
        assert (REPOSITORY_ROOT / "qzx.bat").is_file()
        assert (REPOSITORY_ROOT / "qzx.sh").is_file()
        return

    environment = os.environ.copy()
    environment["QZX_TELEMETRY"] = "0"
    environment.pop("QZX_PYTHON", None)
    environment.pop("VIRTUAL_ENV", None)
    environment["pythonLocation"] = str(Path(sys.executable).parent)
    environment["PATH"] = os.pathsep.join([
        str(Path(os.environ["SystemRoot"]) / "System32"),
        str(Path(os.environ["SystemRoot"])),
    ])

    completed = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/c",
            str(REPOSITORY_ROOT / "qzx.bat"),
            "version",
            "--json",
        ],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert completed.stderr == ""
    assert json.loads(completed.stdout)["version"] == __version__


def test_windows_launcher_uses_builtin_lookup_instead_of_repeated_where():
    """The hot path must not spawn WHERE.EXE for every Python candidate."""
    launcher = (REPOSITORY_ROOT / "qzx.bat").read_text(
        encoding="utf-8",
    )

    executable_lines = [
        line.strip().upper()
        for line in launcher.splitlines()
        if line.strip() and not line.lstrip().upper().startswith("REM ")
    ]
    assert not any(line.startswith("WHERE ") for line in executable_lines)
    assert "%%~$PATH:P" in launcher.upper()
    assert "CPYTHON-3.13*-WINDOWS-*" in launcher.upper()
    assert "%PYTHONLOCATION%" in launcher.upper()
