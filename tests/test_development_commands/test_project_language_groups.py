"""Real filesystem contracts for one-pass, fully accounted project groups."""

import pytest

from qzx.commands.development import _project_language_command as workflow
from qzx.commands.development import _project_language_native as native
from qzx.commands.development import _project_language_scan as portable
from qzx.commands.development.project_languages import ProjectLanguagesCommand


def _project(root):
    root.mkdir()
    (root / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    (root / "app.py").write_text("# note\nprint('source')\n\n", encoding="utf-8")
    (root / "ignored.py").write_text("print('ignored')\n", encoding="utf-8")
    (root / "data.json").write_text('{"ok": true}\n', encoding="utf-8")
    (root / "mystery.unknown_qzx").write_text("plain content\n", encoding="utf-8")
    (root / "generated.js").write_text(
        "// @generated\nconst a = 1;\n",
        encoding="utf-8",
    )
    (root / "binary.py").write_bytes(b"\x00\x01\x02")
    return root


def _always_native():
    return True


def test_grouped_scan_rejects_missing_and_empty_targets(tmp_path):
    command = ProjectLanguagesCommand()
    with pytest.raises(ValueError, match="does not exist"):
        native.scan_native_groups(command, [[tmp_path / "missing"]])
    with pytest.raises(ValueError, match="at least one target"):
        native.scan_native_groups(command, [[]])
    assert native.scan_native_groups(command, []) == []


def test_native_failure_retains_full_python_fallback(tmp_path):
    (tmp_path / "app.py").write_text(
        "# note\nprint('still works')\n",
        encoding="utf-8",
    )

    def failed_native(*args):
        raise OSError("deliberate native I/O failure")

    command = ProjectLanguagesCommand()
    result = workflow.execute_project_languages(
        command,
        str(tmp_path),
        portable.LANGUAGE_DEPENDENCY_ERROR,
        portable.pygments,
        portable.pathspec,
        native_available_func=_always_native,
        scan_native_func=failed_native,
    )
    assert result["scan_complete"] is True
    assert result["analysis_engine"]["native"] is False
    assert result["languages_found"] == {"Python": 1}
    assert result["languages"][0]["code_lines"] == 1
    assert result["languages"][0]["comment_lines"] == 1


def test_metadata_uses_directory_entry_symlink_status(tmp_path):
    class SymlinkEntry:
        @staticmethod
        def is_symlink():
            return True

    command = ProjectLanguagesCommand()
    state = workflow._state()
    included = set()
    native._handle_metadata_file(
        command,
        tmp_path / "alias.py",
        [],
        tmp_path,
        state,
        {},
        included,
        entry=SymlinkEntry(),
    )
    assert state["counters"]["symlinks_skipped"] == 1
    assert included == set()


def test_native_inaccurate_flag_is_rejected_before_accounting():
    payload = {
        "engine": "Tokei",
        "files": [],
        "inaccurate_languages": ["Python"],
    }
    with pytest.raises(RuntimeError, match="incomplete language statistics"):
        native._native_maps(payload)


if native.native_available():

    class TestNativeProjectLanguageGroups:
        def test_grouped_scan_matches_complete_separate_scans(self, tmp_path):
            command = ProjectLanguagesCommand()
            roots = [_project(tmp_path / "web"), _project(tmp_path / "desktop")]
            grouped = native.scan_native_groups(command, [[root] for root in roots])
            separate = [
                native.scan_native_batch_result(command, [root])
                for root in roots
            ]
            for actual, expected in zip(grouped, separate, strict=True):
                for field in (
                    "scan_complete",
                    "summary",
                    "languages",
                    "supporting_formats",
                    "exclusions",
                    "unclassified",
                    "scan_errors",
                    "analysis_engine",
                ):
                    assert actual[field] == expected[field], field
                assert actual["summary"]["ignored_files"] == 1
                assert actual["summary"]["generated_files"] == 1
                assert actual["summary"]["binary_files"] == 1
                assert actual["unclassified"]["file_count"] >= 1

        def test_grouped_scan_calls_real_native_parser_once(self, tmp_path):
            command = ProjectLanguagesCommand()
            roots = [_project(tmp_path / "first"), _project(tmp_path / "second")]
            calls = []

            def measured(current_command, targets):
                calls.append(tuple(targets))
                return native._native_payload(current_command, targets)

            results = native.scan_native_groups(
                command,
                [[root] for root in roots],
                payload_loader=measured,
            )
            assert len(calls) == 1
            assert len(calls[0]) == 2
            assert all(result["scan_complete"] for result in results)

        def test_scan_errors_are_not_hidden_or_leaked_between_groups(self, tmp_path):
            command = ProjectLanguagesCommand()
            bad = _project(tmp_path / "bad")
            good = _project(tmp_path / "good")
            (bad / ".ignore").write_bytes(b"\xff")
            results = native.scan_native_groups(command, [[bad], [good]])
            assert results[0]["scan_complete"] is False
            assert results[0]["summary"]["scan_error_count"] == 1
            assert results[0]["scan_errors"][0]["path"] == ".ignore"
            assert results[1]["scan_complete"] is True
            assert results[1]["scan_errors"] == []

        def test_same_size_and_mtime_edits_are_reanalysed(self, tmp_path):
            import os

            command = ProjectLanguagesCommand()
            source = tmp_path / "app.py"
            source.write_bytes(b"a=1\n# x\n")
            before_stat = source.stat()
            first = native.scan_native_groups(command, [[tmp_path]])[0]
            source.write_bytes(b"a=1\nb=2\n")
            os.utime(
                source,
                ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns),
            )
            second = native.scan_native_groups(command, [[tmp_path]])[0]
            assert source.stat().st_size == before_stat.st_size
            assert source.stat().st_mtime_ns == before_stat.st_mtime_ns
            assert first["languages"][0]["code_lines"] == 1
            assert second["languages"][0]["code_lines"] == 2

        def test_added_and_deleted_files_are_seen_on_next_scan(self, tmp_path):
            command = ProjectLanguagesCommand()
            first = tmp_path / "first.py"
            second = tmp_path / "second.cpp"
            first.write_text("print(1)\n", encoding="utf-8")
            assert native.scan_native_groups(command, [[tmp_path]])[0]["total_files"] == 1
            second.write_text("int main() {}\n", encoding="utf-8")
            assert native.scan_native_groups(command, [[tmp_path]])[0]["total_files"] == 2
            first.unlink()
            result = native.scan_native_groups(command, [[tmp_path]])[0]
            assert result["total_files"] == 1
            assert "Python" not in result["languages_found"]
