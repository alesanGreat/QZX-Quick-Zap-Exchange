"""Regression tests for the getHumanLanguageStats command."""

from qzx.commands.file.get_human_language_stats import (
    FUNCTION_WORDS_DIR,
    GetHumanLanguageStatsFromFileCommand,
)


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

    output = capsys.readouterr().out
    assert str(FUNCTION_WORDS_DIR) in output
    assert result["success"] is True
    assert result["files_processed"] == 1
    assert str(text_file) in result["file_stats"]
