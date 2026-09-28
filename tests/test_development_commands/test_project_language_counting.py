"""Differential contracts for the compact portable line counter."""

import random

import pytest
from pygments.lexers import get_lexer_by_name
from pygments.token import Comment, Name, String, Text

from qzx.commands.development._project_language_scan import count_lines


def reference_counts(text, lexer):
    """Independent, deliberately simple pre-optimization state model."""
    states = [{"code": False, "comment": False} for _ in text.splitlines()]
    if not states:
        return dict(total_lines=0, code_lines=0, comment_lines=0, blank_lines=0)
    line = 0
    for kind, value in lexer.get_tokens(text):
        for piece in value.splitlines(keepends=True):
            if line >= len(states):
                break
            content = piece.rstrip("\r\n")
            if content.strip():
                states[line]["comment" if kind in Comment else "code"] = True
            if piece.endswith(("\n", "\r")):
                line += 1
    code = sum(item["code"] for item in states)
    comments = sum(item["comment"] and not item["code"] for item in states)
    return dict(total_lines=len(states), code_lines=code, comment_lines=comments,
                blank_lines=len(states) - code - comments)


class TokenStream:
    def __init__(self, tokens):
        self.tokens = tokens

    def get_tokens(self, text):
        return iter(self.tokens)


@pytest.mark.parametrize("ending", ["", "\n", "\r", "\r\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"])
def test_token_boundaries_and_unicode_line_separators(ending):
    tokens = [(Comment.Single, "# note" + ending), (Name, "a"),
              (Text, " \t"), (Comment.Multiline, "/* x */" + ending),
              (Text, ending), (String, '"# not a comment"' + ending)]
    text = "".join(value for _, value in tokens)
    assert count_lines(text, TokenStream(tokens)) == reference_counts(text, TokenStream(tokens))


@pytest.mark.parametrize("alias", ["python", "rust", "cpp", "javascript", "php", "html", "css", "json", "toml", "powershell", "yaml", "bash"])
def test_real_lexers_preserve_multiline_and_trailing_line_counts(alias):
    text = '# comment\n/* comment\n continued */\nx = "# string"; // tail\n\n  \nlast'
    lexer = get_lexer_by_name(alias, stripnl=False, ensurenl=False)
    assert count_lines(text, lexer) == reference_counts(text, lexer)


def test_randomized_token_streams_match_reference():
    rng = random.Random(25092026)
    kinds = [Name, Text, Comment, Comment.Single, Comment.Multiline, String]
    pieces = ["", "a", "# note", "\n", "\r\n", "\r", " \t", "\u2028", "x\ny\n", "\x85"]
    for _ in range(1000):
        tokens = [(rng.choice(kinds), rng.choice(pieces)) for _ in range(rng.randrange(40))]
        text = "".join(value for _, value in tokens)
        assert count_lines(text, TokenStream(tokens)) == reference_counts(text, TokenStream(tokens))


def test_empty_input_does_not_start_lexer():
    class UnusedLexer:
        def get_tokens(self, text):
            raise AssertionError("Empty input must not be lexed")

    assert count_lines("", UnusedLexer()) == dict(total_lines=0, code_lines=0, comment_lines=0, blank_lines=0)


def test_filtered_token_stream_is_not_bypassed():
    lexer = get_lexer_by_name("python", stripnl=False, ensurenl=False)
    lexer.add_filter("gobble", n=2)
    text = "  # comment\n  print('x')\n\n"
    assert count_lines(text, lexer) == reference_counts(text, lexer)
