"""Fresh content, exclusions, and fallback remain authoritative on both paths."""

import os

import pytest

from qzx.commands.development import _project_language_command as workflow
from qzx.commands.development import _project_language_native as native
from qzx.commands.development import _project_language_scan as portable
from qzx.commands.development.project_languages import ProjectLanguagesCommand


_BACKENDS = ["portable"]
if native.native_available():
    _BACKENDS.append("native")


def _never_native():
    return False


def _always_native():
    return True


def _portable_execute(command, scan_path):
    return workflow.execute_project_languages(
        command,
        scan_path,
        portable.LANGUAGE_DEPENDENCY_ERROR,
        portable.pygments,
        portable.pathspec,
        native_available_func=_never_native,
    )


@pytest.fixture(params=_BACKENDS)
def command_runner(request):
    command = ProjectLanguagesCommand()
    if request.param == "native":
        return command, command.execute

    def execute(scan_path):
        return _portable_execute(command, scan_path)

    return command, execute


def test_same_size_same_mtime_edit_is_reanalyzed(command_runner, tmp_path):
    _, execute = command_runner
    source = tmp_path / "app.py"
    source.write_bytes(b"a=1       \n")
    stamp = source.stat()
    before = execute(str(tmp_path))
    source.write_bytes(b"a=1\nb=2   \n")
    assert source.stat().st_size == stamp.st_size
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    after = execute(str(tmp_path))
    assert before["languages"][0]["code_lines"] == 1
    assert after["languages"][0]["code_lines"] == 2
    assert after["scan_complete"] is True


def test_ignore_changes_and_deletions_are_not_cached(command_runner, tmp_path):
    _, execute = command_runner
    source = tmp_path / "app.py"
    source.write_text("print(1)\n", encoding="utf-8")
    assert execute(str(tmp_path))["total_files"] == 1
    ignore = tmp_path / ".gitignore"
    ignore.write_text("app.py\n", encoding="utf-8")
    excluded = execute(str(tmp_path))
    assert excluded["total_files"] == 0
    assert excluded["summary"]["ignored_files"] == 1
    ignore.unlink()
    source.unlink()
    assert execute(str(tmp_path))["total_files"] == 0


@pytest.mark.parametrize(
    "marker",
    ["@generated", "AUTO-GENERATED", "automatically generated", "code generated - do not edit"],
)
def test_generated_marker_boundary_is_preserved(command_runner, tmp_path, marker):
    _, execute = command_runner
    source = tmp_path / "app.py"
    source.write_text(
        "# note\n" * 19 + "# " + marker + "\nprint(1)\n",
        encoding="utf-8",
    )
    assert execute(str(tmp_path))["summary"]["generated_files"] == 1
    source.write_text(
        "# note\n" * 20 + "# " + marker + "\nprint(1)\n",
        encoding="utf-8",
    )
    assert execute(str(tmp_path))["total_files"] == 1


def test_binary_precedes_generated_and_size_precedes_binary(command_runner, tmp_path):
    command, execute = command_runner
    source = tmp_path / "app.min.js"
    source.write_bytes(b"\x00// @generated\n")
    result = execute(str(tmp_path))
    assert result["summary"]["binary_files"] == 1
    assert result["summary"]["generated_files"] == 0
    command.MAX_FILE_SIZE_BYTES = 1
    result = execute(str(tmp_path))
    assert result["summary"]["oversized_files"] == 1
    assert result["summary"]["binary_files"] == 0


def test_native_failure_restarts_portable_scan_without_partial_counts(tmp_path):
    class FailedNative:
        @staticmethod
        def scan(command, target, state):
            state["counters"]["visited_files"] = 99
            raise OSError("Simulated native read failure")

    (tmp_path / "app.py").write_text("print(1)\n", encoding="utf-8")
    command = ProjectLanguagesCommand()
    result = workflow.execute_project_languages(
        command,
        str(tmp_path),
        portable.LANGUAGE_DEPENDENCY_ERROR,
        portable.pygments,
        portable.pathspec,
        native_available_func=_always_native,
        scan_native_func=FailedNative.scan,
    )
    assert result["scan_complete"] is True
    assert result["total_files"] == 1
    assert result["languages"][0]["code_lines"] == 1
    assert result["analysis_engine"]["native"] is False
