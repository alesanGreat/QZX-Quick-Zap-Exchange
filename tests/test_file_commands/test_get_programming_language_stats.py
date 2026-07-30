from qzx.commands.file.get_programming_language_stats import (
    GetProgrammingLanguageStatsFromFileCommand,
)


class FailingProgrammingLanguageStatsCommand(
    GetProgrammingLanguageStatsFromFileCommand
):
    """Deterministic file-analysis boundary for aggregate failure behavior."""

    def _analyze_file(self, file_path, detailed=False, language_data=None):
        return {
            "success": False,
            "file_path": file_path,
            "error": "deterministic read failure",
        }


def test_real_python_file_uses_consistent_aggregate_fields(tmp_path):
    source = tmp_path / "example.py"
    source.write_text(
        "def greet(name):\n    # Friendly greeting\n    return f'Hi {name}'\n",
        encoding="utf-8",
    )

    result = GetProgrammingLanguageStatsFromFileCommand().execute(str(source))

    assert result["success"] is True
    assert result["files_found"] == 1
    assert result["files_analyzed"] == 1
    assert result["files_failed"] == 0
    assert result["language_counts"] == {"Python": 1}
    assert result["aggregated_stats"]["total_lines"] == 3
    file_result = result["file_results"][str(source)]
    assert file_result["language"] == file_result["detected_language"]
    assert file_result["total_lines"] == file_result["line_count"]
    assert file_result["blank_lines"] == file_result["empty_lines"]


def test_all_file_failures_make_the_command_fail(tmp_path):
    source = tmp_path / "example.py"
    source.write_text("x = 1\n", encoding="utf-8")

    result = FailingProgrammingLanguageStatsCommand().execute(str(source))

    assert result["success"] is False
    assert result["error_code"] == "file_analysis_failed"
    assert result["files_found"] == 1
    assert result["files_analyzed"] == 0
    assert result["files_failed"] == 1
    assert "deterministic read failure" in result["file_results"][
        str(source)
    ]["error"]


def test_dictionary_fallback_is_structured_and_keeps_stdout_clean(
    tmp_path, capsys
):
    source = tmp_path / "example.py"
    source.write_text("answer = 42\n", encoding="utf-8")
    command = GetProgrammingLanguageStatsFromFileCommand()
    command.LANGUAGES_DIR = tmp_path / "missing-language-dictionaries"

    result = command.execute(str(source))

    assert capsys.readouterr().out == ""
    assert result["success"] is True
    assert result["warnings"]
    assert str(command.LANGUAGES_DIR) in result["warnings"][0]
