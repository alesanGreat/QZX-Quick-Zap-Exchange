"""Focused analysis contracts for getHumanLanguageStats."""

from qzx.commands.file.get_human_language_stats import (
    GetHumanLanguageStatsFromFileCommand,
)


def _command_with_words():
    command = GetHumanLanguageStatsFromFileCommand()
    command.function_words = {
        "english": {"this", "that", "with", "from"},
        "spanish": {"este", "esta", "para", "como"},
    }
    command.dictionary_warnings = []
    return command


def test_language_filter_limits_selected_dictionaries(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text(
        "este texto para prueba with this document",
        encoding="utf-8",
    )

    result = _command_with_words().execute(
        str(target),
        languages="spanish",
        min_word_length=2,
    )

    stats = result["file_stats"][str(target)]
    assert result["success"] is True
    assert set(stats["word_count_by_language"]) <= {"spanish"}


def test_ignore_comments_removes_python_comment_words(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text(
        "value = 1  # este comentario para prueba\n"
        "text = 'this ordinary document'\n",
        encoding="utf-8",
    )

    with_comments = _command_with_words().execute(
        str(target),
        ignore_comments=False,
        min_word_length=2,
    )
    without_comments = _command_with_words().execute(
        str(target),
        ignore_comments=True,
        min_word_length=2,
    )

    with_stats = with_comments["file_stats"][str(target)]
    without_stats = without_comments["file_stats"][str(target)]
    assert with_stats["word_count_by_language"].get("spanish", 0) > 0
    assert without_stats["word_count_by_language"].get("spanish", 0) == 0


def test_mixed_language_fixture_sections_are_preserved(tmp_path):
    target = tmp_path / "mixed-languages.txt"
    target.write_text(
        "====== English ======\n"
        "This ordinary language section contains words.\n"
        "====== Español ======\n"
        "Este contenido español contiene palabras.\n",
        encoding="utf-8",
    )

    result = _command_with_words().execute(
        str(target),
        min_word_length=2,
    )

    stats = result["file_stats"][str(target)]
    assert stats["word_count_by_language"]["english"] > 0
    assert stats["word_count_by_language"]["spanish"] > 0


def test_detect_word_language_recognizes_major_non_latin_scripts():
    command = _command_with_words()

    assert command._detect_word_language("привет") == "russian"
    assert command._detect_word_language("γειά") == "greek"
    assert command._detect_word_language("مرحبا") == "arabic"
    assert command._detect_word_language("שלום") == "hebrew"
    assert command._detect_word_language("中文") == "cjk"
    assert command._detect_word_language("नमस्ते") == "hindi"
