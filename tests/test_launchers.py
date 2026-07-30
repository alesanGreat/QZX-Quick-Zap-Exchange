"""Integration checks for the repository-local QZX launchers."""

import json
import os
from pathlib import Path
import subprocess

from qzx import __version__


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _launcher_command():
    if os.name == "nt":
        return ["cmd.exe", "/d", "/c", str(REPOSITORY_ROOT / "qzx.bat")]
    return [str(REPOSITORY_ROOT / "qzx.sh")]


def test_local_launcher_emits_parseable_json_from_checkout():
    """The documented local launcher must preserve the JSON-only contract."""
    completed = subprocess.run(
        [*_launcher_command(), "version", "--json"],
        cwd=REPOSITORY_ROOT,
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


def test_windows_launcher_finds_uv_python_when_path_has_no_python(tmp_path):
    """qzx.bat must recover the installed uv interpreter after a PATH reset."""
    if os.name != "nt":
        assert (REPOSITORY_ROOT / "qzx.bat").is_file()
        assert (REPOSITORY_ROOT / "qzx.sh").is_file()
        return

    environment = os.environ.copy()
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
