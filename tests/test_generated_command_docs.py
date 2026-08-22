from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from scripts import generate_command_docs as generator

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = REPOSITORY_ROOT / "docs" / "reference" / "commands-generated.md"
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "generate_command_docs.py"


def test_generated_command_reference_matches_public_metadata():
    reference = REFERENCE_PATH.read_text(encoding="utf-8")

    assert reference == generator.generate_reference()
    assert "Generated on:" not in reference
    assert "scripts/generate_command_docs.py" in reference
    assert "### listStartupPrograms" in reference
    assert "### getStartupPrograms" not in reference
    assert "`qzx terminal`" in reference
    assert "`qzx welcome`" in reference


def test_check_mode_is_read_only_and_succeeds_for_current_reference():
    before = REFERENCE_PATH.read_bytes()
    before_mtime = REFERENCE_PATH.stat().st_mtime_ns
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    process = subprocess.run(
        [sys.executable, "-B", str(SCRIPT_PATH), "--check"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert process.returncode == 0, process.stderr
    assert "up to date" in process.stdout
    assert REFERENCE_PATH.read_bytes() == before
    assert REFERENCE_PATH.stat().st_mtime_ns == before_mtime


def test_atomic_writer_is_a_noop_for_identical_content(tmp_path):
    output = tmp_path / "reference.md"

    assert generator.write_if_changed(output, "stable\n") is True
    first_mtime = output.stat().st_mtime_ns
    assert generator.write_if_changed(output, "stable\n") is False

    assert output.read_bytes() == b"stable\n"
    assert output.stat().st_mtime_ns == first_mtime
    assert list(tmp_path.glob("*.tmp")) == []
