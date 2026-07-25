#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Real-filesystem tests for findText."""

import re

import pytest

from qzx.commands.file.find_text import FindTextCommand


@pytest.fixture
def text_file(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text(
        "Line 1: TEST\n"
        "Line 2: example\n"
        "Line 3: test example\n"
        "Line 4\n",
        encoding="utf-8",
    )
    return path


def test_parse_recursive_parameter():
    command = FindTextCommand()
    assert command._parse_recursive_parameter(None) == 0
    assert command._parse_recursive_parameter("-r") is None
    assert command._parse_recursive_parameter("--recursive") is None
    assert command._parse_recursive_parameter("-r3") == 3
    assert command._parse_recursive_parameter("--recursive2") == 2
    assert command._parse_recursive_parameter("invalid") == 0


def test_search_file_uses_real_content_for_text_regex_and_case(text_file):
    command = FindTextCommand()

    exact = command._search_file(
        str(text_file), "test", False, True, 0, False, False, False
    )
    insensitive = command._search_file(
        str(text_file), "test", False, False, 0, False, False, False
    )
    regex = command._search_file(
        str(text_file),
        re.compile(r"Line \d:"),
        True,
        True,
        0,
        False,
        False,
        False,
    )

    assert exact["matches"] == 1
    assert insensitive["matches"] == 2
    assert regex["matches"] == 3


def test_search_file_context_inversion_and_count_use_real_lines(text_file):
    command = FindTextCommand()

    context = command._search_file(
        str(text_file), "example", False, True, 1, False, False, False
    )
    inverted = command._search_file(
        str(text_file), "example", False, True, 0, True, False, False
    )
    count = command._search_file(
        str(text_file), "example", False, True, 0, False, True, False
    )

    assert context["matches"] == 2
    assert {line["line_num"] for line in context["lines"]} == {1, 2, 3, 4}
    assert inverted["matches"] == 2
    assert [line["line_num"] for line in inverted["lines"]] == [1, 4]
    assert count["matches"] == 2
    assert "lines" not in count


def test_execute_searches_real_file_and_recursive_directory(tmp_path):
    first = tmp_path / "first.txt"
    nested = tmp_path / "nested"
    nested.mkdir()
    second = nested / "second.py"
    ignored = nested / "ignored.md"
    first.write_text("needle\nnone\nneedle\n", encoding="utf-8")
    second.write_text("needle\n", encoding="utf-8")
    ignored.write_text("needle\n", encoding="utf-8")

    single = FindTextCommand().execute("needle", str(first), colored=False)
    recursive = FindTextCommand().execute(
        "needle",
        str(tmp_path),
        recursive="-r",
        file_pattern="*.py",
        colored=False,
    )

    assert single["success"] is True
    assert single["files_searched"] == 1
    assert single["total_matches"] == 2
    assert recursive["success"] is True
    assert recursive["recursive"] == "unlimited"
    assert recursive["files_searched"] == 1
    assert recursive["files_with_matches"] == 1
    assert recursive["total_matches"] == 1
