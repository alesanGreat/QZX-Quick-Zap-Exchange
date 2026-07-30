"""Regression tests for the getHumanLanguageStats command."""

from qzx.commands.file.get_human_language_stats import (
    FUNCTION_WORDS_DIR,
    GetHumanLanguageStatsFromFileCommand,
)


class FailingHumanLanguageStatsCommand(
    GetHumanLanguageStatsFromFileCommand
):
    """Deterministic file-analysis boundary for aggregate failure behavior."""

    def _analyze_file(
        self,
        file_path,
        ignore_comments=False,
        min_word_length=4,
        function_words=None,
    ):
        return {"error": "deterministic analysis failure"}


def test_missing_function_words_uses_documented_fallback(tmp_path, capsys):
    """A missing dictionary set must not crash the documented fallback path."""
    text_file = tmp_path / "sample.txt"
    text_file.write_text(
        "This document contains enough ordinary words for language analysis.",
        encoding="utf-8",
    )
    command = GetHumanLanguageStatsFromFileCommand()
    command.function_words = {}

    result = command.execute(str(text_file))

    assert capsys.readouterr().out == ""
    assert result["success"] is True
    assert result["files_processed"] == 1
    assert result["files_analyzed"] == 1
    assert result["files_failed"] == 0
    assert any(
        str(FUNCTION_WORDS_DIR) in warning
        or "less accurate" in warning
        for warning in result["warnings"]
    )
    assert str(text_file) in result["file_stats"]


def test_show_files_match_returns_paths_without_progress_output(
    tmp_path, capsys
):
    text_file = tmp_path / "sample.txt"
    text_file.write_text(
        "This document contains ordinary words for language analysis.",
        encoding="utf-8",
    )

    result = GetHumanLanguageStatsFromFileCommand().execute(
        str(text_file), show_files_match=True
    )

    assert capsys.readouterr().out == ""
    assert result["matched_files"] == [str(text_file)]


def test_file_analysis_failures_propagate_to_the_command_status(tmp_path):
    text_file = tmp_path / "sample.txt"
    text_file.write_text("Readable input.", encoding="utf-8")
    command = FailingHumanLanguageStatsCommand()

    result = command.execute(str(text_file))

    assert result["success"] is False
    assert result["status"] == "error"
    assert result["error_code"] == "partial_analysis_failure"
    assert result["files_analyzed"] == 0
    assert result["files_failed"] == 1
